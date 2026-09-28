#!/usr/bin/env python3
"""ModelExpress (MX) for Engel AI Main — weight-location broker + client library.

Implements the ModelExpress architecture against Engel's real hardware:

  CONTROL PLANE  MX Server brokers metadata; a Metadata Store records which model
                 weights are resident where. Engel has no Redis/K8s backend, so the
                 store is Engel's usual on-disk JSON receipt (same durability story
                 as every other Engel registry). Substitution is reported, not hidden.

  DATA PLANE     Weights either move client-to-client over P2P GPUDirect RDMA, or
                 stream from file/object storage through ModelStreamer.

Why the plan almost always says POSIX here: peer-to-peer GPUDirect RDMA needs two or
more GPUs and an RDMA-capable fabric, and GPUDirect Storage needs NIXL/cuFile. This
box has ONE RTX 2070 on a 1 GbE Realtek NIC with no NIXL installed, so those lanes
are reported UNAVAILABLE with a reason instead of being stubbed out as if they work.
POSIX I/O is the diagram's own documented default, and it is what actually runs.

The value MX adds to Engel today is the control plane: several lanes (the ROG GPU
chat server, the CT246 local model, the image lane) each load weights independently
with no shared record of who already holds what. This gives them one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = ROOT / "runtime" / "model_express"
REGISTRY_PATH = STORE_DIR / "registry.json"
RECEIPT_DIR = ROOT / "reports" / "model_express"

MX_SERVER_PORT = int(os.environ.get("ENGEL_MX_SERVER_PORT", "24894") or "24894")
MX_SERVER_URL = f"http://127.0.0.1:{MX_SERVER_PORT}"

# Transport identifiers, best first. The diagram's ordering: peer RDMA beats storage,
# and GPUDirect Storage beats plain POSIX.
TRANSPORT_P2P_RDMA = "p2p_gpudirect_rdma_nixl"
TRANSPORT_GDS = "modelstreamer_gpudirect_storage_nixl"
TRANSPORT_POSIX = "modelstreamer_posix_io"

SCHEMA_REGISTRY = "engel_model_express_registry_v1"
SCHEMA_PLAN = "engel_model_express_load_plan_v1"
SCHEMA_CAPS = "engel_model_express_capabilities_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# capabilities — what this machine can actually do
# --------------------------------------------------------------------------- #
def _gpu_count() -> tuple[int, list[str]]:
    exe = shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
    if not Path(exe).is_file():
        return 0, []
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except Exception:
        return 0, []
    names = [line.strip() for line in out.splitlines() if line.strip()]
    return len(names), names


def _module_present(name: str) -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def _rdma_fabric_present() -> tuple[bool, str]:
    """RoCE/InfiniBand heuristic. Consumer GbE is not an RDMA fabric."""
    if platform.system() != "Windows":
        return (Path("/sys/class/infiniband").is_dir(), "checked /sys/class/infiniband")
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-NetAdapterRdma | Where-Object Enabled | Select-Object -ExpandProperty Name",
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        return False, f"RDMA adapter query failed: {type(exc).__name__}"
    adapters = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    if adapters:
        return True, "RDMA-enabled adapters: " + ", ".join(adapters)
    return False, "no RDMA-enabled network adapter"


def mx_capabilities(refresh: bool = True) -> dict[str, Any]:
    """What the data plane can really do on this host, with a reason for each no."""
    gpus, gpu_names = _gpu_count()
    nixl = _module_present("nixl")
    gds_lib = _module_present("cufile") or _module_present("kvikio")
    rdma_ok, rdma_detail = _rdma_fabric_present()

    p2p_reasons = []
    if gpus < 2:
        p2p_reasons.append(f"peer GPUDirect needs >=2 GPUs, found {gpus}")
    if not nixl:
        p2p_reasons.append("NIXL python module not installed")
    if not rdma_ok:
        p2p_reasons.append(rdma_detail)

    gds_reasons = []
    if not nixl:
        gds_reasons.append("NIXL python module not installed")
    if not gds_lib:
        gds_reasons.append("no cuFile/kvikio GPUDirect Storage binding")

    return {
        "schema": SCHEMA_CAPS,
        "checked_at_utc": _now(),
        "host": socket.gethostname(),
        "gpu_count": gpus,
        "gpus": gpu_names,
        "nixl_present": nixl,
        "gds_binding_present": gds_lib,
        "rdma_fabric_present": rdma_ok,
        "rdma_detail": rdma_detail,
        "transports": {
            TRANSPORT_P2P_RDMA: {
                "available": not p2p_reasons,
                "reasons_unavailable": p2p_reasons,
            },
            TRANSPORT_GDS: {
                "available": not gds_reasons,
                "reasons_unavailable": gds_reasons,
            },
            # POSIX is the documented default and always works.
            TRANSPORT_POSIX: {"available": True, "reasons_unavailable": []},
        },
        "metadata_store_backend": "engel_json_receipt",
        "metadata_store_note": (
            "reference architecture uses Redis/K8s; Engel has neither, so the store is "
            "an atomic on-disk JSON registry with the same durability story as other "
            "Engel registries"
        ),
    }


# --------------------------------------------------------------------------- #
# metadata store
# --------------------------------------------------------------------------- #
def load_registry() -> dict[str, Any]:
    data = _read_json(REGISTRY_PATH)
    if data.get("schema") != SCHEMA_REGISTRY:
        return {"schema": SCHEMA_REGISTRY, "updated_at_utc": _now(), "entries": {}}
    if not isinstance(data.get("entries"), dict):
        data["entries"] = {}
    return data


def save_registry(registry: dict[str, Any]) -> None:
    registry["schema"] = SCHEMA_REGISTRY
    registry["updated_at_utc"] = _now()
    _write_json_atomic(REGISTRY_PATH, registry)


def _entry_key(model_id: str, holder: str, device: str) -> str:
    return f"{model_id}::{holder}::{device}"


def register_resident_weights(
    model_id: str,
    weights_path: str,
    holder: str,
    device: str = "cpu",
    bytes_total: int | None = None,
    sha256: str = "",
    lane: str = "",
    resident: bool = True,
) -> dict[str, Any]:
    """MX Client Library: announce that these weights are resident on this holder.

    `holder` is the engine/host that has them (e.g. the ROG GPU chat server), `device`
    the memory they occupy (cuda:0, cpu, or a storage path for cold weights).
    """
    model_id = str(model_id or "").strip()
    if not model_id:
        raise ValueError("model_id is required")
    holder = str(holder or "").strip() or socket.gethostname()
    registry = load_registry()
    key = _entry_key(model_id, holder, device)
    registry["entries"][key] = {
        "model_id": model_id,
        "weights_path": str(weights_path),
        "holder": holder,
        "device": device,
        "lane": lane,
        "bytes_total": bytes_total,
        "sha256": sha256,
        "resident": bool(resident),
        "registered_at_utc": _now(),
    }
    save_registry(registry)
    return registry["entries"][key]


def locate(model_id: str) -> list[dict[str, Any]]:
    """Every known holder of these weights, GPU-resident holders first."""
    model_id = str(model_id or "").strip()
    entries = [
        entry
        for entry in load_registry()["entries"].values()
        if entry.get("model_id") == model_id
    ]

    def rank(entry: dict[str, Any]) -> tuple[int, str]:
        device = str(entry.get("device") or "")
        gpu_resident = entry.get("resident") is True and device.startswith("cuda")
        return (0 if gpu_resident else 1, str(entry.get("registered_at_utc") or ""))

    return sorted(entries, key=rank)


def forget(model_id: str = "", holder: str = "") -> int:
    """Drop registry entries. A holder that unloaded its weights must say so, or the
    broker will keep recommending a peer that no longer has them."""
    registry = load_registry()
    before = len(registry["entries"])
    registry["entries"] = {
        key: entry
        for key, entry in registry["entries"].items()
        if not (
            (not model_id or entry.get("model_id") == model_id)
            and (not holder or entry.get("holder") == holder)
        )
    }
    save_registry(registry)
    return before - len(registry["entries"])


# --------------------------------------------------------------------------- #
# load planning — the decision the diagram encodes
# --------------------------------------------------------------------------- #
def plan_load(
    model_id: str,
    requesting_holder: str = "",
    caps: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Choose how the NEW engine should get these weights.

    Order follows the architecture: a peer that already holds them in GPU memory over
    P2P RDMA, else stream from storage with GPUDirect Storage, else POSIX I/O.
    """
    capabilities = caps or mx_capabilities()
    transports = capabilities.get("transports", {})
    requesting_holder = str(requesting_holder or "").strip() or socket.gethostname()
    holders = locate(model_id)
    peers = [
        entry
        for entry in holders
        if entry.get("holder") != requesting_holder
        and entry.get("resident") is True
        and str(entry.get("device") or "").startswith("cuda")
    ]
    storage = [
        entry for entry in holders if Path(str(entry.get("weights_path") or "")).exists()
    ]

    considered: list[dict[str, Any]] = []

    def note(transport: str, chosen: bool, why: str) -> None:
        considered.append({"transport": transport, "chosen": chosen, "why": why})

    if peers and transports.get(TRANSPORT_P2P_RDMA, {}).get("available") is True:
        note(TRANSPORT_P2P_RDMA, True, f"peer {peers[0]['holder']} holds them in {peers[0]['device']}")
        chosen, source = TRANSPORT_P2P_RDMA, peers[0]
    else:
        if not peers:
            note(TRANSPORT_P2P_RDMA, False, "no peer holds these weights in GPU memory")
        else:
            note(
                TRANSPORT_P2P_RDMA,
                False,
                "; ".join(transports.get(TRANSPORT_P2P_RDMA, {}).get("reasons_unavailable", []))
                or "peer transport unavailable",
            )
        if storage and transports.get(TRANSPORT_GDS, {}).get("available") is True:
            note(TRANSPORT_GDS, True, "streaming from storage with GPUDirect Storage")
            chosen, source = TRANSPORT_GDS, storage[0]
        else:
            if storage:
                note(
                    TRANSPORT_GDS,
                    False,
                    "; ".join(transports.get(TRANSPORT_GDS, {}).get("reasons_unavailable", []))
                    or "GPUDirect Storage unavailable",
                )
                note(TRANSPORT_POSIX, True, "POSIX I/O is the documented default fallback")
                chosen, source = TRANSPORT_POSIX, storage[0]
            else:
                note(TRANSPORT_GDS, False, "no reachable weights file registered")
                note(TRANSPORT_POSIX, False, "no reachable weights file registered")
                chosen, source = "", {}

    return {
        "schema": SCHEMA_PLAN,
        "planned_at_utc": _now(),
        "model_id": model_id,
        "requesting_holder": requesting_holder,
        "ok": bool(chosen),
        "transport": chosen,
        "source": source,
        "known_holders": len(holders),
        "gpu_resident_peers": len(peers),
        "transports_considered": considered,
        "status": (
            f"load {model_id} via {chosen}" if chosen
            else f"no usable source registered for {model_id}"
        ),
    }


# --------------------------------------------------------------------------- #
# ModelStreamer — the storage data plane that actually runs here
# --------------------------------------------------------------------------- #
def stream_weights(
    weights_path: str,
    chunk_bytes: int = 8 * 1024 * 1024,
    verify_sha256: bool = False,
    limit_bytes: int | None = None,
) -> dict[str, Any]:
    """Stream weights from file storage with POSIX I/O and measure real throughput.

    This is a measurement/verification path, not a model loader: it proves the storage
    lane is readable at a known rate. `limit_bytes` keeps a verifier from reading a
    30 GB file end to end.
    """
    path = Path(weights_path)
    if not path.is_file():
        return {"ok": False, "status": f"weights not found: {path}"}
    digest = hashlib.sha256() if verify_sha256 else None
    read_total = 0
    started = time.perf_counter()
    try:
        with path.open("rb") as handle:
            while True:
                if limit_bytes is not None and read_total >= limit_bytes:
                    break
                chunk = handle.read(chunk_bytes)
                if not chunk:
                    break
                read_total += len(chunk)
                if digest is not None:
                    digest.update(chunk)
    except OSError as exc:
        return {"ok": False, "status": f"read failed: {exc}", "bytes_read": read_total}
    elapsed = max(1e-6, time.perf_counter() - started)
    return {
        "ok": True,
        "status": "streamed from file storage via POSIX I/O",
        "transport": TRANSPORT_POSIX,
        "weights_path": str(path),
        "bytes_read": read_total,
        "bytes_total": path.stat().st_size,
        "partial": limit_bytes is not None and read_total >= (limit_bytes or 0),
        "elapsed_seconds": round(elapsed, 4),
        "throughput_mib_s": round((read_total / (1024 * 1024)) / elapsed, 1),
        "sha256": digest.hexdigest() if digest is not None else "",
    }


# --------------------------------------------------------------------------- #
# discovery — register Engel's real lanes so the registry reflects reality
# --------------------------------------------------------------------------- #
def _gpu_lane_model() -> dict[str, Any]:
    """The model the ROG GPU chat server currently holds, read from its command line."""
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "
                "'*llama_cpp.server*' } | Select-Object -First 1 -ExpandProperty CommandLine",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except Exception:
        return {}
    marker = "--model"
    if marker not in out:
        return {}
    tail = out.split(marker, 1)[1].strip()
    if tail.startswith('"'):
        model_path = tail[1:].split('"', 1)[0]
    else:
        model_path = tail.split()[0] if tail.split() else ""
    if not model_path:
        return {}
    return {"weights_path": model_path, "device": "cuda:0"}


CT_SSH_KEY = Path(os.environ.get("ENGEL_CT_SSH_KEY", "")) if os.environ.get(
    "ENGEL_CT_SSH_KEY"
) else Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519"
CT_HOST = os.environ.get("ENGEL_CT_HOST", "192.0.2.50")
CT_PORT = os.environ.get("ENGEL_MAIN_SERVER_SSH_PORT", "24622")
CT_MODELS_ROOT = "/opt/engel/models-active/llm"


def discover_ct246_engine() -> dict[str, Any]:
    """Register the OTHER Engel inference engine — the CT246 chat runtime.

    This is the second "Inference Engine" box in the architecture: a real Engel part,
    not a placeholder. Its weights live on the CT SSD, so they are a legitimate
    ModelStreamer source even though no RDMA path exists to them from here.
    """
    if not CT_SSH_KEY.is_file():
        return {"ok": False, "status": f"CT ssh key not found: {CT_SSH_KEY}"}
    listing = (
        f"find {CT_MODELS_ROOT} -maxdepth 2 -name '*.gguf' -printf '%s %p\\n' 2>/dev/null"
    )
    try:
        out = subprocess.run(
            [
                "ssh",
                "-i",
                str(CT_SSH_KEY),
                "-p",
                str(CT_PORT),
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=15",
                f"root@{CT_HOST}",
                listing,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        return {"ok": False, "status": f"CT query failed: {type(exc).__name__}: {exc}"}
    registered: list[dict[str, Any]] = []
    for line in out.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        size, remote_path = int(parts[0]), parts[1]
        registered.append(
            register_resident_weights(
                model_id=remote_path.rsplit("/", 1)[-1],
                weights_path=remote_path,
                holder="ct246:engel-main-chat",
                # CT weights are on its SSD, not in GPU memory (CT has no GPU).
                device="file:/opt/engel/models-active",
                bytes_total=size,
                lane="ct246_local_model",
                resident=False,
            )
        )
    return {"ok": True, "holder": "ct246:engel-main-chat", "registered": registered}


def discover_and_register(host: str = "") -> dict[str, Any]:
    """Seed the Metadata Store from what this host really has."""
    host = str(host or "").strip() or socket.gethostname()
    registered: list[dict[str, Any]] = []

    lane = _gpu_lane_model()
    if lane:
        path = Path(lane["weights_path"])
        registered.append(
            register_resident_weights(
                model_id=path.name,
                weights_path=str(path),
                holder=f"{host}:rog-gpu-chat-8899",
                device=lane["device"],
                bytes_total=path.stat().st_size if path.is_file() else None,
                lane="rog_rtx2070_llama_cpp_gpu",
                resident=True,
            )
        )

    # Cold weights on local file storage are still a valid ModelStreamer source.
    gpu_models = ROOT / "runtime" / "gpu_models"
    if gpu_models.is_dir():
        for candidate in sorted(gpu_models.glob("*.gguf")):
            already = any(
                entry.get("weights_path") == str(candidate)
                and str(entry.get("device") or "").startswith("cuda")
                for entry in load_registry()["entries"].values()
            )
            if already:
                continue
            registered.append(
                register_resident_weights(
                    model_id=candidate.name,
                    weights_path=str(candidate),
                    holder=f"{host}:file-storage",
                    device=f"file:{gpu_models.name}",
                    bytes_total=candidate.stat().st_size,
                    lane="file_storage_local",
                    resident=False,
                )
            )
    ct = discover_ct246_engine()
    if ct.get("ok") is True:
        registered.extend(ct.get("registered") or [])
    return {
        "ok": True,
        "host": host,
        "registered_count": len(registered),
        "ct246_engine": {"ok": ct.get("ok"), "status": ct.get("status", "registered")},
        "registered": registered,
    }


# Measured on 2026-07-30 (operator directive: best hardware for each model).
# These are RECEIPTS of real benchmarks, not estimates — re-measure before editing.
# ROG RTX 2070: Mistral-7B Q4 completion, 171 tok / 3.39 s. CT246 E5-2660 v3:
# deepseek-r1 7B Q5 thread sweep 8/10/12/16/24 -> 3.35/3.57/3.69/3.4/2.5 tok/s
# (memory-bandwidth-bound; hyperthreads hurt; service pinned to 12 threads).
MEASURED_THROUGHPUT = {
    "rog_rtx2070_7b_q4": {"tok_s": 50.4, "measured_at": "2026-07-30"},
    "rog_rtx2070_7b_q5_lora": {"tok_s": 35.8, "measured_at": "2026-07-30"},
    "ct246_cpu_7b_q5_12t": {"tok_s": 3.69, "measured_at": "2026-07-30"},
}

# Every serving role in the cluster and WHY its seat is the right one. A role is
# either on the best hardware outright, or carries the documented trade that keeps
# it where it is. An empty `why` is a verifier failure — placement without a
# reason is how quiet misplacements (math on CPU while the GPU idles) happen.
PLACEMENT_ROLES = [
    {"role": "general_chat_big_lane",
     "model": "qwen2.5-7b-instruct-q5 + vipy LoRA (persona-aligned)",
     "host": "ROG", "device": "cuda:0 (RTX 2070), n_ctx 6144", "tok_s": 35.8,
     "placement": "best_available",
     "why": "operator-approved 2026-07-30: the ALIGNED product-voice model (better math "
            "than Mistral, canary-gated adapter B4DD1B93) on the fastest device; Q5 costs "
            "~14 tok/s vs Mistral Q4 but buys quality + alignment; 6.7 GB of 8 GB, "
            "identity verified through the full pipeline; Mistral Q4 kept on disk as rollback"},
    {"role": "math_deterministic_lane", "model": "sympy 1.14 (no LLM)",
     "host": "CT246", "device": "cpu (training venv subprocess)", "tok_s": None,
     "placement": "best_available",
     "why": "exact CAS computation is CPU-trivial (<1 s/turn); a GPU adds nothing"},
    {"role": "math_reasoning_specialist", "model": "deepseek-r1-distill-qwen-7b-q5",
     "host": "CT246", "device": "cpu 12 threads", "tok_s": 3.69,
     "placement": "documented_tradeoff",
     "why": "best AVAILABLE seat: the RTX 2070 (would be ~50 tok/s) is held by the "
            "higher-traffic chat lane; both 7Bs cannot co-fit in 8 GB, and an "
            "on-demand swap costs ~2-4 min of cold chat per math turn plus OOM risk. "
            "Rare minutes-long specialist turns lose that trade"},
    {"role": "deep_local_14b", "model": "qwen2.5-14b-instruct-Q4",
     "host": "CT246", "device": "cpu 12 threads", "tok_s": None,
     "placement": "best_available",
     "why": "14B cannot fit the 8 GB GPU at all; explicit-request-only lane tolerates CPU pace"},
    {"role": "quick_persona_lane", "model": "engel-qwen2.5-1.5b-deepreason",
     "host": "CT246", "device": "cpu", "tok_s": None,
     "placement": "best_available",
     "why": "1.5B is fast enough on CPU; spending GPU on it would evict the chat model"},
    {"role": "code_lane", "model": "qwen2.5-coder-3b-instruct-q5",
     "host": "CT246", "device": "cpu", "tok_s": None,
     "placement": "best_available",
     "why": "3B on CPU meets the lane's latency; GPU is spoken for"},
    {"role": "image_lane", "model": "sdxl-turbo",
     "host": "ROG", "device": "cuda:0 (RTX 2070, port 8931)", "tok_s": None,
     "placement": "best_available",
     "why": "diffusion is GPU-only in practice; shares the 2070 with chat by design"},
    {"role": "embedding_search", "model": "nomic-embed-text-v1.5",
     "host": "CT246", "device": "cpu (memory-search service)", "tok_s": None,
     "placement": "best_available",
     "why": "embedding batches are small and latency-tolerant"},
]

PLACEMENT_OPEN_RECOMMENDATION = (
    "DONE 2026-07-30: aligned qwen2.5-7b+vipy is the GPU tenant (Qwen's 4-KV-head "
    "GQA made Q5 fit at n_ctx 6144 — 6.7 of 8 GB — no Q4 quant needed). One "
    "operational item outstanding: the EngelRogGpuModelServer scheduled task still "
    "carries the broken --lora flag and needs ONE elevated setup re-run "
    "(Setup-EngelStackLifecycle-RunAsAdmin.cmd, script already corrected to "
    "--lora_path); until then a manual server process holds port 8899."
)


def placement_report() -> dict[str, Any]:
    """The cluster's model-to-hardware map with measured numbers and reasons."""
    report = {
        "schema": "engel_model_express_placement_v1",
        "generated_at_utc": _now(),
        "measured_throughput": MEASURED_THROUGHPUT,
        "roles": PLACEMENT_ROLES,
        "open_recommendation": PLACEMENT_OPEN_RECOMMENDATION,
        "ok": all(r.get("why") and r.get("placement") for r in PLACEMENT_ROLES),
    }
    write_receipt(report, "PLACEMENT")
    return report


def mx_status() -> dict[str, Any]:
    registry = load_registry()
    caps = mx_capabilities()
    entries = list(registry["entries"].values())
    return {
        "schema": "engel_model_express_status_v1",
        "updated_at_utc": _now(),
        "mx_server_url": MX_SERVER_URL,
        "registry_path": str(REGISTRY_PATH),
        "entry_count": len(entries),
        "models_known": sorted({str(e.get("model_id")) for e in entries}),
        "gpu_resident_count": sum(
            1
            for e in entries
            if e.get("resident") is True and str(e.get("device") or "").startswith("cuda")
        ),
        "capabilities": caps,
        "available_transports": [
            name
            for name, info in caps.get("transports", {}).items()
            if info.get("available") is True
        ],
    }


def write_receipt(payload: dict[str, Any], name: str) -> Path:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = RECEIPT_DIR / f"ENGEL_MODEL_EXPRESS_{name}_{stamp}.json"
    _write_json_atomic(path, payload)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Engel ModelExpress client")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="registry + capability report")
    sub.add_parser("capabilities", help="what the data plane can do on this host")
    sub.add_parser("placement", help="model-to-hardware map with measured throughput")
    sub.add_parser("discover", help="register this host's real weights")
    loc = sub.add_parser("locate", help="who holds these weights")
    loc.add_argument("model_id")
    pl = sub.add_parser("plan", help="how a new engine should load these weights")
    pl.add_argument("model_id")
    pl.add_argument("--requesting-holder", default="")
    st = sub.add_parser("stream", help="measure the storage lane")
    st.add_argument("weights_path")
    st.add_argument("--limit-mib", type=int, default=256)
    fg = sub.add_parser("forget", help="drop registry entries")
    fg.add_argument("--model-id", default="")
    fg.add_argument("--holder", default="")
    args = parser.parse_args()

    if args.command == "status":
        payload = mx_status()
    elif args.command == "capabilities":
        payload = mx_capabilities()
    elif args.command == "placement":
        payload = placement_report()
    elif args.command == "discover":
        payload = discover_and_register()
    elif args.command == "locate":
        payload = {"model_id": args.model_id, "holders": locate(args.model_id)}
    elif args.command == "plan":
        payload = plan_load(args.model_id, args.requesting_holder)
    elif args.command == "stream":
        payload = stream_weights(
            args.weights_path, limit_bytes=max(1, args.limit_mib) * 1024 * 1024
        )
    elif args.command == "forget":
        payload = {"ok": True, "forgotten": forget(args.model_id, args.holder)}
    else:
        payload = {"ok": False, "status": f"unknown command {args.command}"}

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
