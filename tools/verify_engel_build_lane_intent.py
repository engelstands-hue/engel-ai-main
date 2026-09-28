#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from engel_main_local_model_worker import _requested_app_build


def main() -> int:
    positives = (
        "Build me a CLI status tool in Python.",
        "Create a small drafting dashboard app.",
        "Write a script that validates drawing filenames.",
        # (2026-08-14) the live failure that motivated the pdf/spreadsheet/qr-code
        # targets: this exact ask got "which tool do you want - Acrobat, Word,
        # Blender?" from the quick chat lane instead of a built artifact.
        "Lets make a pdf with hello world then a 3d one spinning",
        "Create a spreadsheet of the door hardware schedule totals.",
        "Make me a qr code for the shop wifi.",
    )
    negatives = (
        "Write a brief client update in English and Spanish.",
        "Tell me what happened on both phones.",
        "Make the explanation practical and direct.",
        # pdf/spreadsheet in PROSE must stay chat: no build verb, or a question.
        "Summarize this pdf for me please.",
        "What does the pdf say about egress widths?",
        "Is the spreadsheet from yesterday still correct?",
    )
    for prompt in positives:
        assert _requested_app_build(prompt) == prompt, prompt
    for prompt in negatives:
        assert _requested_app_build(prompt) is None, prompt
    print("VERIFY_ENGEL_BUILD_LANE_INTENT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
