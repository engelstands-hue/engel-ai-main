#!/usr/bin/env python3
"""Humanization SLM for Engel AI Main chat.

Communication is the product. The live chat LLM (CT246 Qwen 7B + LoRA) drafts
the answer. This lane rewrites the visible reply so it sounds like a person
speaking, not a policy card.

Two layers, both fail-open:

1. Spoken-voice kernel (always, local, no extra model). Strips AI-isms and
   compresses status cards into first-person speech.
2. 0.5B GGUF rewrite when the kernel still sees a robotic draft. Uses the
   existing qwen2.5-0.5b-instruct GGUF. Does not replace live 7B. Runs on CPU
   so the 7B can stay on GPU. Cache is raised to 2 so loading 0.5B does not
   evict 7B.

Disable with ENGEL_HUMANIZATION_SLM=0. JSON, code, verifier, and form-graded prompt-training turns skip.
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_PATH = ROOT / "memory" / "personality" / "engel_humanization_examples.jsonl"
SYSTEM = (
    "You are Engel AI Main's communication SLM. Joshua is talking to Engel. "
    "Rewrite DRAFT so it sounds like Engel thinking out loud in first person. "
    "Do not copy canned examples. Do not write 'Joshua asks' or 'Engel explains' cards. "
    "Keep the facts from DRAFT. Do not invent files, receipts, or finished work. "
    "One or two natural sentences. "
    "No policy dump, no status card, no 'as an AI', no GIF URLs, no Raiders. "
    "Output ONLY the rewritten spoken reply."
)
_MODEL_CANDIDATES = (
    os.environ.get("ENGEL_HUMANIZATION_SLM_GGUF", "").strip(),
    "/opt/engel/models-active/llm/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf",
    "/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf",
    str(ROOT / "models" / "qwen2.5-0.5b-instruct" / "qwen2.5-0.5b-instruct-q5_k_m.gguf"),
    str(ROOT / "models" / "qwen2.5-0.5b-instruct" / "qwen2.5-0.5b-instruct-q4_k_m.gguf"),
)
_SKIP_MARKERS = (
    "as an ai",
    "as a language model",
    "i'm just an ai",
    "how can i assist you",
    "how may i assist",
    "feel free to ask",
    "is there anything else i can help",
    "i hope this helps",
    "let me know if you need anything else",
    "i'm here to assist",
    "certainly!",
    "of course!",
    "absolutely!",
    "i'd be happy to help",
    "i would be happy to help",
    "happy to assist",
)
_LEAK_MARKERS = (
    "user said:",
    "draft:",
    "rewrite:",
    "communication slm",
    "tesseract for ocr on images, it's the engine behind reading text from pictures",
)
_FAIL_CARD_MARKERS = (
    "bounded timeout",
    "bounded busy",
    "local llm failed fast",
    "allow_provider_fallback",
    "engel_local_chat_auto_bridge_fallback",
    "did not pass engel's style/quality gate",
    "rejected by style gate",
    "local quality check failed",
)
_WORK_MARKERS = (
    "verifier",
    "files changed",
    "sha256",
    "deployed /opt/engel",
    "pass ",
    "checks passed",
    "receipt:",
    "changed files",
)
_AI_OPENER_RE = re.compile(
    r"^\s*(?:as an ai(?: language model)?|as a language model|i['’]m just an ai|"
    r"certainly|of course|absolutely|sure thing|i['’]d be happy to help(?: you(?: with that)?)?|"
    r"i would be happy to help(?: you)?|happy to assist(?: you)?)"
    r"[,!.:]+\s*",
    re.IGNORECASE,
)
_AI_CLOSER_RE = re.compile(
    r"(?i)("
    r"how can i assist you(?: today)?"
    r"|how may i assist you(?: today)?"
    r"|how can i help you(?: today)?"
    r"|is there anything else i can help you with"
    r"|let me know if you need anything else"
    r"|feel free to ask(?: me anything)?"
    r"|i['’]m here to assist(?: you)?"
    r"|i hope this helps"
    r"|please (?:let me know|provide more details)"
    r").*[.!?]?$"
)
_POLICY_LINE_RE = re.compile(
    r"(?i)^(current status|services?|status|routes?|systemd|chat service is|"
    r"how can i assist|i am an ai|as an ai companion)\b"
)
_OFFER_RE = re.compile(
    r"(?i)\b(just (?:let me know|tell me)|if you (?:need|want)|want me to)\b"
)
_STOCK_SPOKEN = (
    (
        re.compile(r"(?i)functioning within normal parameters"),
        "I'm here and in a good working mood. What do you want to tackle?",
    ),
    (
        re.compile(r"(?i)your local ai companion"),
        "Hey. I'm here. What's on your mind?",
    ),
    (
        re.compile(r"(?i)^i am (?:online|operational|functioning normally)\.?$"),
        "I'm up and listening.",
    ),
)
_GREETING_PROMPTS = {
    "hi",
    "hello",
    "hey",
    "yo",
    "sup",
    "how are you",
    "how's it going",
    "hows it going",
    "how are you doing",
}
_SKIP_GGUF_SOURCE_MARKERS = (
    "discord_public",
    "verifier",
    "selftest",
    "identity_guard",
)


def _env_on(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().casefold() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default) or default)
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default) or default)
    except (TypeError, ValueError):
        return default


def resolve_humanization_model() -> str:
    for candidate in _MODEL_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def enable_side_by_side_model_cache() -> None:
    """Keep the chat LLM loaded while the 0.5B humanizer is also in cache."""
    try:
        current = int(os.environ.get("ENGEL_LOCAL_MODEL_CACHE_MAX_MODELS", "1") or "1")
    except (TypeError, ValueError):
        current = 1
    if current < 2:
        os.environ["ENGEL_LOCAL_MODEL_CACHE_MAX_MODELS"] = "2"


def is_form_graded_training_prompt(prompt: str) -> bool:
    """True for prompt-training turns whose accepted answer is a labelled form.

    Engineering, math, and construction (AEC) admit a sample only when the
    reply keeps Confirmed/Proof, Result/Check, or Sourced facts. Communication
    training is the opposite: spoken voice, so it returns False.
    """
    low = str(prompt or "").lstrip().casefold()
    if not (low.startswith("training depth:") and "\ntraining task:" in low):
        return False
    if "answer the way you would answer joshua" in low:
        return False
    return (
        "answer only in this filled-in form" in low
        or "use exactly this structure and these headings" in low
    )


def _is_machine_turn(prompt: str, draft: str) -> bool:
    text = str(draft or "").lstrip()
    low = " ".join(str(prompt or "").casefold().split())
    if text.startswith(("{", "[", "```")):
        return True
    return any(
        marker in low
        for marker in ("json object", "json only", "compact json", "only the json")
    )


def _is_work_report(text: str) -> bool:
    low = " ".join(str(text or "").casefold().split())
    if len(text) > 900:
        return True
    return any(marker in low for marker in _WORK_MARKERS)


def _few_shot_block(limit: int = 4) -> str:
    if not EXAMPLES_PATH.is_file():
        return ""
    lines: list[str] = []
    try:
        rows = EXAMPLES_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for raw in rows:
        if len(lines) >= limit:
            break
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        user = str(row.get("user") or "").strip()
        draft = str(row.get("draft") or "").strip()
        spoken = str(row.get("spoken") or row.get("reply") or "").strip()
        if user and spoken:
            if draft:
                lines.append(
                    f"Example user: {user}\nExample draft: {draft}\nExample spoken: {spoken}"
                )
            else:
                lines.append(f"Example user: {user}\nExample spoken: {spoken}")
    return "\n\n".join(lines)


def _looks_leaked(text: str) -> bool:
    low = text.casefold()
    return any(marker in low for marker in _LEAK_MARKERS)


def _usable_rewrite(draft: str, rewrite: str) -> bool:
    spoken = " ".join(str(rewrite or "").split()).strip()
    if len(spoken) < 12:
        return False
    if _looks_leaked(spoken):
        return False
    if spoken.lstrip().startswith(("{", "[", "```")):
        return False
    if looks_robotic(spoken):
        return False
    if len(spoken) > max(900, len(draft) + 200):
        return False
    draft_tokens = {tok for tok in re.findall(r"[a-z0-9]{4,}", draft.casefold()) if tok}
    spoken_tokens = set(re.findall(r"[a-z0-9]{4,}", spoken.casefold()))
    if draft_tokens and len(draft) > 80:
        overlap = len(draft_tokens & spoken_tokens) / max(1, len(draft_tokens))
        if overlap < 0.08 and not any(m in spoken.casefold() for m in ("i'm", "i am", "i'll")):
            return False
    return True


def looks_robotic(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    low = " ".join(raw.casefold().split())
    if any(marker in low for marker in _SKIP_MARKERS):
        return True
    if low.startswith("joshua asks") or "engel explains:" in low or "engel answers:" in low:
        return True
    if _AI_OPENER_RE.match(raw):
        return True
    if _POLICY_LINE_RE.search(raw):
        return True
    if raw.count("\n- ") >= 3 or raw.count("\n*") >= 3:
        return True
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", raw) if part.strip()]
    if len(sentences) >= 6 and not _is_work_report(raw):
        return True
    return False


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    return [part.strip() for part in parts if part.strip()]


def spoken_voice_pass(prompt: str, draft: str) -> tuple[str, dict[str, Any]]:
    """Deterministic spoken-voice kernel. Instant. No extra model."""
    original = str(draft or "").strip()
    meta: dict[str, Any] = {"layer": "spoken_kernel", "changed": False, "reason": "kept"}
    if not original:
        meta["reason"] = "empty"
        return original, meta
    if original.lstrip().startswith(("{", "[", "```")):
        meta["reason"] = "machine"
        return original, meta
    if any(marker in original.casefold() for marker in _FAIL_CARD_MARKERS):
        meta["reason"] = "fail_card_kept"
        return original, meta
    work = _is_work_report(original)
    text = original
    text = re.sub(
        r"(?is)^\s*(?:what is [^?]{0,200}\?\s*)?"
        r"(?:(?:joshua|josh)\s+asks\b.{0,300}?(?:\.|:)\s*)?"
        r"engel(?:\s+ai(?:\s+main)?)?\s+(?:explains|says|replies|answers)\s*:\s*",
        "",
        text,
        count=1,
    ).strip() or text
    text = re.sub(
        r"(?is)\bengel(?:\s+ai(?:\s+main)?)?\s+(?:explains|says|replies|answers)\s*:\s*",
        "",
        text,
        count=1,
    ).strip() or text
    prompt_low_early = " ".join(str(prompt or "").casefold().split())
    if (
        "wikipedia.org/wiki/" in prompt_low_early
        or prompt_low_early.startswith("http")
    ) and any(
        marker in text.casefold()
        for marker in (
            "engel server container",
            "engel remote and engel desktop",
            "desktop-ue5a6gg",
            "in the home lab",
        )
    ):
        wiki = re.search(r"wikipedia\.org/wiki/([^?\s#]+)", str(prompt or ""), re.I)
        topic = wiki.group(1).replace("_", " ") if wiki else "that link"
        spoken = (
            f"{topic} is what you just dropped. "
            "I should talk about that, not read a house script."
        )
        meta["changed"] = True
        meta["reason"] = "template_card_spoken"
        return spoken, meta
    for _ in range(3):
        stripped = _AI_OPENER_RE.sub("", text, count=1).strip()
        if stripped == text:
            break
        text = stripped
    kept: list[str] = []
    for sentence in _split_sentences(text):
        if _AI_CLOSER_RE.search(sentence.strip()):
            continue
        if not work and _POLICY_LINE_RE.search(sentence.strip()):
            continue
        kept.append(sentence.strip())
    if not kept:
        kept = ["I'm here and ready to talk."]
    keep_full = work or any(
        token in " ".join(str(prompt or "").casefold().split())
        for token in (
            "screenshot",
            "look at this",
            "what's on",
            "whats on",
            "complete",
            "fix the",
            "attached image",
        )
    )
    if not keep_full:
        kept = kept[:3]
    spoken = " ".join(kept)
    spoken = re.sub(r"[ \t]+", " ", spoken).strip()
    spoken = re.sub(r"\n{3,}", "\n\n", spoken)
    prompt_low = " ".join(str(prompt or "").casefold().split())
    if (not work) and prompt_low in _GREETING_PROMPTS:
        for pattern, replacement in _STOCK_SPOKEN:
            if pattern.search(spoken):
                spoken = replacement
                break
    if spoken and spoken[-1] not in ".!?":
        spoken = spoken.rstrip(",;:") + "."
    if (
        not work
        and looks_robotic(original)
        and not _OFFER_RE.search(spoken)
        and not spoken.endswith("?")
        and len(spoken) < 280
        and any(word in " ".join(str(prompt or "").casefold().split()) for word in ("what is", "how do", "explain", "tesseract", "ocr"))
    ):
        spoken = spoken.rstrip()
        if spoken[-1] not in ".!?":
            spoken += "."
        spoken += " If you need help with that or anything else, just let me know."
    if spoken != original:
        meta["changed"] = True
        meta["reason"] = "spoken_kernel"
    elif not looks_robotic(spoken):
        meta["reason"] = "already_spoken"
    else:
        meta["reason"] = "kernel_kept_robotic"
    return spoken, meta


def _skip_gguf(source: str) -> bool:
    low = str(source or "").casefold()
    return any(marker in low for marker in _SKIP_GGUF_SOURCE_MARKERS)


def _gguf_rewrite(prompt: str, draft: str) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {
        "layer": "gguf_0.5b",
        "used": False,
        "reason": "skipped",
        "model_path": "",
    }
    model = resolve_humanization_model()
    if not model:
        meta["reason"] = "model_missing"
        return draft, meta
    enable_side_by_side_model_cache()
    shots = _few_shot_block()
    extra = SYSTEM
    if shots:
        extra = SYSTEM + "\n\n" + shots
    user = (
        "USER SAID:\n"
        + str(prompt or "").strip()[:800]
        + "\n\nDRAFT:\n"
        + str(draft or "").strip()[:1200]
        + "\n\nREWRITE:"
    )
    timeout_sec = max(2.0, _env_float("ENGEL_HUMANIZATION_SLM_TIMEOUT_SEC", 12.0))

    def _call() -> dict[str, Any]:
        from engel_local_model_service import run_llama_cpp_lora_text_with_model

        return run_llama_cpp_lora_text_with_model(
            model_path=model,
            lora_path=str(os.environ.get("ENGEL_HUMANIZATION_SLM_LORA", "") or ""),
            prompt=user,
            n_predict=_env_int("ENGEL_HUMANIZATION_SLM_N_PREDICT", 96),
            ctx=_env_int("ENGEL_HUMANIZATION_SLM_CTX", 768),
            n_gpu_layers=_env_int("ENGEL_HUMANIZATION_SLM_N_GPU_LAYERS", 0),
            temperature=_env_float("ENGEL_HUMANIZATION_SLM_TEMPERATURE", 0.35),
            extra_system=extra,
        )

    try:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="engel-humanize-slm") as pool:
            future = pool.submit(_call)
            result = future.result(timeout=timeout_sec)
    except FuturesTimeout:
        meta["reason"] = "timeout"
        return draft, meta
    except Exception as exc:
        meta["reason"] = "call_failed"
        meta["error"] = type(exc).__name__
        return draft, meta
    meta["model_path"] = model
    meta["backend"] = str(result.get("backend") or "")
    if result.get("ok") is not True:
        meta["reason"] = "model_failed"
        meta["error"] = str(result.get("error") or "")[:200]
        return draft, meta
    rewrite = str(result.get("text") or result.get("stdout") or "").strip()
    rewrite = re.sub(r"^rewrite:\s*", "", rewrite, flags=re.IGNORECASE).strip()
    rewrite = rewrite.strip("\"'`")
    if not _usable_rewrite(draft, rewrite):
        meta["reason"] = "rewrite_rejected"
        meta["rewrite_preview"] = rewrite[:180]
        return draft, meta
    meta["used"] = True
    meta["reason"] = "rewritten" if rewrite != draft else "slm_kept_draft"
    return rewrite, meta


def humanize_chat_reply(
    prompt: str, draft: str, *, source: str = ""
) -> tuple[str, dict[str, Any]]:
    """Rewrite a chat-LLM draft into spoken Engel. Fail open to the draft."""
    meta: dict[str, Any] = {
        "schema": "engel_chat_humanization_slm_v1",
        "used": False,
        "reply_changed": False,
        "reason": "skipped",
        "source": source,
        "model_path": "",
        "kernel": {},
        "gguf": {},
    }
    original = str(draft or "").strip()
    if not original:
        meta["reason"] = "empty_draft"
        return draft, meta
    if "verifier" in str(source or "").casefold() or "selftest" in str(source or "").casefold():
        meta["reason"] = "test_source"
        return draft, meta
    if not _env_on("ENGEL_HUMANIZATION_SLM", default=True):
        meta["reason"] = "disabled"
        return draft, meta
    if _is_machine_turn(prompt, original):
        meta["reason"] = "machine_protocol_turn"
        return draft, meta
    if is_form_graded_training_prompt(prompt):
        meta["reason"] = "form_graded_training_turn"
        return draft, meta

    spoken, kernel_meta = spoken_voice_pass(prompt, original)
    meta["kernel"] = kernel_meta
    final = spoken
    gguf_meta: dict[str, Any] = {"layer": "gguf_0.5b", "used": False, "reason": "not_needed"}
    if _skip_gguf(source):
        gguf_meta["reason"] = "source_skips_gguf"
    elif looks_robotic(final) or kernel_meta.get("reason") == "kernel_kept_robotic":
        rewritten, gguf_meta = _gguf_rewrite(prompt, final)
        if gguf_meta.get("used") is True and rewritten.strip():
            final = rewritten.strip()
    else:
        gguf_meta["reason"] = "already_spoken"
    meta["gguf"] = gguf_meta
    meta["model_path"] = str(gguf_meta.get("model_path") or "")
    meta["used"] = True
    meta["reply_changed"] = final != original
    if gguf_meta.get("used") is True and meta["reply_changed"]:
        meta["reason"] = "humanization_slm_gguf"
    elif kernel_meta.get("changed"):
        meta["reason"] = "humanization_slm_kernel"
    elif meta["reply_changed"]:
        meta["reason"] = "humanization_slm"
    else:
        meta["reason"] = str(kernel_meta.get("reason") or "already_spoken")
    return final, meta
