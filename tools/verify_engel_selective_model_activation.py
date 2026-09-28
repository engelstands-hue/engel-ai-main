#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


class FakeLlama:
    instances: list["FakeLlama"] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.closed = False
        self.__class__.instances.append(self)

    def create_chat_completion(self, **_: object) -> dict[str, object]:
        return {"choices": [{"message": {"content": "selective local model reply"}}]}

    def close(self) -> None:
        self.closed = True


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    sys.modules["llama_cpp"] = types.SimpleNamespace(Llama=FakeLlama)
    os.environ["ENGEL_LOCAL_MODEL_CACHE_MAX_MODELS"] = "1"
    os.environ["ENGEL_LOCAL_MODEL_CACHE_MAX_GGUF_BYTES"] = str(1024 * 1024)

    import engel_local_model_service as service

    service._MODEL_CACHE.clear()
    service._LOAD_COUNT = 0
    service._EVICTION_COUNT = 0

    with tempfile.TemporaryDirectory(prefix="engel-selective-model-") as temp:
        first_path = Path(temp) / "quick.gguf"
        second_path = Path(temp) / "Qwen3-30B-A3B-Q4_K_M.gguf"
        first_path.write_bytes(b"quick")
        second_path.write_bytes(b"deep")

        common = {
            "lora_path": "",
            "prompt": "Answer locally.",
            "n_predict": 16,
            "ctx": 6144,
            "n_gpu_layers": 0,
            "temperature": 0.1,
        }
        first = service.run_llama_cpp_lora_text_with_model(
            model_path=str(first_path), **common
        )
        second = service.run_llama_cpp_lora_text_with_model(
            model_path=str(second_path), **common
        )
        status = service.local_model_cache_status()

    require(first.get("ok") is True, "first selective model call failed")
    require(second.get("ok") is True, "second selective model call failed")
    require(len(FakeLlama.instances) == 2, "expected two task-selected model loads")
    require(FakeLlama.instances[0].closed, "prior model was not closed on lane switch")
    require(not FakeLlama.instances[1].closed, "selected model was closed unexpectedly")
    require(
        second.get("model_cache_evicted") == ["quick.gguf"],
        "lane switch did not report the evicted model",
    )
    require(status.get("active_model_count") == 1, "more than one model remains resident")
    require(
        status.get("active_models", [{}])[0].get("model_name")
        == "Qwen3-30B-A3B-Q4_K_M.gguf",
        "active cache does not contain only the selected model",
    )
    require(
        status.get("activation_mode") == "task_routed_single_resident_mmap",
        "selective activation mode is not reported",
    )
    require(
        second.get("adaptive_context", {}).get("active_ctx") == 1024,
        "short turn did not reduce the active KV context",
    )
    require(
        FakeLlama.instances[1].kwargs.get("n_ctx") == 1024,
        "adaptive KV context was not passed to llama.cpp",
    )
    require(
        second.get("compute_profile", {}).get("architecture")
        == "sparse_mixture_of_experts",
        "Qwen3 sparse MoE compute profile was not detected",
    )
    require(
        second.get("compute_profile", {}).get("active_experts_per_token") == 8,
        "Qwen3 active expert count is missing",
    )
    require(
        status.get("dense_partial_layer_activation_claimed") is False,
        "dense partial-layer execution is being claimed",
    )
    hidden, removed = service._strip_hidden_thinking(
        "<think>private scratch</think>Final answer."
    )
    require(
        hidden == "Final answer." and removed is True,
        "closed Qwen thinking block was not removed",
    )
    truncated, removed = service._strip_hidden_thinking(
        "<think>truncated private scratch"
    )
    require(
        truncated == "" and removed is True,
        "truncated Qwen thinking block could become visible",
    )

    server_source = (TOOLS / "engel_main_server_chat_http_service.py").read_text(
        encoding="utf-8"
    )
    setup_source = (ROOT / "scripts" / "setup_engel_ct246_server_transport.sh").read_text(
        encoding="utf-8"
    )
    require(
        "def _prompt_requests_deep_local_specialist(" in server_source,
        "explicit deep-local route is missing",
    )
    require(
        '"ct_deep_local_specialist": 2' in server_source,
        "deep-local activation depth is missing",
    )
    require(
        "def _sparse_moe_local_model_receipt(" in server_source,
        "sparse MoE local route is missing",
    )
    require(
        '"ct_sparse_moe_specialist": 2' in server_source,
        "sparse MoE activation depth is missing",
    )
    require(
        "ENGEL_LOCAL_MODEL_CACHE_MAX_MODELS=1" in setup_source,
        "CT246 one-model residency policy is not deployed",
    )
    require(
        "ENGEL_MOE_REASON_AUTO_ROUTE=1" in setup_source
        and "Qwen3-30B-A3B-Q4_K_M.gguf" in setup_source,
        "CT246 sparse MoE route is not restart-persistent",
    )
    require(
        "ENGEL_LOCAL_MODEL_MIN_ACTIVE_CTX=1024" in setup_source,
        "CT246 adaptive KV context policy is not restart-persistent",
    )
    install_source = (
        ROOT / "scripts" / "install_engel_ct246_qwen3_30b_a3b_moe.sh"
    ).read_text(encoding="utf-8")
    require(
        "Qwen/Qwen3-30B-A3B-GGUF" in install_source
        and "power_vault_used" in install_source,
        "pinned CT246 SSD MoE installer is missing",
    )
    require(
        "qwen2.5-coder-3b-instruct/qwen2.5-coder-3b-instruct-q5_k_m.gguf"
        in server_source,
        "CT246 build lane is not routed to the selective 3B coder",
    )
    require(
        "ENGEL_CODE_LANE_GGUF_MODEL=/opt/engel/models-active/llm/"
        "qwen2.5-coder-3b-instruct/qwen2.5-coder-3b-instruct-q5_k_m.gguf"
        in setup_source,
        "CT246 selective coder route is not restart-persistent",
    )
    require(
        "ENGEL_BUILD_LOCAL_N_PREDICT_CAP=1800" in setup_source,
        "CT246 local coder cannot produce a bounded multi-file build",
    )
    require(
        "engel_local_model_service.py" in setup_source,
        "shared model service is not included in CT246 deployment",
    )
    print("PASS: Engel selective local model activation")
    print("active_model=Qwen3-30B-A3B-Q4_K_M.gguf")
    print("evicted_model=quick.gguf")
    print("resident_model_count=1")
    print("active_experts_per_token=8")
    print("adaptive_ctx=1024")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
