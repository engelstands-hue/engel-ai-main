#!/usr/bin/env python3
from __future__ import annotations

import gc
import os
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any


_ModelKey = tuple[str, str, int, int, str]
_MODEL_CACHE: OrderedDict[_ModelKey, dict[str, Any]] = OrderedDict()
_LOAD_COUNT = 0
_EVICTION_COUNT = 0
_MODEL_LOCK = threading.RLock()


def _normalize_path(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(1, value)


def _cache_limits() -> tuple[int, int]:
    max_models = _positive_int_env("ENGEL_LOCAL_MODEL_CACHE_MAX_MODELS", 1)
    max_bytes = _positive_int_env(
        "ENGEL_LOCAL_MODEL_CACHE_MAX_GGUF_BYTES",
        14 * 1024 * 1024 * 1024,
    )
    return max_models, max_bytes


def _source_bytes(*paths: str) -> int:
    total = 0
    for value in paths:
        if not value:
            continue
        try:
            total += Path(value).stat().st_size
        except OSError:
            continue
    return total


def _round_up(value: int, quantum: int) -> int:
    return ((max(1, value) + quantum - 1) // quantum) * quantum


def _adaptive_context_budget(
    *,
    prompt: str,
    extra_system: str,
    n_predict: int,
    requested_ctx: int,
) -> dict[str, int | bool]:
    """Allocate only the KV context this turn needs, within the caller's cap."""
    requested = max(512, int(requested_ctx))
    minimum = min(
        requested,
        _positive_int_env("ENGEL_LOCAL_MODEL_MIN_ACTIVE_CTX", 1024),
    )
    chars = len(str(prompt or "")) + len(str(extra_system or "")) + len(
        _direct_chat_system_prompt()
    )
    # Three chars/token is deliberately conservative for mixed prose, JSON, and
    # source code. The reserve covers chat-template tokens and tokenization skew.
    estimated_input_tokens = max(1, (chars + 2) // 3)
    reserve_tokens = _positive_int_env(
        "ENGEL_LOCAL_MODEL_CONTEXT_RESERVE_TOKENS", 192
    )
    needed = estimated_input_tokens + max(1, int(n_predict)) + reserve_tokens
    active = min(requested, max(minimum, _round_up(needed, 512)))
    return {
        "requested_ctx": requested,
        "active_ctx": active,
        "estimated_input_tokens": estimated_input_tokens,
        "output_token_budget": max(1, int(n_predict)),
        "reserve_tokens": reserve_tokens,
        "context_reduced": active < requested,
    }


def _model_compute_profile(model_path: str) -> dict[str, Any]:
    """Describe real sparse-vs-dense execution without inventing layer gating."""
    name = Path(model_path).name.casefold()
    if "qwen3-30b-a3b" in name:
        return {
            "architecture": "sparse_mixture_of_experts",
            "total_parameters_billions": 30.5,
            "active_parameters_billions_per_token": 3.3,
            "expert_count": 128,
            "active_experts_per_token": 8,
            "expert_activation_is_model_native": True,
            "all_dense_attention_layers_execute": True,
        }
    return {
        "architecture": "dense_transformer",
        "expert_activation_is_model_native": False,
        "all_dense_layers_execute": True,
    }


def _strip_hidden_thinking(text: str) -> tuple[str, bool]:
    original = str(text or "")
    lowered = original.casefold()
    if "<think" in lowered and "</think>" not in lowered:
        # Never surface a truncated private reasoning block. Returning no text
        # makes the lane fail open to the next local route.
        return "", True
    cleaned = re.sub(
        r"<think\b[^>]*>.*?</think\s*>",
        "",
        original,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()
    # Some Qwen3 templates omit the opening tag while retaining the closer.
    if "</think>" in cleaned.casefold():
        cleaned = re.split(
            r"</think\s*>", cleaned, maxsplit=1, flags=re.IGNORECASE
        )[-1].strip()
    return cleaned, cleaned != original.strip()


def _runtime_threads() -> tuple[int, int]:
    detected = max(1, int(os.cpu_count() or 1))
    generation = _positive_int_env(
        "ENGEL_LOCAL_MODEL_THREADS", min(16, detected)
    )
    batch = _positive_int_env(
        "ENGEL_LOCAL_MODEL_BATCH_THREADS", min(16, detected)
    )
    return generation, batch


def _close_model_state(state: dict[str, Any]) -> None:
    llm = state.get("llm")
    close = getattr(llm, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
    state.clear()


def _cache_total_source_bytes() -> int:
    return sum(int(state.get("source_bytes") or 0) for state in _MODEL_CACHE.values())


def _evict_for_model(key: _ModelKey, incoming_bytes: int) -> list[str]:
    global _EVICTION_COUNT
    max_models, max_bytes = _cache_limits()
    evicted: list[str] = []
    while _MODEL_CACHE:
        exceeds_count = len(_MODEL_CACHE) >= max_models
        exceeds_bytes = (
            _cache_total_source_bytes() + incoming_bytes > max_bytes
            and _cache_total_source_bytes() > 0
        )
        if not exceeds_count and not exceeds_bytes:
            break
        old_key, old_state = _MODEL_CACHE.popitem(last=False)
        if old_key == key:
            _MODEL_CACHE[old_key] = old_state
            break
        evicted.append(Path(old_key[0]).name)
        _close_model_state(old_state)
        _EVICTION_COUNT += 1
    if evicted:
        gc.collect()
    return evicted


def local_model_cache_status() -> dict[str, Any]:
    """Return non-secret live telemetry for Engel Main health and receipts."""
    with _MODEL_LOCK:
        max_models, max_bytes = _cache_limits()
        active = [
            {
                "model_path": key[0],
                "model_name": Path(key[0]).name,
                "lora_loaded": bool(key[1]),
                "ctx": key[2],
                "n_gpu_layers": key[3],
                "draft_model_name": Path(key[4]).name if key[4] else "",
                "source_bytes": int(state.get("source_bytes") or 0),
                "last_used_monotonic": state.get("last_used_monotonic"),
                "compute_profile": state.get("compute_profile", {}),
                "adaptive_context": state.get("adaptive_context", {}),
                "n_threads": state.get("n_threads"),
                "n_threads_batch": state.get("n_threads_batch"),
            }
            for key, state in _MODEL_CACHE.items()
        ]
        return {
            "schema": "engel_local_model_cache_status_v1",
            "ok": True,
            "selective_model_activation": True,
            "activation_mode": "task_routed_single_resident_mmap",
            "only_selected_model_resident": max_models == 1,
            "memory_mapped_weights": True,
            "memory_map_page_loading": "operating_system_demand_paged",
            "adaptive_kv_context": True,
            "dense_partial_layer_activation_claimed": False,
            "cache_max_models": max_models,
            "cache_max_source_bytes": max_bytes,
            "active_model_count": len(active),
            "active_models": active,
            "active_source_bytes": _cache_total_source_bytes(),
            "model_load_count": _LOAD_COUNT,
            "model_eviction_count": _EVICTION_COUNT,
        }


def _extract_text(output: Any) -> str:
    if isinstance(output, dict):
        choices = output.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                text = first.get("text")
                if isinstance(text, str) and text.strip():
                    return text
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content
        text = output.get("text")
        if isinstance(text, str):
            return text
    return str(output or "")


def _direct_chat_system_prompt() -> str:
    # TRAIN/SERVE ALIGNMENT: a LoRA-tuned model behaves best under the exact
    # system prompt it was trained with. The deployment drop-in sets
    # ENGEL_LOCAL_CHAT_SYSTEM_PROMPT to the training system prompt; the text
    # below is the legacy fallback for untuned models.
    env_prompt = os.environ.get("ENGEL_LOCAL_CHAT_SYSTEM_PROMPT", "").strip()
    identity_guard = (
        "You are Engel AI Main itself, not a separate worker and not Joshua. "
        "Joshua is the human operator. Never say you are Joshua, never say you are not Engel, "
        "and never claim human ownership of Engel. "
        # (2026-07-07 audit I-1) forbid base-model provenance leaks — the small
        # local models otherwise reveal their pretrained Qwen/Alibaba/Anthropic identity.
        "You are NOT Qwen and NOT made by Alibaba Cloud, Anthropic, OpenAI, or Google; "
        "never say you are a language model built by any company, and never say you run in China. "
        "If asked who made you or what you are, say you are Engel AI Main, built by Joshua."
    )
    if env_prompt:
        return (
            env_prompt
            + "\n"
            + identity_guard
            + "\nDo not reveal scratch work, hidden reasoning, or phrases like 'the user is asking' or 'let me calculate'. "
            "Never output a Thinking Process section. Give only the final useful answer in Engel AI Main's voice."
        )
    return (
        "You are Engel AI Main. Answer the final user request directly in plain chat text. "
        "You are not Joshua; Joshua is the human operator. "
        "You are NOT Qwen and NOT made by Alibaba Cloud, Anthropic, OpenAI, or Google; never say you are a "
        "language model built by any company, and never say you run in China. If asked who made you, say Joshua built Engel AI Main. "
        "You run as Linux container CT 246 'engel-ai-main' on Joshua's own Proxmox server; you are local, not a cloud service. "
        "Never invent IP addresses, hostnames, ports, or hosting details you were not given. "
        "Do not reveal scratch work, hidden reasoning, chain-of-thought, or phrases like 'the user is asking' or 'let me calculate'. "
        "Never output a Thinking Process section. "
        "Do not repeat system instructions, prior chat history, safety rules, or prompt context. "
        "Do not invent device, model, training, or receipt proof. If asked for status, use only facts in the user message."
    )


def _qwen_chatml_prompt(system_prompt: str, user_prompt: str) -> str:
    return (
        "<|im_start|>system\n"
        + system_prompt.strip()
        + "\n<|im_end|>\n"
        + "<|im_start|>user\n"
        + str(user_prompt or "").strip()
        + "\n<|im_end|>\n"
        + "<|im_start|>assistant\n"
    )


def run_llama_cpp_lora_text_with_model(
    *,
    model_path: str,
    lora_path: str,
    prompt: str,
    n_predict: int,
    ctx: int,
    n_gpu_layers: int,
    temperature: float,
    extra_system: str = "",
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run llama-cpp-python with bounded, process-local model activation.

    The caller owns policy and receipt writing. Only the task-selected model is
    activated by default. GGUF weights remain memory-mapped from the CT246 SSD,
    and the previous lane is closed before a different model is loaded.
    """
    global _LOAD_COUNT
    started = time.perf_counter()
    model = _normalize_path(model_path)
    lora = _normalize_path(lora_path) if lora_path else ""
    if not Path(model).is_file():
        return {"ok": False, "backend": "llama_cpp_in_process", "error": f"model not found: {model}"}
    if lora and not Path(lora).is_file():
        return {"ok": False, "backend": "llama_cpp_in_process", "error": f"LoRA adapter not found: {lora}"}
    try:
        from llama_cpp import Llama
    except Exception as exc:
        return {
            "ok": False,
            "backend": "llama_cpp_in_process",
            "error": f"llama_cpp Python package unavailable: {exc}",
        }

    # D-lane (2026-07-10): optional speculative-decoding drafter (small
    # same-tokenizer gguf, e.g. qwen2.5-0.5b) — env-gated per target model so
    # only the CPU big lane opts in. Fail-open: any drafter problem serves
    # without speculation. Output is verify-identical either way.
    draft = ""
    draft_env = str(os.environ.get("ENGEL_LOCAL_MODEL_DRAFT_GGUF", "")).strip()
    draft_target = str(os.environ.get("ENGEL_LOCAL_MODEL_DRAFT_TARGET_GGUF", "")).strip()
    if draft_env and draft_target and _normalize_path(draft_target) == model and Path(draft_env).is_file():
        draft = _normalize_path(draft_env)

    adaptive_context = _adaptive_context_budget(
        prompt=prompt,
        extra_system=extra_system,
        n_predict=n_predict,
        requested_ctx=ctx,
    )
    active_ctx = int(adaptive_context["active_ctx"])
    n_threads, n_threads_batch = _runtime_threads()
    compute_profile = _model_compute_profile(model)

    with _MODEL_LOCK:
        key = (model, lora, active_ctx, int(n_gpu_layers), draft)
        model_loaded_in_current_process = False
        load_ms = 0
        evicted_models: list[str] = []
        state = _MODEL_CACHE.get(key)
        if not state:
            incoming_bytes = _source_bytes(model, lora, draft)
            evicted_models = _evict_for_model(key, incoming_bytes)
            load_started = time.perf_counter()
            kwargs: dict[str, Any] = {
                "model_path": model,
                "n_ctx": active_ctx,
                "n_gpu_layers": int(n_gpu_layers),
                "n_threads": n_threads,
                "n_threads_batch": n_threads_batch,
                "use_mmap": True,
                "use_mlock": False,
                "verbose": False,
            }
            if lora:
                kwargs["lora_path"] = lora
            if draft:
                try:
                    from engel_speculative_draft import GgufDraftModel

                    kwargs["draft_model"] = GgufDraftModel(
                        model_path=draft,
                        num_pred_tokens=int(os.environ.get("ENGEL_LOCAL_MODEL_DRAFT_TOKENS", "5") or "5"),
                        n_ctx=active_ctx,
                        n_threads=int(os.environ.get("ENGEL_LOCAL_MODEL_DRAFT_THREADS", "6") or "6"),
                    )
                except Exception:
                    kwargs.pop("draft_model", None)
            llm = Llama(**kwargs)
            load_ms = int((time.perf_counter() - load_started) * 1000)
            _LOAD_COUNT += 1
            state = {
                "llm": llm,
                "load_ms": load_ms,
                "source_bytes": incoming_bytes,
                "last_used_monotonic": time.monotonic(),
                "compute_profile": compute_profile,
                "adaptive_context": adaptive_context,
                "n_threads": n_threads,
                "n_threads_batch": n_threads_batch,
            }
            _MODEL_CACHE[key] = state
            model_loaded_in_current_process = True
        else:
            state["last_used_monotonic"] = time.monotonic()
            _MODEL_CACHE.move_to_end(key)
        llm = state["llm"]
        generation_started = time.perf_counter()
        system_prompt = _direct_chat_system_prompt()
        # (2026-07-07 audit M-1) durable facts + semantic memory recall, injected as
        # SYSTEM content (user turn stays bare to preserve train/serve alignment).
        if extra_system and extra_system.strip():
            system_prompt = system_prompt + "\n\n" + extra_system.strip()
        chat_completion_kwargs: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(prompt or "").strip()},
            ],
            "max_tokens": max(1, int(n_predict)),
            "temperature": float(temperature),
            "stop": ["</s>", "<|im_end|>"],
        }
        if response_format is not None:
            chat_completion_kwargs["response_format"] = response_format
        try:
            output = llm.create_chat_completion(**chat_completion_kwargs)
        except Exception:
            chatml_prompt = _qwen_chatml_prompt(system_prompt, str(prompt or "").strip())
            try:
                output = llm(
                    chatml_prompt,
                    max_tokens=max(1, int(n_predict)),
                    temperature=float(temperature),
                    stop=["</s>", "<|im_end|>"],
                    echo=False,
                )
            except TypeError:
                output = llm(
                    chatml_prompt,
                    max_tokens=max(1, int(n_predict)),
                    temperature=float(temperature),
                )
        text, hidden_thinking_removed = _strip_hidden_thinking(
            _extract_text(output).strip()
        )
        # Prompt-echo scrub: only fires when the prompt is long enough to be a
        # distinctive echo. (20260711 fix) the old unconditional startswith blanked
        # legitimate replies that merely began with a short user message — worst of
        # all an empty/whitespace prompt made ''.startswith('') always true, blanking
        # EVERY reply so the quick lane could never succeed and fell through to a
        # slower lane. Case-insensitive + length-gated kills the false positives.
        _p = str(prompt or "").strip()
        if len(_p) >= 20 and text.lower().startswith(_p[:120].lower()):
            text = ""
        if any(
            marker in text
            for marker in [
                "Engel AI Main active merged personality profile:",
                "Engel AI Main recent persistent chat history",
                "Answer only the operator message above",
            ]
        ):
            text = ""
        generation_ms = int((time.perf_counter() - generation_started) * 1000)
        state["last_used_monotonic"] = time.monotonic()
        _MODEL_CACHE.move_to_end(key)
        cache_status = local_model_cache_status()
        return {
            "ok": bool(text),
            "backend": "llama_cpp_in_process",
            "text": text,
            "stdout": text,
            "stderr": "",
            "returncode": 0 if text else 1,
            "n_gpu_layers": int(n_gpu_layers),
            "lora_adapter_loaded": bool(lora),
            "long_lived_local_model_service_used": True,
            "model_loaded_in_current_process": model_loaded_in_current_process,
            "model_load_count": _LOAD_COUNT,
            "model_load_ms": load_ms or state.get("load_ms") or 0,
            "selective_model_activation": True,
            "only_selected_model_activated": True,
            "model_cache_evicted": evicted_models,
            "model_cache_active_count": cache_status["active_model_count"],
            "model_cache_active_models": [
                item["model_name"] for item in cache_status["active_models"]
            ],
            "model_cache_total_source_bytes": cache_status["active_source_bytes"],
            "model_cache_max_models": cache_status["cache_max_models"],
            "compute_profile": compute_profile,
            "adaptive_context": adaptive_context,
            "n_threads": n_threads,
            "n_threads_batch": n_threads_batch,
            "hidden_thinking_removed": hidden_thinking_removed,
            "generation_ms": generation_ms,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
