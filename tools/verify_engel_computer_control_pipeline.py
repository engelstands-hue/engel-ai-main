from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "tools" / "engel_computer_control_pipeline.py"
LAUNCHER = ROOT / "scripts" / "Start-EngelComputerControlPipeline.ps1"
CONTRACT = ROOT / "memory" / "ENGEL_COMPUTER_CONTROL_PIPELINE_CONTRACT_V1.md"
REPORT_ROOT = ROOT / "reports" / "computer_control_pipeline"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_json_from_stdout(stdout: str) -> dict:
    text = stdout.strip()
    require(text, "empty JSON stdout")
    payload = json.loads(text)
    require(isinstance(payload, dict), "stdout JSON is not an object")
    return payload


def main() -> int:
    for path in [PIPELINE, LAUNCHER, CONTRACT]:
        require(path.is_file(), f"missing file: {path}")

    source = read(PIPELINE)
    launcher = read(LAUNCHER)
    contract = read(CONTRACT)

    require("APPROVE_COMPUTER_CONTROL_ACTIONS" in source, "approval token missing")
    require("--allow-actions" in source, "allow-actions CLI gate missing")
    require("--approval-token" in source, "approval-token CLI gate missing")
    require("--full-access" in source, "full-access CLI gate missing")
    require("operator approved full access in chat on 2026-07-02" in source, "operator full-access approval marker missing")
    require("DEFAULT_LOCAL_LLM_URLS" in source, "local/server LLM URL list missing")
    require("http://127.0.0.1:24680" in source, "Engel server/local chat URL missing")
    require("default=30.0" in source, "LLM timeout default must allow Engel server responses")
    require('"timeout": max(5, int(args.llm_timeout))' in source, "Engel server timeout not forwarded")
    require("rules_decision" in source, "rules fallback missing")
    require("redact_text" in source and "SECRET_WORDS" in source, "screen state redaction missing")
    require("easyocr.Reader" in source, "EasyOCR fallback missing")
    require("shutil.which(\"tesseract\")" in source, "Tesseract executable guard missing")
    require("capture_screen" in source and "build_state" in source, "capture/state builder missing")
    require("execute_action" in source and "dry-run" in source, "guarded action layer missing")
    require("vault_used" in source and "False" in source, "Vault-use receipt field missing")
    require("Start-EngelComputerControlPipeline" in str(LAUNCHER), "launcher name mismatch")
    require("--no-llm" in launcher and "--llm-url" in launcher, "launcher LLM controls missing")
    require("$AllowActions" in launcher and "$ApprovalToken" in launcher, "launcher action gates missing")
    require("$FullAccess" in launcher and "--full-access" in launcher, "launcher full-access gate missing")
    require("No writes to `/mnt/engel-vault`" in contract, "contract missing offline Vault rule")
    require("Josh explicitly approved this full-access operator mode on 2026-07-02" in contract, "contract missing full-access approval record")

    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(PIPELINE)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(compile_result.returncode == 0, compile_result.stderr)

    ps_parse = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "$path = " + json.dumps(str(LAUNCHER)) + "; "
                "$null=[System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$null,[ref]$errs); "
                "if($errs.Count){$errs | ForEach-Object { $_.Message }; exit 1}; 'PS_PARSE_OK'"
            ),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(ps_parse.returncode == 0, ps_parse.stdout + ps_parse.stderr)

    self_test = subprocess.run(
        [sys.executable, str(PIPELINE), "--self-test", "--no-llm", "--json", "--goal", "Observe Engel AI Main screen"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=60,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(self_test.returncode == 0, self_test.stderr)
    payload = parse_json_from_stdout(self_test.stdout)
    require(payload.get("schema") == "engel_computer_control_pipeline_v1", "bad pipeline schema")
    require(payload.get("ok") is True, "pipeline self-test not ok")
    require(payload.get("vault_used") is False, "pipeline claims Vault use")
    require(payload.get("actions_guarded") is True, "actions not guarded")
    require(payload.get("full_access") is False, "self-test should not use full access")
    require(payload.get("allow_actions") is False, "self-test should not allow actions")
    require(payload.get("secrets_redacted") is True, "redaction flag missing")
    require(float(payload.get("llm_timeout_seconds") or 0) >= 20, "LLM timeout receipt too low")
    require(payload.get("cycles"), "self-test produced no cycles")
    first_cycle = payload["cycles"][0]
    require(first_cycle["decision"]["engine"] == "rules", "self-test should use rules fallback with --no-llm")
    require(first_cycle["action_result"]["executed"] is False, "self-test should not execute actions")
    require(REPORT_ROOT.is_dir(), "report root not created")

    print(
        json.dumps(
            {
                "ok": True,
                "schema": "engel_computer_control_pipeline_verify_v1",
                "pipeline_report": payload.get("report_path"),
                "decision_engine": first_cycle["decision"]["engine"],
                "action_status": first_cycle["action_result"]["status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
