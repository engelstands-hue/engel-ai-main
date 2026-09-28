"""Engel Darwin Status — read-only framework info for engel_darwin evolution lab.

engel_darwin problems currently require Anthropic SDK for LLM mutations.
This module surfaces framework structure, available problems, and dependency
status without executing any problem runs or making provider calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

_APP_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
_DARWIN_ROOT = _APP_ROOT / "engel_evolution_lab_main" / "engel_darwin"


def _darwin_available() -> bool:
    return _DARWIN_ROOT.exists() and (_DARWIN_ROOT / "__init__.py").exists()


def _check_dep(name: str) -> tuple[bool, str]:
    try:
        import importlib
        mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", "installed")
        return True, ver
    except ImportError:
        return False, "NOT INSTALLED"


def render_darwin_status() -> str:
    present = _darwin_available()
    lines = ["# Engel Darwin — Evolution Lab Status", ""]
    lines += [
        f"Module path:     {_DARWIN_ROOT}",
        f"Module present:  {'YES' if present else 'NO'}",
        "",
    ]
    if not present:
        lines += [
            "engel_darwin not found. Expected:",
            f"  {_DARWIN_ROOT}",
        ]
        return "\n".join(lines)
    # Deps
    deps = [
        ("pydantic", "pydantic"),
        ("jinja2", "jinja2"),
        ("anthropic", "anthropic"),  # required for all current problems
        ("numpy", "numpy"),
        ("func_timeout", "func_timeout"),
    ]
    lines.append("Dependencies:")
    all_core_ok = True
    for label, module in deps:
        ok, ver = _check_dep(module)
        status = f"OK ({ver})" if ok else "MISSING"
        required = " [required for problems]" if module == "anthropic" else ""
        lines.append(f"  {label:15s}  {status}{required}")
        if module != "anthropic" and not ok:
            all_core_ok = False
    lines += [
        "",
        "Note: All current problem implementations call Anthropic API.",
        "      anthropic SDK and ANTHROPIC_API_KEY env var are needed to run problems.",
        "      Status/info routes run without provider calls.",
        "",
        f"Framework ready (structure):  {'YES' if present else 'NO'}",
        f"Ready to run problems:        {'YES' if _check_dep('anthropic')[0] else 'NO (missing anthropic SDK)'}",
    ]
    return "\n".join(lines)


def render_darwin_problems() -> str:
    """List available evolution problems with descriptions."""
    if not _darwin_available():
        return "# Engel Darwin — Problems\n\nengel_darwin module not found."
    lines = ["# Engel Darwin — Available Problems", ""]
    problems = {
        "parrot": {
            "desc": "Evolve a prompt that causes an LLM to repeat a phrase verbatim.",
            "difficulty": "beginner",
            "model": "claude-sonnet-4-6",
            "advanced": ["batch mutation", "holdout phrases"],
        },
        "circle_packing": {
            "desc": "Evolve code that packs circles into a bounded area.",
            "difficulty": "intermediate",
            "model": "claude-sonnet-4-6",
            "advanced": ["code evolution", "numpy scoring", "func_timeout safety"],
        },
        "multiplication_verifier": {
            "desc": "Evolve a prompt that reliably verifies multiplication results.",
            "difficulty": "intermediate",
            "model": "claude-haiku-4-5 (eval) + claude-sonnet-4-6 (mutate)",
            "advanced": ["batch mutation", "post-mutation verification", "enum scoring"],
        },
    }
    for name, info in problems.items():
        lines += [
            f"## {name}",
            f"  {info['desc']}",
            f"  Difficulty:  {info['difficulty']}",
            f"  Model used:  {info['model']}",
            f"  Features:    {', '.join(info['advanced'])}",
            "",
        ]
    lines += [
        "To run a problem (requires ANTHROPIC_API_KEY):",
        "  cd engel_evolution_lab_main",
        "  python -m engel_darwin <problem_name> --num_iterations 3",
        "",
        "Available problem names: " + ", ".join(problems),
    ]
    return "\n".join(lines)


def render_darwin_framework_info() -> str:
    """Explain the engel_darwin Organism/Mutator/Evaluator framework."""
    return "\n".join([
        "# Engel Darwin — Framework Architecture",
        "",
        "engel_darwin implements a Darwinian evolution loop for LLM prompts and code.",
        "Based on the ACES / Darwin Prompt paper approach.",
        "",
        "## Core Abstractions",
        "",
        "  Organism     — The evolving artifact (a prompt template, a code block, etc.)",
        "  Evaluator    — Scores organisms; produces EvaluationResult + FailureCases",
        "  Mutator      — Takes an organism + failures, asks an LLM for improvements",
        "  Population   — Manages the current generation of organisms",
        "  LearningLog  — Accumulates cross-generation insights for the Mutator",
        "",
        "## Evolution Loop",
        "",
        "  1. Start with initial_organism",
        "  2. Evaluate → get score and failure cases",
        "  3. If viable and score good enough → done",
        "  4. Otherwise → Mutator proposes improved organisms (via LLM)",
        "  5. Optionally verify mutations → filter bad ones",
        "  6. Add survivors to population → repeat from step 2",
        "",
        "## Extending with a Local LLM Mutator",
        "",
        "  The Mutator's only requirement is a mutate() method. You can replace",
        "  Anthropic calls with llama-cli or llama-cpp-python by subclassing Mutator",
        "  and calling render_llama_cli_run(prompt) instead of Anthropic().messages.create().",
        "",
        "  Example stub:",
        "    class LocalMutator(Mutator[ParrotOrganism, ParrotEvaluationFailureCase]):",
        "        def mutate(self, organism, failure_cases, learning_log):",
        "            from engel_llama_cli_runner import render_llama_cli_run",
        "            response = render_llama_cli_run(self.build_prompt(organism, failure_cases))",
        "            return [ParrotOrganism(prompt_template=self._parse(response))]",
        "",
        "Module path:  " + str(_DARWIN_ROOT),
        "Problems:     parrot, circle_packing, multiplication_verifier",
    ])


def render_darwin_learning_log() -> str:
    """Check for any existing learning log files from past runs."""
    if not _darwin_available():
        return "# Engel Darwin — Learning Log\n\nModule not found."
    # Learning logs are written to the cwd at run time — check common locations
    search_roots = [
        _APP_ROOT / "engel_evolution_lab_main",
        _APP_ROOT / "reports" / "darwin",
        _APP_ROOT,
    ]
    logs: list[Path] = []
    for root in search_roots:
        if root.exists():
            logs.extend(root.rglob("learning_log*.json"))
            logs.extend(root.rglob("lineage*.json"))
    lines = ["# Engel Darwin — Learning Log", ""]
    if logs:
        lines.append(f"Found {len(logs)} log file(s):")
        for log in sorted(logs)[:10]:
            lines.append(f"  {log}  ({log.stat().st_size // 1024} KB)")
    else:
        lines += [
            "No learning log files found.",
            "Logs are created when you run a problem:",
            "  python -m engel_darwin parrot --num_iterations 3",
        ]
    return "\n".join(lines)
