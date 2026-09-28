"""Engel Verify Status — run static workspace verifiers read-only.

Each render_* function runs one of the tools/ verify scripts via subprocess
(they call sys.exit(), so subprocess isolation is required). No network,
no model calls, no mutations — pure file-system checks.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_APP_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
_TOOLS_DIR = _APP_ROOT.parent / "tools"  # D:\b.WorkSpace\tools


def _run_verifier(script_name: str, label: str) -> str:
    script = _TOOLS_DIR / script_name
    if not script.exists():
        return f"# {label}\n\nScript not found: {script}"
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_APP_ROOT.parent),  # workspace root so relative paths resolve
        )
        output = (result.stdout + result.stderr).strip()
        status = "PASS" if result.returncode == 0 else "FAIL"
        return f"# {label} — {status}\n\n```\n{output[:3000]}\n```"
    except subprocess.TimeoutExpired:
        return f"# {label} — TIMEOUT\n\nVerifier exceeded 30s time limit."
    except Exception as exc:
        return f"# {label} — ERROR\n\n{exc}"


def render_verify_local_llm_growth() -> str:
    return _run_verifier(
        "verify_customer_ready_local_llm_growth.py",
        "Customer-Ready Local LLM Growth Verifier",
    )


def render_verify_promotion() -> str:
    return _run_verifier(
        "verify_customer_ready_promotion.py",
        "Customer-Ready Promotion Verifier",
    )


def render_verify_brain_provider() -> str:
    return _run_verifier(
        "verify_brain_provider_trusted_context.py",
        "Brain Provider Trusted Context Verifier",
    )


def render_verify_llm_teaching() -> str:
    return _run_verifier(
        "verify_local_llm_one_hour_teaching_session.py",
        "Local LLM One-Hour Teaching Session Verifier",
    )


def render_verify_style_guide() -> str:
    return _run_verifier(
        "verify_local_llm_trusted_style_guide_proposal.py",
        "Local LLM Trusted Style Guide Proposal Verifier",
    )


def render_verify_all() -> str:
    """Run all verifiers and produce a combined summary."""
    verifiers = [
        ("verify_customer_ready_local_llm_growth.py", "Local LLM Growth"),
        ("verify_customer_ready_promotion.py", "Promotion"),
        ("verify_brain_provider_trusted_context.py", "Brain Provider"),
        ("verify_local_llm_one_hour_teaching_session.py", "LLM Teaching Session"),
        ("verify_local_llm_trusted_style_guide_proposal.py", "Style Guide Proposal"),
    ]
    lines = ["# Engel Verify — All Verifiers", ""]
    passes = 0
    fails = 0
    errors = 0
    for script, label in verifiers:
        script_path = _TOOLS_DIR / script
        if not script_path.exists():
            lines.append(f"  SKIP   {label} (script not found)")
            errors += 1
            continue
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True, text=True, timeout=30,
                cwd=str(_APP_ROOT.parent),
            )
            if result.returncode == 0:
                lines.append(f"  PASS   {label}")
                passes += 1
            else:
                # Extract FAIL lines from output
                fail_lines = [l for l in (result.stdout + result.stderr).splitlines()
                              if "FAIL" in l or "RESULT" in l]
                lines.append(f"  FAIL   {label}")
                for fl in fail_lines[:3]:
                    lines.append(f"           {fl.strip()}")
                fails += 1
        except subprocess.TimeoutExpired:
            lines.append(f"  TIMEOUT {label}")
            errors += 1
        except Exception as exc:
            lines.append(f"  ERROR  {label}: {exc}")
            errors += 1
    lines += [
        "",
        f"Results: {passes} pass | {fails} fail | {errors} skip/error",
        f"Overall: {'PASS' if fails == 0 and errors == 0 else 'FAIL'}",
    ]
    return "\n".join(lines)
