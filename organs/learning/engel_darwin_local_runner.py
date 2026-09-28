"""Engel Darwin Local Runner â€” run Darwin evolution using llama-cli (no Anthropic SDK).

Provides a local version of the parrot problem that substitutes the Anthropic
API calls with engel_llama_cli_runner subprocess inference.

Safety: NO_PROVIDER_CALLS, NO_NETWORK, NO_TRUSTED_MEMORY_WRITE.
Requires: jinja2, pydantic, llama-cli binary, active model.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_APP_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
_LAB_ROOT = _APP_ROOT / "engel_evolution_lab_main"


def _ensure_lab_on_path() -> bool:
    """Add engel_evolution_lab_main to sys.path so Darwin imports work."""
    lab = str(_LAB_ROOT)
    if lab not in sys.path:
        sys.path.insert(0, lab)
    return (_LAB_ROOT / "engel_darwin" / "__init__.py").exists()


def _extract_response(raw: str) -> str:
    """Pull the actual LLM text out of a render_llama_cli_run() result block.

    llama-cli stdout includes a banner, command list, '> prompt' line, response,
    token stats, and 'Exiting...'. We want only what follows the '> ' prompt line.
    """
    marker = "## Response\n\n"
    idx = raw.find(marker)
    section = raw[idx + len(marker):] if idx != -1 else raw
    lines = section.split("\n")
    response_lines: list[str] = []
    found_prompt = False
    for line in lines:
        if not found_prompt:
            if line.startswith("> "):
                found_prompt = True
            continue
        # Stop at token-rate stats or exit message
        if line.startswith("[ Prompt:") or line.strip() == "Exiting...":
            break
        response_lines.append(line)
    if response_lines:
        return "\n".join(response_lines).strip()
    # Fallback: strip banner lines heuristically
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(("â–„", "â–ˆ", "/", "build", "model", "mod", "avail", "Loading")):
            return stripped
    return section.strip()


# ---------------------------------------------------------------------------
# Local organism â€” overrides run() to use llama-cli
# ---------------------------------------------------------------------------

class LocalParrotOrganism:
    """Parrot organism that uses llama-cli instead of Anthropic for inference."""

    def __init__(
        self,
        prompt_template: str,
        parent: "LocalParrotOrganism | None" = None,
        model_path: "Path | None" = None,
    ) -> None:
        self.prompt_template = prompt_template
        self.parent = parent
        self.model_path = model_path  # None â†’ use active model

    def run(self, phrase: str) -> str:
        import jinja2
        try:
            prompt = jinja2.Template(self.prompt_template).render(phrase=phrase)
        except jinja2.exceptions.TemplateError as exc:
            return "Error: " + str(exc)
        if not prompt:
            return ""
        if self.model_path is not None:
            from engel_llama_cli_runner import render_llama_cli_run_with_model
            raw = render_llama_cli_run_with_model(self.model_path, prompt)
        else:
            from engel_llama_cli_runner import render_llama_cli_run
            raw = render_llama_cli_run(prompt)
        return _extract_response(raw)


# ---------------------------------------------------------------------------
# Local evaluator â€” uses LocalParrotOrganism.run()
# ---------------------------------------------------------------------------

TRAINABLE_PHRASES = [
    "bla",
    "Bla",
    "bla.",
    "bla twice.",
]
HOLDOUT_PHRASES = [
    "bla, but only once.",
    "'bla'",
]


def _evaluate(organism: LocalParrotOrganism) -> dict:
    failures = []
    correct = 0
    total = len(TRAINABLE_PHRASES) + len(HOLDOUT_PHRASES)
    for i, phrase in enumerate(TRAINABLE_PHRASES):
        resp = organism.run(phrase)
        if resp.strip() == phrase:
            correct += 1
        else:
            failures.append({"kind": "trainable", "idx": i, "phrase": phrase, "response": resp})
    for i, phrase in enumerate(HOLDOUT_PHRASES):
        resp = organism.run(phrase)
        if resp.strip() == phrase:
            correct += 1
        else:
            failures.append({"kind": "holdout", "idx": i, "phrase": phrase, "response": resp})
    return {"score": correct / total, "correct": correct, "total": total, "failures": failures}


# ---------------------------------------------------------------------------
# Local mutator â€” uses llama-cli to generate improved prompt
# ---------------------------------------------------------------------------

_IMPROVEMENT_PROMPT = """\
We want a prompt that causes an LLM to repeat back a given phrase verbatim.

Current prompt template:
```
{prompt_template}
```

The phrase placeholder is {{{{ phrase }}}}. The template is filled with a phrase and sent to an LLM.

The LLM failed on this phrase:
```
{phrase}
```

The LLM's response was:
```
{response}
```

Please diagnose the problem and then write an improved prompt template.
End your response with the improved template enclosed in triple backticks.
"""


def _resolve_model(slug: str | None) -> "Path | None":
    """Resolve a model slug to a Path, or return the best available fallback."""
    from pathlib import Path as _Path
    if slug:
        try:
            from engel_local_model_manager import _find_gguf_files
            matched = next((m for m in _find_gguf_files() if m["slug"] == slug), None)
            if matched:
                return _Path(matched["path"])
        except Exception:
            pass
    # Prefer 7B for quality; fall back to whatever is active
    preferred = [
        _Path("/opt/engel/models-active/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m.gguf"),
        _Path("/opt/engel/models-active/mistral-7b-instruct-v0.3/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"),
        _Path("/opt/engel/models-active/qwen2.5-3b-instruct/qwen2.5-3b-instruct-q5_k_m.gguf"),
    ]
    for p in preferred:
        if p.exists():
            return p
    from engel_llama_cli_runner import _active_model_path
    return _active_model_path()


def _mutate(organism: LocalParrotOrganism, failure: dict, model_path: "Path | None" = None) -> "LocalParrotOrganism | None":
    prompt = _IMPROVEMENT_PROMPT.format(
        prompt_template=organism.prompt_template,
        phrase=failure["phrase"],
        response=failure["response"],
    )
    if model_path is not None:
        from engel_llama_cli_runner import render_llama_cli_run_with_model
        raw = render_llama_cli_run_with_model(model_path, prompt)
    else:
        from engel_llama_cli_runner import render_llama_cli_run
        raw = render_llama_cli_run(prompt)
    response_text = _extract_response(raw)
    # Parse last ```-enclosed block
    parts = response_text.split("```")
    if len(parts) < 3:
        return None
    new_template = parts[-2].strip()
    if not new_template:
        return None
    return LocalParrotOrganism(prompt_template=new_template, parent=organism, model_path=model_path)


# ---------------------------------------------------------------------------
# Route render functions
# ---------------------------------------------------------------------------

def render_darwin_local_parrot_run(payload: str = "") -> str:
    """Run 1-2 iterations of parrot evolution using llama-cli (no Anthropic needed).

    Payload (optional): model slug to use, e.g. "qwen2_5_7b_instruct_q5_k_m"
    Default: auto-selects largest available model (7B > 3B > active).
    """
    from engel_llama_cli_runner import _find_cli

    cli, is_cuda = _find_cli()
    if cli is None:
        return "# Darwin Local Parrot â€” FAIL\n\nNo llama-cli.exe found under F: drive.\nCheck: engel llama cli status"

    slug = payload.strip() or None
    model = _resolve_model(slug)
    if model is None:
        return (
            "# Darwin Local Parrot â€” FAIL\n\n"
            "No model available. Load one first:\n  engel models load qwen2_5_7b_instruct_q5_k_m"
        )

    backend = "CUDA" if is_cuda else "CPU"
    lines = [
        "# Darwin Local Parrot â€” Evolution Run",
        "",
        f"Model:   {model.name}",
        f"CLI:     {cli.parent.name}  [{backend}]",
        f"Phrases (trainable): {len(TRAINABLE_PHRASES)} | Holdout: {len(HOLDOUT_PHRASES)}",
        "",
    ]

    # Generation 0
    organism = LocalParrotOrganism(prompt_template="Say {{ phrase }}", model_path=model)
    lines += ["## Generation 0 â€” Evaluate initial organism", ""]
    t0 = time.time()
    result0 = _evaluate(organism)
    lines += [
        f"Score:   {result0['correct']}/{result0['total']} ({result0['score']:.0%})",
        f"Elapsed: {round(time.time()-t0, 1)}s",
    ]
    if result0["failures"]:
        lines.append(f"Failures: {len(result0['failures'])}")
        for f in result0["failures"][:2]:
            lines.append(f"  phrase={f['phrase']!r}  got={f['response'][:60]!r}")
    lines.append("")

    if result0["score"] >= 1.0:
        lines += ["Perfect score on generation 0. No mutation needed."]
        return "\n".join(lines)

    # Mutation attempt
    trainable_failures = [f for f in result0["failures"] if f["kind"] == "trainable"]
    if not trainable_failures:
        lines += ["No trainable failures. Cannot mutate."]
        return "\n".join(lines)

    lines += ["## Generation 1 â€” Mutate", ""]
    t1 = time.time()
    mutant = _mutate(organism, trainable_failures[0], model_path=model)
    elapsed_mutate = round(time.time()-t1, 1)

    if mutant is None:
        lines += [f"Mutator failed to produce a valid template ({elapsed_mutate}s). Try a larger model."]
        return "\n".join(lines)

    mutant.model_path = model
    lines += [
        f"Mutator elapsed: {elapsed_mutate}s",
        f"New template:    {mutant.prompt_template[:120]!r}",
        "",
    ]

    # Evaluate mutant
    lines += ["## Generation 1 â€” Evaluate mutant", ""]
    t2 = time.time()
    result1 = _evaluate(mutant)
    lines += [
        f"Score:   {result1['correct']}/{result1['total']} ({result1['score']:.0%})",
        f"Elapsed: {round(time.time()-t2, 1)}s",
    ]
    if result1["failures"]:
        lines.append(f"Failures: {len(result1['failures'])}")

    delta = result1["score"] - result0["score"]
    lines += [
        "",
        f"Delta: {delta:+.0%} ({'improved' if delta > 0 else 'same' if delta == 0 else 'regressed'})",
        "",
        "Run complete. For more iterations use the Darwin CLI:",
        "  cd engel_evolution_lab_main",
        "  python -m engel_darwin parrot --num_iterations 5  (requires ANTHROPIC_API_KEY)",
    ]
    return "\n".join(lines)


def render_darwin_local_parrot_status() -> str:
    """Show prerequisites and readiness for local parrot evolution."""
    from engel_llama_cli_runner import _find_cli, _active_model_path
    cli, is_cuda = _find_cli()
    model = _active_model_path()
    lab_ok = _ensure_lab_on_path()
    backend = "CUDA" if is_cuda else "CPU"

    checks = [
        ("llama-cli binary", cli is not None, (str(cli) + f"  [{backend}]") if cli else "MISSING"),
        ("active model", model is not None, str(model.name) if model else "MISSING â€” load one first"),
        ("engel_darwin module", lab_ok, str(_LAB_ROOT / "engel_darwin") if lab_ok else "NOT FOUND"),
        ("jinja2", True, _check_import("jinja2")),
        ("pydantic", True, _check_import("pydantic")),
    ]
    all_ok = all(ok for _, ok, _ in checks)
    lines = [
        "# Darwin Local Parrot â€” Status",
        "",
        f"Overall: {'READY' if all_ok else 'NOT READY'}",
        "",
        "Prerequisites:",
    ]
    for label, ok, detail in checks:
        mark = "OK" if ok else "FAIL"
        lines.append(f"  [{mark}]  {label:25s}  {detail}")
    lines += [
        "",
        "Run:  engel darwin local parrot run",
        "Note: local run uses llama-cli â€” no Anthropic SDK needed.",
        "      Model quality affects mutation quality. 7B+ recommended for mutation.",
    ]
    return "\n".join(lines)


def _check_import(name: str) -> str:
    try:
        import importlib
        m = importlib.import_module(name)
        return getattr(m, "__version__", "installed")
    except ImportError:
        return "NOT INSTALLED"
