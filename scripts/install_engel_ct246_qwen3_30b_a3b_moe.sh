#!/usr/bin/env bash
set -euo pipefail

if [[ "$(hostname)" != "engel-ai-main" ]]; then
  echo "Refusing model installation outside CT246 engel-ai-main" >&2
  exit 2
fi

root="/opt/engel/models-active/llm/qwen3-30b-a3b"
model="$root/Qwen3-30B-A3B-Q4_K_M.gguf"
partial="$model.partial"
receipt="/opt/engel/memory/models/ENGEL_QWEN3_30B_A3B_MOE_INSTALL.json"
commit="e4d4bafdfb96a411a163846265362aceb0b9c63a"
sha256="0d003f6662faee786ed5da3e31b29c978de5ae5d275c8794c606a7f3c01aa8f5"
url="https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF/resolve/${commit}/Qwen3-30B-A3B-Q4_K_M.gguf"

target_source="$(findmnt -n -o SOURCE -T /opt/engel)"
target_path="$(findmnt -n -o TARGET -T /opt/engel)"
case "${target_source,,} ${target_path,,}" in
  *engel-vault*|*powervault*|*/mnt/engel-vault*)
    echo "Refusing PowerVault/external-array model target" >&2
    exit 3
    ;;
esac

available_bytes="$(df --output=avail -B1 /opt/engel | tail -1 | tr -d ' ')"
required_bytes=$((22 * 1024 * 1024 * 1024))
if (( available_bytes < required_bytes )) && [[ ! -f "$model" ]]; then
  echo "Need at least 22 GiB free on CT246 SSD before download" >&2
  exit 4
fi

mkdir -p "$root" "$(dirname "$receipt")"
if [[ -f "$model" ]]; then
  observed="$(sha256sum "$model" | awk '{print $1}')"
  if [[ "$observed" != "$sha256" ]]; then
    echo "Existing model hash mismatch; refusing overwrite" >&2
    exit 5
  fi
else
  curl \
    --fail \
    --location \
    --continue-at - \
    --retry 8 \
    --retry-all-errors \
    --connect-timeout 20 \
    --output "$partial" \
    "$url"
  observed="$(sha256sum "$partial" | awk '{print $1}')"
  if [[ "$observed" != "$sha256" ]]; then
    echo "Downloaded model hash mismatch" >&2
    exit 6
  fi
  mv "$partial" "$model"
fi

chmod 0640 "$model"
observed_bytes="$(stat -c '%s' "$model")"
observed_sha256="$observed"
installed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

/opt/engel/.venv/bin/python - "$receipt" "$model" "$observed_bytes" \
  "$observed_sha256" "$commit" "$target_source" "$target_path" "$installed_at" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

receipt, model, size, digest, commit, source, target, installed_at = sys.argv[1:]
payload = {
    "schema": "engel_qwen3_30b_a3b_moe_install_v1",
    "ok": True,
    "installed_at_utc": installed_at,
    "container": "CT246",
    "hostname": "engel-ai-main",
    "storage_policy": "CT246 engel-fast-ssd active runtime",
    "power_vault_used": False,
    "google_drive_used": False,
    "model": {
        "repository": "Qwen/Qwen3-30B-A3B-GGUF",
        "revision": commit,
        "quantization": "Q4_K_M",
        "path": model,
        "bytes": int(size),
        "sha256": digest,
        "architecture": "sparse_mixture_of_experts",
        "total_parameters_billions": 30.5,
        "active_parameters_billions_per_token": 3.3,
        "expert_count": 128,
        "active_experts_per_token": 8,
    },
    "filesystem": {
        "source": source,
        "target": target,
    },
}
path = Path(receipt)
temp = path.with_suffix(path.suffix + ".tmp")
temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temp.replace(path)

active_root = Path("/opt/engel/models-active")
extensions = {".bin", ".ckpt", ".gguf", ".pt", ".pth", ".safetensors"}
files = []
by_extension = {}
for candidate in active_root.rglob("*"):
    if not candidate.is_file() or candidate.suffix.casefold() not in extensions:
        continue
    try:
        file_bytes = candidate.stat().st_size
    except OSError:
        continue
    suffix = candidate.suffix.casefold()
    files.append((file_bytes, str(candidate)))
    bucket = by_extension.setdefault(suffix, {"count": 0, "bytes": 0})
    bucket["count"] += 1
    bucket["bytes"] += file_bytes
total_bytes = sum(item[0] for item in files)
largest = [
    {"path": file_path, "bytes": file_bytes, "gib": round(file_bytes / 1024**3, 2)}
    for file_bytes, file_path in sorted(files, reverse=True)[:20]
]
inventory = {
    "schema": "engel_ct_fast_ssd_model_inventory_v1",
    "ok": True,
    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    "refresh_source": "install_engel_ct246_qwen3_30b_a3b_moe.sh",
    "active_model_root": str(active_root),
    "active_runtime_storage": "engel-fast-ssd",
    "model_file_count": len(files),
    "model_total_bytes": total_bytes,
    "model_total_gib": round(total_bytes / 1024**3, 2),
    "by_extension": by_extension,
    "largest_files": largest,
    "du_models_active": subprocess.run(
        ["du", "-sh", str(active_root)],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip(),
    "df_opt_engel": subprocess.run(
        ["df", "-h", "/opt/engel"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip(),
    "vault_used_as_copy_source": False,
    "vault_used_for_active_runtime": False,
    "powervault_used": False,
    "ct245_used": False,
}
inventory_path = Path(
    "/opt/engel/memory/models/ENGEL_CT_FAST_SSD_MODEL_INVENTORY.json"
)
inventory_temp = inventory_path.with_suffix(inventory_path.suffix + ".tmp")
inventory_temp.write_text(
    json.dumps(inventory, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
inventory_temp.replace(inventory_path)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
