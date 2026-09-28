"""Engel speech bridge — STT (faster-whisper) + TTS (piper-tts) + a small
model picker for managing the local speech-model library.

Chat commands:

  models                       — list installed and available models
  models install <name>        — download a model
  models remove <name>         — delete a model from disk
  stt status                   — what STT model is loaded, if any
  stt use <name>               — pick the active Whisper model
  stt transcribe <wav-path>    — transcribe a WAV file
  tts status                   — what voice is loaded
  tts use <voice>              — pick the active Piper voice
  say <text>                   — speak text out through the default audio device
  voice on                     — start full hold-to-talk voice conversation
                                 (records 5s, transcribes, chats, speaks reply)
  voice off                    — stop voice mode

Models live under <engel-root>/models/speech/{whisper,piper}/.
First-time install pulls from Hugging Face (faster-whisper) or rhasspy/piper
GitHub releases (piper voices).
"""
from __future__ import annotations

import json
import os
import threading
import time
import wave
from pathlib import Path
from typing import Any

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
SPEECH_ROOT = ROOT / "models" / "speech"
WHISPER_DIR = SPEECH_ROOT / "whisper"
PIPER_DIR = SPEECH_ROOT / "piper"

_LOCK = threading.Lock()
_STATE: dict = {
    "stt_model_name": "",   # e.g. "base"
    "stt_model": None,      # loaded faster_whisper.WhisperModel
    "tts_voice": "",        # e.g. "en_US-amy-medium"
    "tts_piper": None,      # loaded piper.PiperVoice
    "voice_mode": False,
    "last_error": "",
}

# Whisper model registry. faster-whisper downloads from HF on first load.
# Sizes are approximate on-disk after download.
WHISPER_REGISTRY = {
    "tiny":   {"size_mb": 75,   "desc": "fastest, lowest quality"},
    "base":   {"size_mb": 145,  "desc": "good balance"},
    "small":  {"size_mb": 480,  "desc": "better quality"},
    "medium": {"size_mb": 1500, "desc": "high quality, slow on CPU"},
    "large-v3": {"size_mb": 3100, "desc": "best quality, GPU recommended"},
}

# Piper voice registry. Each voice = .onnx + .onnx.json from rhasspy/piper.
PIPER_REGISTRY = {
    "en_US-amy-medium":    {"size_mb": 64,  "desc": "female, US English, medium"},
    "en_US-lessac-medium": {"size_mb": 64,  "desc": "male, US English, medium"},
    "en_US-ryan-high":     {"size_mb": 110, "desc": "male, US English, high quality"},
    "en_GB-alan-medium":   {"size_mb": 64,  "desc": "male, UK English, medium"},
}

PIPER_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def _ensure_dirs() -> None:
    SPEECH_ROOT.mkdir(parents=True, exist_ok=True)
    WHISPER_DIR.mkdir(parents=True, exist_ok=True)
    PIPER_DIR.mkdir(parents=True, exist_ok=True)


def _have(mod: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(mod) is not None


# ─── status & listings ────────────────────────────────────────────────────

def models_list() -> str:
    _ensure_dirs()
    lines = ["# Speech Model Library", ""]

    lines.append("## Whisper (STT)")
    lines.append(f"Backend: {'faster-whisper installed' if _have('faster_whisper') else 'NOT installed (pip install faster-whisper)'}")
    lines.append("")
    lines.append("Installed:")
    installed_whisper = _installed_whisper_models()
    if installed_whisper:
        for name in installed_whisper:
            lines.append(f"  ✓ {name}")
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("Available:")
    for name, meta in WHISPER_REGISTRY.items():
        marker = "✓" if name in installed_whisper else "·"
        lines.append(f"  {marker} {name:10s}  ~{meta['size_mb']:4d} MB   {meta['desc']}")
    lines.append("")

    lines.append("## Piper (TTS)")
    lines.append(f"Backend: {'piper-tts installed' if _have('piper') else 'NOT installed (pip install piper-tts)'}")
    lines.append("")
    lines.append("Installed:")
    installed_piper = _installed_piper_voices()
    if installed_piper:
        for name in installed_piper:
            lines.append(f"  ✓ {name}")
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("Available:")
    for name, meta in PIPER_REGISTRY.items():
        marker = "✓" if name in installed_piper else "·"
        lines.append(f"  {marker} {name:24s}  ~{meta['size_mb']:3d} MB   {meta['desc']}")
    lines += [
        "",
        "Install:  models install whisper:<name>    e.g.  models install whisper:base",
        "          models install piper:<name>      e.g.  models install piper:en_US-amy-medium",
        "Remove:   models remove whisper:<name>     or    models remove piper:<voice>",
    ]
    return "\n".join(lines)


def _installed_whisper_models() -> list[str]:
    _ensure_dirs()
    # faster-whisper stores models under HF cache by default; we use a local
    # download_root so installs land here. Detect by directory presence.
    out: list[str] = []
    for child in WHISPER_DIR.iterdir() if WHISPER_DIR.exists() else []:
        if child.is_dir():
            # HF cache layout: "models--Systran--faster-whisper-<name>"
            if "faster-whisper-" in child.name:
                name = child.name.split("faster-whisper-")[-1]
                out.append(name)
            else:
                # Or a plain <name>/ dir we wrote ourselves.
                out.append(child.name)
    return sorted(set(out))


def _installed_piper_voices() -> list[str]:
    _ensure_dirs()
    voices = []
    for onnx in PIPER_DIR.glob("*.onnx"):
        if onnx.with_suffix(".onnx.json").exists():
            voices.append(onnx.stem)
    return sorted(voices)


# ─── install / remove ────────────────────────────────────────────────────

def models_install(spec: str) -> str:
    spec = spec.strip()
    if ":" not in spec:
        return "Usage: models install whisper:<name> or models install piper:<voice>"
    kind, _, name = spec.partition(":")
    kind = kind.strip().lower()
    name = name.strip()
    if kind == "whisper":
        return _install_whisper(name)
    if kind == "piper":
        return _install_piper(name)
    return f"Unknown model kind '{kind}'. Use whisper or piper."


def _install_whisper(name: str) -> str:
    if name not in WHISPER_REGISTRY:
        return f"Unknown whisper model '{name}'. Available: {', '.join(WHISPER_REGISTRY)}"
    if not _have("faster_whisper"):
        return "faster-whisper not installed. Run: pip install faster-whisper"
    _ensure_dirs()
    try:
        from faster_whisper import WhisperModel
        # Constructing a WhisperModel downloads weights into download_root.
        WhisperModel(name, device="cpu", compute_type="int8", download_root=str(WHISPER_DIR))
    except Exception as exc:
        return f"Whisper '{name}' install failed: {exc}"
    return f"Whisper '{name}' installed under {WHISPER_DIR}"


def _install_piper(voice: str) -> str:
    if voice not in PIPER_REGISTRY:
        return f"Unknown piper voice '{voice}'. Available: {', '.join(PIPER_REGISTRY)}"
    try:
        import requests
    except ImportError:
        return "requests not installed. Run: pip install requests"
    _ensure_dirs()
    # Voice URLs: <base>/<lang>/<region>/<voice-name>/<quality>/<voice>.onnx
    # e.g. en/en_US/amy/medium/en_US-amy-medium.onnx
    lang, region, name_quality = _parse_piper_voice(voice)
    base = f"{PIPER_BASE_URL}/{lang}/{region}/{name_quality['name']}/{name_quality['quality']}"
    files = {
        f"{voice}.onnx":      f"{base}/{voice}.onnx",
        f"{voice}.onnx.json": f"{base}/{voice}.onnx.json",
    }
    for fname, url in files.items():
        out = PIPER_DIR / fname
        if out.exists():
            continue
        try:
            r = requests.get(url, stream=True, timeout=120)
            if r.status_code != 200:
                return f"Download failed ({r.status_code}): {url}"
            with out.open("wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        except Exception as exc:
            return f"Download of {fname} failed: {exc}"
    return f"Piper voice '{voice}' installed under {PIPER_DIR}"


def _parse_piper_voice(voice: str) -> tuple[str, str, dict]:
    # voice = "en_US-amy-medium" → lang "en", region "en_US", name "amy", quality "medium"
    parts = voice.split("-")
    region = parts[0]                         # "en_US"
    lang = region.split("_")[0]               # "en"
    quality = parts[-1]                       # "medium"
    name = "-".join(parts[1:-1])              # "amy"
    return lang, region, {"name": name, "quality": quality}


def models_remove(spec: str) -> str:
    spec = spec.strip()
    if ":" not in spec:
        return "Usage: models remove whisper:<name> or models remove piper:<voice>"
    kind, _, name = spec.partition(":")
    kind = kind.strip().lower()
    name = name.strip()
    _ensure_dirs()
    removed = 0
    if kind == "whisper":
        for d in WHISPER_DIR.iterdir():
            if name in d.name:
                _rm_tree(d)
                removed += 1
    elif kind == "piper":
        for f in PIPER_DIR.glob(f"{name}.onnx*"):
            f.unlink()
            removed += 1
    else:
        return f"Unknown kind '{kind}'"
    return f"Removed {removed} file(s) for {kind}:{name}"


def _rm_tree(path: Path) -> None:
    if path.is_file():
        path.unlink()
        return
    for child in path.iterdir():
        _rm_tree(child)
    path.rmdir()


# ─── STT ─────────────────────────────────────────────────────────────────

def stt_status() -> str:
    lines = ["# STT Status", ""]
    lines.append(f"Backend:    {'faster-whisper installed' if _have('faster_whisper') else 'NOT installed'}")
    lines.append(f"Active:     {_STATE['stt_model_name'] or '(none)'}")
    lines.append(f"Installed:  {', '.join(_installed_whisper_models()) or '(none)'}")
    if _STATE["last_error"]:
        lines.append(f"Last error: {_STATE['last_error']}")
    lines += [
        "",
        "Commands:",
        "  stt use <name>            — pick active model (must be installed)",
        "  stt transcribe <wav>      — transcribe a wav file",
    ]
    return "\n".join(lines)


def stt_use(name: str) -> str:
    name = name.strip()
    if not name:
        return "Usage: stt use <model-name>"
    if name not in _installed_whisper_models():
        return f"Model '{name}' not installed. Run: models install whisper:{name}"
    if not _have("faster_whisper"):
        return "faster-whisper not installed."
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(name, device="cpu", compute_type="int8", download_root=str(WHISPER_DIR))
    except Exception as exc:
        return f"Failed to load: {exc}"
    with _LOCK:
        _STATE["stt_model"] = model
        _STATE["stt_model_name"] = name
    return f"STT model set to '{name}'"


def stt_transcribe(wav_path: str) -> str:
    wav_path = wav_path.strip().strip('"').strip("'")
    if not wav_path:
        return "Usage: stt transcribe <wav-path>"
    p = Path(wav_path)
    if not p.exists():
        return f"File not found: {p}"
    if _STATE["stt_model"] is None:
        return "No STT model loaded. Run: stt use <name>"
    try:
        segments, info = _STATE["stt_model"].transcribe(str(p), beam_size=1)
        text_parts = [seg.text for seg in segments]
    except Exception as exc:
        _STATE["last_error"] = str(exc)
        return f"Transcribe failed: {exc}"
    return "".join(text_parts).strip() or "(empty transcription)"


def transcribe_for_companion(wav_path: str) -> str:
    """Public API used by engel_companion.py's voice-note flow.
    Auto-loads the smallest installed model if none active. Returns empty
    string if STT is unavailable or has no models installed (caller treats
    that as 'no transcription'). Returns the transcribed text on success."""
    if _STATE["stt_model"] is None:
        installed = _installed_whisper_models()
        if not installed:
            return ""
        # Pick smallest available.
        order = ["tiny", "base", "small", "medium", "large-v3"]
        for name in order:
            if name in installed:
                msg = stt_use(name)
                if "set to" not in msg:
                    return ""
                break
        else:
            stt_use(installed[0])
    return stt_transcribe(wav_path)


# ─── TTS ─────────────────────────────────────────────────────────────────

def tts_status() -> str:
    lines = ["# TTS Status", ""]
    lines.append(f"Backend:   {'piper-tts installed' if _have('piper') else 'NOT installed'}")
    lines.append(f"Active:    {_STATE['tts_voice'] or '(none)'}")
    lines.append(f"Installed: {', '.join(_installed_piper_voices()) or '(none)'}")
    lines += [
        "",
        "Commands:",
        "  tts use <voice>           — pick active voice (must be installed)",
        "  say <text>                — speak text out",
    ]
    return "\n".join(lines)


def tts_use(voice: str) -> str:
    voice = voice.strip()
    if not voice:
        return "Usage: tts use <voice>"
    onnx = PIPER_DIR / f"{voice}.onnx"
    if not onnx.exists():
        return f"Voice '{voice}' not installed. Run: models install piper:{voice}"
    if not _have("piper"):
        return "piper-tts not installed."
    try:
        from piper import PiperVoice
        piper_voice = PiperVoice.load(str(onnx))
    except Exception as exc:
        return f"Failed to load: {exc}"
    with _LOCK:
        _STATE["tts_piper"] = piper_voice
        _STATE["tts_voice"] = voice
    return f"TTS voice set to '{voice}'"


def say(text: str) -> str:
    text = text.strip()
    if not text:
        return "Usage: say <text>"
    if _STATE["tts_piper"] is None:
        # Try to auto-load the first installed voice.
        installed = _installed_piper_voices()
        if not installed:
            return "No TTS voice loaded. Run: models install piper:en_US-amy-medium  then  tts use en_US-amy-medium"
        msg = tts_use(installed[0])
        if "set to" not in msg:
            return msg
    try:
        import sounddevice as sd
        import numpy as np
        voice = _STATE["tts_piper"]
        # Piper streams int16 PCM at voice.config.sample_rate.
        chunks: list[bytes] = []
        for audio_chunk in voice.synthesize(text):
            # piper-tts 1.4 yields AudioChunk objects with .audio_int16_array
            arr = getattr(audio_chunk, "audio_int16_array", None)
            if arr is None:
                # Older API returns raw bytes.
                chunks.append(bytes(audio_chunk))
            else:
                chunks.append(arr.tobytes())
        if not chunks:
            return "TTS returned no audio."
        raw = b"".join(chunks)
        samples = np.frombuffer(raw, dtype=np.int16)
        sample_rate = getattr(voice.config, "sample_rate", 22050)
        sd.play(samples, samplerate=sample_rate)
        sd.wait()
        return f"Spoke {len(text)} chars."
    except Exception as exc:
        return f"say failed: {exc}"


# ─── Voice mode (full conversation) ──────────────────────────────────────

def voice_on() -> str:
    if _STATE["voice_mode"]:
        return "Voice mode already on."
    if not _installed_whisper_models():
        return "Install a Whisper model first. Try: models install whisper:base"
    if not _installed_piper_voices():
        return "Install a Piper voice first. Try: models install piper:en_US-amy-medium"
    with _LOCK:
        _STATE["voice_mode"] = True
    return (
        "Voice mode ON.\n"
        "Use the desktop Ctrl+Space to record a voice note — it will be\n"
        "transcribed, sent through Engel's chat pipeline, and the reply\n"
        "spoken back out loud."
    )


def voice_off() -> str:
    with _LOCK:
        _STATE["voice_mode"] = False
    return "Voice mode OFF."


def voice_mode_active() -> bool:
    return bool(_STATE["voice_mode"])


# ─── Top-level routers ───────────────────────────────────────────────────

def handle_models_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "list":
        return models_list()
    if text.startswith("install"):
        return models_install(text[7:].strip())
    if text.startswith("remove"):
        return models_remove(text[6:].strip())
    return f"Unknown models subcommand: '{text}'. Try 'models'."


def handle_stt_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return stt_status()
    if text.startswith("use"):
        return stt_use(text[3:].strip())
    if text.startswith("transcribe"):
        return stt_transcribe(text[10:].strip())
    return f"Unknown stt subcommand: '{text}'. Try 'stt status'."


def handle_tts_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return tts_status()
    if text.startswith("use"):
        return tts_use(text[3:].strip())
    return f"Unknown tts subcommand: '{text}'. Try 'tts status'."


def handle_say_command(args: str) -> str:
    return say(args or "")


def handle_voice_command(args: str) -> str:
    text = (args or "").strip().lower()
    if text == "on":
        return voice_on()
    if text == "off":
        return voice_off()
    return (
        "Voice mode: "
        + ("ON" if _STATE["voice_mode"] else "OFF")
        + "\nUse: voice on / voice off"
    )
