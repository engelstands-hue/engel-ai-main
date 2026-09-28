#!/usr/bin/env python3
"""
Engel AI Main — voice (TTS + STT), OpenClaw voice/talk port.

Ported concept from OpenClaw (MIT) voice: Talk Mode + TTS/STT. Engel had no
voice; this adds real text-to-speech via the built-in Windows Speech API (SAPI,
no extra install) — speak live or render a WAV — plus a talk-reply that speaks
Engel's failover-chat answer. STT (speech-in) runs through faster-whisper in the
isolated runtime/stt_venv. Live microphone capture is wired via sounddevice
(PortAudio) + numpy: record_mic() grabs a spoken WAV and listen_and_reply()
does the full LIVE two-way turn (mic -> STT -> failover chat -> speak).

So Engel can now both TALK and LISTEN end-to-end from the microphone.

Reimplemented natively in Python; MIT-attributed. Windows-only TTS (SAPI).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
VOICE_DIR = ROOT / "runtime" / "voice"

# SAPI SpFileStream open mode: SSFMCreateForWrite = 3
_SSFM_CREATE_FOR_WRITE = 3


def _sapi():
    import win32com.client  # pywin32; ships with the Engel python
    return win32com.client.Dispatch("SAPI.SpVoice")


def list_voices() -> list[str]:
    try:
        v = _sapi()
        return [v.GetVoices().Item(i).GetDescription() for i in range(v.GetVoices().Count)]
    except Exception as exc:
        return [f"(voice enumeration failed: {exc})"]


def _select_voice(voice_obj, name: str) -> None:
    if not name:
        return
    tokens = voice_obj.GetVoices()
    for i in range(tokens.Count):
        if name.lower() in tokens.Item(i).GetDescription().lower():
            voice_obj.Voice = tokens.Item(i)
            return


def speak(text: str, voice: str = "", rate: int = 0) -> dict:
    """Speak text live through the default audio device."""
    try:
        v = _sapi()
        _select_voice(v, voice)
        v.Rate = max(-10, min(10, rate))
        v.Speak(text)
        return {"ok": True, "spoke": len(text)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}


def synthesize_to_wav(text: str, out_path: Optional[str] = None, voice: str = "", rate: int = 0) -> dict:
    """Render text to a WAV file (no speakers needed) — testable + shareable."""
    import win32com.client
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    if not out_path:
        import time
        out_path = str(VOICE_DIR / f"tts_{int(time.time()*1000)}.wav")
    try:
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(out_path, _SSFM_CREATE_FOR_WRITE)
        v = _sapi()
        _select_voice(v, voice)
        v.Rate = max(-10, min(10, rate))
        v.AudioOutputStream = stream
        v.Speak(text)
        stream.Close()
        b = Path(out_path).stat().st_size
        return {"ok": True, "path": out_path, "bytes": b}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}


def _stt_venv_python():
    p = ROOT / "runtime" / "stt_venv" / "Scripts" / "python.exe"
    return p if p.exists() else None


def stt_available() -> bool:
    if _stt_venv_python():
        return True
    for mod in ("faster_whisper", "whisper", "speech_recognition"):
        try:
            __import__(mod)
            return True
        except Exception:
            continue
    return False


def transcribe(wav_path: str, model_size: str = "base") -> dict:
    """Speech-to-text via faster-whisper in the isolated runtime/stt_venv (kept
    out of Engel's main runtime). First call downloads the model (~150MB)."""
    import json as _json
    stt_py = _stt_venv_python()
    if stt_py:
        import subprocess
        code = (
            "import sys, json\n"
            "from faster_whisper import WhisperModel\n"
            "m = WhisperModel(sys.argv[2], device='cpu', compute_type='int8')\n"
            "segs, info = m.transcribe(sys.argv[1])\n"
            "print(json.dumps({'text': ' '.join(s.text for s in segs).strip(), 'language': info.language}))\n"
        )
        try:
            cp = subprocess.run([str(stt_py), "-c", code, str(wav_path), model_size],
                                capture_output=True, text=True, timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            lines = [ln for ln in (cp.stdout or "").splitlines() if ln.strip().startswith("{")]
            if lines:
                return {"ok": True, **_json.loads(lines[-1])}
            return {"ok": False, "error": "no transcript produced", "stderr": (cp.stderr or "")[-200:]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}
    # in-process fallback if faster_whisper ever lands in the calling python
    try:
        from faster_whisper import WhisperModel  # type: ignore
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _info = model.transcribe(wav_path)
        return {"ok": True, "text": " ".join(s.text for s in segments).strip()}
    except Exception:
        return {"ok": False, "error": "no STT backend installed",
                "enable": "faster-whisper into runtime/stt_venv, or a Deepgram API key"}


def talk_reply(prompt: str, *, voice: str = "", to_wav: Optional[str] = None) -> dict:
    """Run the prompt through Engel's failover chat and SPEAK the answer."""
    sys.path.insert(0, str(ROOT / "tools"))
    import engel_agent_failover_loop as fl
    result = fl.run_with_failover(prompt, timeout_s=60, max_tokens=256)
    reply = result.reply if result.ok else "Engel couldn't reach an AI right now."
    if to_wav:
        say = synthesize_to_wav(reply, to_wav, voice=voice)
    else:
        say = speak(reply, voice=voice)
    return {"ok": result.ok, "reply": reply, "provider": result.provider, "spoken": say}


def voice_turn(wav_in: str, *, voice: str = "", to_wav: Optional[str] = None) -> dict:
    """Full two-way voice turn from a WAV: transcribe -> failover chat -> speak.
    For a LIVE microphone turn use listen_and_reply()."""
    heard = transcribe(wav_in)
    if not heard.get("ok"):
        return {"ok": False, "stage": "stt", **heard}
    r = talk_reply(heard["text"], voice=voice, to_wav=to_wav)
    return {"ok": r["ok"], "heard": heard["text"], "reply": r["reply"],
            "provider": r["provider"], "spoken": r["spoken"]}


def mic_available() -> bool:
    """True if sounddevice (PortAudio) is importable AND an input device exists."""
    try:
        import sounddevice as sd
        return any(d.get("max_input_channels", 0) > 0 for d in sd.query_devices())
    except Exception:
        return False


def record_mic(seconds: float = 5.0, out_path: Optional[str] = None,
               samplerate: int = 16000) -> dict:
    """Capture the default microphone to a 16-bit mono WAV (16kHz, STT-ready).
    Needs sounddevice (PortAudio) + numpy in the Engel runtime — no soundfile
    dependency, the buffer is written with the stdlib wave module."""
    try:
        import sounddevice as sd
        import wave
    except Exception as exc:
        return {"ok": False, "error": f"mic capture needs sounddevice: {exc}",
                "enable": r"runtime\python310\python.exe -m pip install sounddevice"}
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    if not out_path:
        import time
        out_path = str(VOICE_DIR / f"mic_{int(time.time()*1000)}.wav")
    try:
        frames = int(max(0.2, float(seconds)) * samplerate)
        audio = sd.rec(frames, samplerate=samplerate, channels=1, dtype="int16")
        sd.wait()
        with wave.open(out_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)  # int16
            w.setframerate(samplerate)
            w.writeframes(audio.tobytes())
        return {"ok": True, "path": out_path,
                "seconds": round(frames / samplerate, 2),
                "bytes": Path(out_path).stat().st_size}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def listen_and_reply(seconds: float = 5.0, *, voice: str = "",
                     to_wav: Optional[str] = None, samplerate: int = 16000) -> dict:
    """LIVE two-way turn: record the mic -> STT -> failover chat -> speak the answer.
    This is the full-loop entry point the Flutter Voice panel drives."""
    cap = record_mic(seconds, samplerate=samplerate)
    if not cap.get("ok"):
        return {"ok": False, "stage": "mic", **cap}
    out = voice_turn(cap["path"], voice=voice, to_wav=to_wav)
    out["captured"] = cap.get("path")
    return out


def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel voice — TTS (Windows SAPI) + talk (OpenClaw voice port).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("voices")
    sp = sub.add_parser("speak"); sp.add_argument("--text", required=True); sp.add_argument("--voice", default="")
    sy = sub.add_parser("synth"); sy.add_argument("--text", required=True); sy.add_argument("--out", default=""); sy.add_argument("--voice", default="")
    tk = sub.add_parser("talk"); tk.add_argument("--prompt", required=True); tk.add_argument("--wav", default=""); tk.add_argument("--voice", default="")
    tr = sub.add_parser("transcribe"); tr.add_argument("--wav", required=True)
    vt = sub.add_parser("voice-turn"); vt.add_argument("--wav-in", required=True); vt.add_argument("--wav-out", default=""); vt.add_argument("--voice", default="")
    mc = sub.add_parser("mic"); mc.add_argument("--seconds", type=float, default=5.0); mc.add_argument("--out", default="")
    ls = sub.add_parser("listen"); ls.add_argument("--seconds", type=float, default=5.0); ls.add_argument("--wav-out", default=""); ls.add_argument("--voice", default="")
    a = ap.parse_args(argv)
    import json
    if a.cmd == "voices":
        for v in list_voices():
            print("  " + v)
    elif a.cmd == "speak":
        print(json.dumps(speak(a.text, a.voice)))
    elif a.cmd == "synth":
        print(json.dumps(synthesize_to_wav(a.text, a.out or None, a.voice), indent=2))
    elif a.cmd == "talk":
        print(json.dumps(talk_reply(a.prompt, voice=a.voice, to_wav=a.wav or None), indent=2))
    elif a.cmd == "transcribe":
        print(json.dumps(transcribe(a.wav), indent=2))
    elif a.cmd == "voice-turn":
        print(json.dumps(voice_turn(a.wav_in, voice=a.voice, to_wav=a.wav_out or None), indent=2))
    elif a.cmd == "mic":
        print(json.dumps(record_mic(a.seconds, a.out or None), indent=2))
    elif a.cmd == "listen":
        print(json.dumps(listen_and_reply(a.seconds, voice=a.voice, to_wav=a.wav_out or None), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
