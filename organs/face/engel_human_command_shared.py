from __future__ import annotations

import datetime


HUMAN_COMMAND_CONTRACT_VERIFIER_REL = r"tools\verify_human_command_mode_contract.py"
CODEX_VERIFY_SCRIPT_REL = r"scripts\codex_verify.ps1"

POST_INSTALL_VERIFIER_COMMANDS = (
    rf"python .\{HUMAN_COMMAND_CONTRACT_VERIFIER_REL}",
    rf"powershell -ExecutionPolicy Bypass -File .\{CODEX_VERIFY_SCRIPT_REL}",
)


def human_command_now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def post_install_verifier_lines() -> list[str]:
    return ["- " + command for command in POST_INSTALL_VERIFIER_COMMANDS]


def post_install_verifier_sentence() -> str:
    return " and ".join(POST_INSTALL_VERIFIER_COMMANDS)
