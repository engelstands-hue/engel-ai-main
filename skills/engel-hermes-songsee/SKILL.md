---
name: "engel-hermes-songsee"
description: "Audio spectrograms/features (mel, chroma, MFCC) via CLI."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-26T00:45:20Z"
updated_at_utc: "2026-08-26T00:45:20Z"
---

# Engel Hermes songsee

## Purpose

Audio spectrograms/features (mel, chroma, MFCC) via CLI.

## Trigger Conditions

- songsee
- hermes songsee
- engel hermes songsee

## Operating Instructions

Operate as Engel AI Main. Authority order is Josh > Guardian > Engel/runtime. Use local Engel storage, routes, and receipts. Do not add provider/API/network calls, live trading keys, trusted-memory writes, queue mutation, ALIVE_STATE writes, autonomous loops, Level 2 runtime, or C: project writes. Do not print secrets, tokens, or private keys. Source remains on disk; this saved card does not enable the upstream tool by itself.

Source card: engel_agent_main/skills/media/songsee/SKILL.md

Audio spectrograms/features (mel, chroma, MFCC) via CLI.

# songsee

Generate spectrograms and multi-panel audio feature visualizations from audio files.

## Prerequisites

Requires [Go](https://go.dev/doc/install):
```bash
go install github.com/steipete/songsee/cmd/songsee@latest
```

Optional: `ffmpeg` for formats beyond WAV/MP3.

## Quick Start

```bash
# Basic spectrogram
songsee track.mp3

# Save to specific file
songsee track.mp3 -o spectrogram.png

# Multi-panel visualization grid
songsee track.mp3 --viz spectrogram,mel,chroma,hpss,selfsim,loudness,tempogram,mfcc,flux

# Time slice (start at 12.5s, 8s duration)
songsee track.mp3 --start 12.5 --duration 8 -o slice.jpg

# From stdin
cat track.mp3 | songsee - --format png -o out.png
```

## Visualization Types

Use `--viz` with comma-separated values:

| Type | Description |
|------|-------------|
| `spectrogram` | Standard frequency spectrogram |
| `mel` | Mel-scaled spectrogram |
| `chroma` | Pitch class distribution |
| `hpss` | Harmonic/percussive separation |
| `selfsim` | Self-similarity matrix |
| `loudness` | Loudness over time |
| `tempogram` | Tempo estimation |
| `mfcc` | Mel-frequency cepstral coefficients |
| `flux` | Spectral flux (onset detection) |

Multiple `--viz` types render as a grid in a single image.

## Common Flags

| Flag | Description |
|------|-------------|
| `--viz` | Visualization types (comma-separated) |
| `--style` | Color palette: `classic`, `magma`, `inferno`, `viridis`, `gray` |
| `--width` / `--height` | Output image dimensions |
| `--window` / `--hop` | FFT window and hop size |
| `--min-freq` / `--max-freq` | Frequency range filter |
| `--start` / `--duration` | Time slice of the audio |
| `--format` | Output format: `jpg` or `png` |
| `-o` | Output file path |

## Notes

- WAV and MP3 are decoded natively; other formats require `ffmpeg`
- Output images can be inspected with `vision_analyze` for automated audio analysis
- Useful for comparing audio outputs, debugging synthesis, or documenting audio processing pipelines

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
