#!/usr/bin/env python3
"""Apply adopted + v5 curriculum material for capabilities, math, and self-build.

Safety:
- Local-only artifact grounding (no live internet / provider research).
- Math answers come from the sympy-minted ENGEL_MATH_REN5_MINT.json.
- Communication + construction must already be adopted separately.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
MINT = ROOT / "memory" / "training" / "engel_main" / "generated" / "ENGEL_MATH_REN5_MINT.json"

CAPABILITY_CARDS_V5 = [
    {
        "topic": "running one REPS cycle as Record then Evaluate then Propose then Sign-off without skipping the gate",
        "scenario": "Engel observed a useful lesson and wants to improve. The capability audit must show the four REPS stages as separate receipts, name which bucket the proposal sits in, and prove nothing promoted itself.",
        "constraint": "Do not collapse Record into Propose, and never treat a drafted proposal as signed-off guidance; Bucket 3 work stays operator-owned.",
        "proof": "Ground the cycle in tools/engel_universal_reps_runtime.py and memory/ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.md, citing the stage names and authority order those artifacts define.",
        "artifacts": [
            "tools/engel_universal_reps_runtime.py",
            "memory/ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.md",
        ],
    },
    {
        "topic": "switching the laptop into Clean Computer Mode so Engel backends stop while Windows stays usable",
        "scenario": "Joshua wants the machine free for ordinary use. The audit must name which Engel tasks and vendor helpers Clean pauses, what must stay running, and why the desktop shortcut needs elevation for GlideX and Nahimic services.",
        "constraint": "Do not kill Explorer, Defender, or the NVIDIA display stack, and do not claim vendor services stopped without an elevated Clean pass.",
        "proof": "Use scripts/Engel-ComputerMode.ps1 and reports/codex_bridge/ENGEL_COMPUTER_MODE_DESKTOP_TOGGLE_20260910.md as the named Clean/Regular contract.",
        "artifacts": [
            "scripts/Engel-ComputerMode.ps1",
            "reports/codex_bridge/ENGEL_COMPUTER_MODE_DESKTOP_TOGGLE_20260910.md",
        ],
    },
    {
        "topic": "applying the humanization SLM only after the chat LLM drafts, and failing open on form-graded training turns",
        "scenario": "A chat draft sounds robotic. The audit must separate Layer-1 kernel rewrite from the optional 0.5B GGUF pass, and show why Confirmed/Proof and math Result/Check turns skip the voice rewrite.",
        "constraint": "Do not replace the live CT246 chat model with the 0.5B humanizer, and never rewrite a form-graded training answer into spoken prose.",
        "proof": "Base the boundary on tools/engel_chat_humanization_slm.py and tools/verify_engel_chat_humanization_slm.py.",
        "artifacts": [
            "tools/engel_chat_humanization_slm.py",
            "tools/verify_engel_chat_humanization_slm.py",
        ],
    },
    {
        "topic": "reading the SLM roster gates so a Reply Grader below the bar cannot pretend it met promotion",
        "scenario": "A model-training cycle receipt shows Intent and Style passing while Reply Grader sits below the gate. The audit must name each roster head, its score, and the keep/throw decision without promoting the failing head.",
        "constraint": "Do not average a failing head into a passing roster, and never auto-deploy weights that missed their gate.",
        "proof": "Use tools/verify_engel_slm_roster.py and tools/engel_slm_runtime.py to bind head status to the advisory-only contract.",
        "artifacts": ["tools/verify_engel_slm_roster.py", "tools/engel_slm_runtime.py"],
    },
    {
        "topic": "honoring CT246 server-first storage so the ROG laptop stays face and helper, not the default weight home",
        "scenario": "A lane asks where active models, receipts, and Meeting Room state should live. The audit must distinguish /opt/engel active runtime from archive vault paths and refuse laptop-external defaults that the registry excludes.",
        "constraint": "Do not treat the ROG SSD as the source of truth for Engel AI Main runtime state, and never invent a storage root outside the allowlist.",
        "proof": "Ground the topology in tools/verify_engel_storage_location_registry.py and memory/ENGEL_STORAGE_LOCATION_REGISTRY_V1.md.",
        "artifacts": [
            "tools/verify_engel_storage_location_registry.py",
            "memory/ENGEL_STORAGE_LOCATION_REGISTRY_V1.md",
        ],
    },
    {
        "topic": "treating each Android phone worker as an independent queue even when roleles share a name",
        "scenario": "Alpha and Beta both appear online. The audit must show separate worker ids, separate queues, and why a job for Alpha must not silently land on Beta.",
        "constraint": "Do not merge same-role phones into one queue, and do not count a return from the wrong serial as the assigned worker's work.",
        "proof": "Use tools/verify_engel_multi_android_remote_workers.py and tools/engel_device_broker.py as the independence contract.",
        "artifacts": [
            "tools/verify_engel_multi_android_remote_workers.py",
            "tools/engel_device_broker.py",
        ],
    },
    {
        "topic": "adopting generated curriculum only with a digest-bound approval phrase and an immutable receipt",
        "scenario": "Fresh construction or communication cards exist as a proposal. The audit must show the proposal digest, the exact approval phrase, the adopted bytes, and why Prepare Files alone cannot invent novel hours.",
        "constraint": "Do not treat a proposal as live material, and treat any adopted file whose bytes disagree with its receipt as tampered.",
        "proof": "Trace the chain through tools/engel_curriculum_adoption.py and tools/verify_engel_curriculum_adoption.py.",
        "artifacts": [
            "tools/engel_curriculum_adoption.py",
            "tools/verify_engel_curriculum_adoption.py",
        ],
    },
    {
        "topic": "stamping Wiki One after a CODE landing so organs, talks-to, and duties stay synchronized",
        "scenario": "A job changed an organ. The audit must show Wiki One was read first, organs.json updated when duties changed, and the journal stamp written with the wiki-read tool.",
        "constraint": "Do not land CODE against a stale Wiki One, and do not skip the journal stamp when an organ or talks-to edge changed.",
        "proof": "Use wiki/ONE.md and tools/stamp_wiki_one_journal.py as the named second-brain contract.",
        "artifacts": ["wiki/ONE.md", "tools/stamp_wiki_one_journal.py"],
    },
]

SELF_BUILD_CARDS_V5 = [
    {
        "topic": "keeping Clean Computer Mode and Regular Mode as operator toggles rather than silent background policy",
        "scenario": "Engel backends were burning CPU while the UI looked idle. The self-build review must show the Clean shortcut pausing EngelChatLinkSvc and vendor helpers, and Regular restoring only what Clean saved.",
        "constraint": "Do not leave tunnel watchdogs enabled after Clean, and do not restore disabled tasks that were already Disabled before Clean.",
        "proof": "Ground the toggle in scripts/Engel-ComputerMode.ps1 and reports/codex_bridge/ENGEL_PROCESS_DEEP_DIVE_CLEAN_EXPAND_20260910.md.",
        "artifacts": [
            "scripts/Engel-ComputerMode.ps1",
            "reports/codex_bridge/ENGEL_PROCESS_DEEP_DIVE_CLEAN_EXPAND_20260910.md",
        ],
    },
    {
        "topic": "feeding measured chat-voice failures back into the next Chat Communication adoption instead of rewriting old cards",
        "scenario": "Communication hours were exhausted. The self-build review must show rejected-reply classes becoming proposal cards, the digest-bound adopt step, and why nonce rewording is forbidden.",
        "constraint": "Do not renew a spent voice curriculum by capitalization tricks, and do not adopt without the printed approval phrase.",
        "proof": "Use tools/engel_communication_renewal_generator.py and tools/engel_prompt_novelty.py to bind measured classes to novelty.",
        "artifacts": [
            "tools/engel_communication_renewal_generator.py",
            "tools/engel_prompt_novelty.py",
        ],
    },
    {
        "topic": "regenerating Construction cards from unread code sections rather than replaying consumed section prompts",
        "scenario": "Construction ran out after section-bound hours. The review must show the generator skipping history-consumed anchors and emitting only sections with clean local excerpts.",
        "constraint": "Do not ship a card whose prompts are already in the novelty ledger, and never invent an excerpt the corpus cannot resolve.",
        "proof": "Base the path on tools/engel_construction_corpus_card_generator.py and tools/engel_prompt_novelty.py.",
        "artifacts": [
            "tools/engel_construction_corpus_card_generator.py",
            "tools/engel_prompt_novelty.py",
        ],
    },
    {
        "topic": "turning pack reject diagnostics into weakness cards without inventing missing artifacts",
        "scenario": "Hundreds of pack rows failed for fabricated citations and unnamed gaps. The self-build review must show observed counts, dropped classes with missing artifacts, and the explicit adopt step.",
        "constraint": "Do not draft a weakness card that cites a file that does not exist; drop the class instead of teaching the defect again.",
        "proof": "Use tools/engel_weakness_curriculum.py and tools/verify_engel_weakness_curriculum.py as the draft-and-adopt contract.",
        "artifacts": [
            "tools/engel_weakness_curriculum.py",
            "tools/verify_engel_weakness_curriculum.py",
        ],
    },
    {
        "topic": "minting a fresh math renewal set whose answers are sympy-proven before the independent oracle copies them",
        "scenario": "Math School exhausted its ren4 hours. The review must show the ren5 mint count, collision checks against the live registry, and the dual registration into engel_math_problems plus the renewal verifier oracle.",
        "constraint": "Do not hand-write answers that disagree with the production grader, and do not reuse a question string already in the registry.",
        "proof": "Ground the mint in tools/mint_engel_math_ren5_curriculum.py and tools/engel_math_problems.py.",
        "artifacts": [
            "tools/mint_engel_math_ren5_curriculum.py",
            "tools/engel_math_problems.py",
        ],
    },
    {
        "topic": "keeping humanization from rewriting form-graded engineering and math training answers into spoken filler",
        "scenario": "A Confirmed/Proof construction answer or a math Result/Check line entered the humanizer. The self-build check must show the fail-open skip and why voice rewrite would destroy the graded form.",
        "constraint": "Do not humanize labelled training forms; communication samples stay spoken, engineering and math forms stay exact.",
        "proof": "Use tools/engel_chat_humanization_slm.py and tools/verify_engel_chat_humanization_slm.py to name the skip contract.",
        "artifacts": [
            "tools/engel_chat_humanization_slm.py",
            "tools/verify_engel_chat_humanization_slm.py",
        ],
    },
    {
        "topic": "reconciling five-curriculum readiness after only some lanes received fresh adopted material",
        "scenario": "Construction is READY and Communication is PARTIAL while Capabilities, Math, and Self-Build remain EXHAUSTED. The review must report per-curriculum novelty honestly instead of one false all-ready flag.",
        "constraint": "Do not claim all_curricula_ready while any canonical lane is EXHAUSTED, and do not hide PARTIAL as READY.",
        "proof": "Use tools/sync_engel_training_assets.py and tools/verify_engel_all_five_training_readiness.py to recompute the index verdicts.",
        "artifacts": [
            "tools/sync_engel_training_assets.py",
            "tools/verify_engel_all_five_training_readiness.py",
        ],
    },
    {
        "topic": "preserving Josh > Guardian > Engel authority when REPS proposes source or route changes",
        "scenario": "REPS drafted a useful rule change. The self-build audit must map the proposal to the correct sign-off bucket and show why runtime/source edits cannot auto-apply from Record alone.",
        "constraint": "Do not auto-approve Bucket 2 or Bucket 3 from a high score, and never let Engel elevate itself above Josh or Guardian.",
        "proof": "Ground the authority cut in memory/ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.md and tools/engel_universal_reps_runtime.py.",
        "artifacts": [
            "memory/ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.md",
            "tools/engel_universal_reps_runtime.py",
        ],
    },
]


def _replace_active_cards(source: str, var_name: str, new_cards: list[dict], version_const: str, version_value: str) -> str:
    """Replace the active card list assignment body for a named list variable."""
    # Bump version constant
    source = re.sub(
        rf"({re.escape(version_const)}\s*=\s*\(\s*\n\s*\")[^\"]+(\")",
        rf"\g<1>{version_value}\2",
        source,
        count=1,
    )
    # Build python literal for cards without problem_ids helper complexity
    import pprint

    body = pprint.pformat(new_cards, width=88, sort_dicts=False)
    # Convert to list display closer to project style is optional; keep valid python
    pattern = rf"({var_name}\s*:\s*list\[dict\[str,\s*Any\]\]\s*=\s*)\[.*?\]\n\n"
    repl = rf"\1{body}\n\n"
    updated, n = re.subn(pattern, repl, source, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f"failed to replace {var_name}")
    return updated


def apply_math_problems(snippet: str) -> None:
    path = TOOLS / "engel_math_problems.py"
    text = path.read_text(encoding="utf-8")
    marker = "    # --- NOT decidable: proofs and conceptual statements -----------------------"
    if "ren5-alg-01" in text:
        print("math problems already contain ren5")
        return
    insert = (
        "    # --- 2026-09-14 v5 renewal (ren5-*): sympy-minted local renewal set ---\n"
        + snippet
        + "\n"
        + marker
    )
    if marker not in text:
        raise RuntimeError("decidable marker missing in engel_math_problems.py")
    path.write_text(text.replace(marker, insert, 1), encoding="utf-8")


def apply_oracle(snippet: str) -> None:
    path = TOOLS / "verify_engel_curriculum_renewal.py"
    text = path.read_text(encoding="utf-8")
    if "ren5-alg-01" in text:
        print("oracle already contains ren5")
        return
    # Insert before closing brace of oracle dict - find last ren4-numc-10 block end then continue;
    # easiest: append before the final "}" that closes INDEPENDENT_MATH_RENEWAL_ORACLE
    # Locate after ren4-prb-10 or end of ren4 entries by finding the dict end after the comment.
    anchor = '    "ren4-numc-10": (\n        "Compute 3^7.",\n        "value", "2187",\n    ),'
    if anchor not in text:
        # tolerant: insert before the blank line following the oracle's last ren4 entry by regex
        m = re.search(r'("ren4-numc-10": \(\n(?:.*?\n){3}\s*\),)', text)
        if not m:
            raise RuntimeError("could not find ren4-numc-10 oracle anchor")
        anchor = m.group(1)
        text = text.replace(anchor, anchor + "\n" + snippet, 1)
    else:
        text = text.replace(anchor, anchor + "\n" + snippet, 1)
    # Also update any check that expects only ren4 active cards via material version strings in comments is fine.
    path.write_text(text, encoding="utf-8")


def apply_renewal_module() -> None:
    path = TOOLS / "engel_curriculum_renewal.py"
    text = path.read_text(encoding="utf-8")
    # Retire current active capability/self-build/math lists by renaming before overwrite
    if "engel_capabilities_renewal_v5_20260914" in text:
        print("renewal module already at v5")
        return

    text = text.replace(
        'ENGEL_CAPABILITIES_RENEWAL_MATERIAL_VERSION = (\n    "engel_capabilities_renewal_v4_20260816"\n)',
        'ENGEL_CAPABILITIES_RENEWAL_MATERIAL_VERSION = (\n    "engel_capabilities_renewal_v5_20260914"\n)',
    )
    text = text.replace(
        'ENGEL_MATH_SCHOOL_RENEWAL_MATERIAL_VERSION = (\n    "engel_math_school_declared_renewal_v4_20260816"\n)',
        'ENGEL_MATH_SCHOOL_RENEWAL_MATERIAL_VERSION = (\n    "engel_math_school_declared_renewal_v5_20260914"\n)',
    )
    text = text.replace(
        'ENGEL_SELF_BUILD_RENEWAL_MATERIAL_VERSION = (\n    "engel_self_build_renewal_v4_20260816"\n)',
        'ENGEL_SELF_BUILD_RENEWAL_MATERIAL_VERSION = (\n    "engel_self_build_renewal_v5_20260914"\n)',
    )

    # Replace capability cards block: from "_CAPABILITY_CARDS: list" through before "_CAPABILITY_CARDS_V3_RETIRED"
    def swap_list(src: str, start_marker: str, end_marker: str, new_list_name: str, cards: list[dict], prefix_comment: str) -> str:
        start = src.index(start_marker)
        end = src.index(end_marker)
        import pprint

        body = pprint.pformat(cards, width=88, sort_dicts=False)
        # problem_ids for math cards need to stay as expressions - handled separately
        block = f"{prefix_comment}{new_list_name}: list[dict[str, Any]] = {body}\n\n"
        return src[:start] + block + src[end:]

    text = swap_list(
        text,
        "_CAPABILITY_CARDS: list[dict[str, Any]] = [",
        "_CAPABILITY_CARDS_V3_RETIRED: list[dict[str, Any]] = [",
        "_CAPABILITY_CARDS",
        CAPABILITY_CARDS_V5,
        "# v5 (2026-09-14): eight NEW capability audits over REPS, Computer Mode, humanization,\n"
        "# SLM roster gates, CT246 storage truth, Android worker independence, curriculum adoption,\n"
        "# and Wiki One stamping. Novelty is new subject matter grounded in local artifacts.\n",
    )
    text = swap_list(
        text,
        "_SELF_BUILD_CARDS: list[dict[str, Any]] = [",
        "_SELF_BUILD_CARDS_V2_RETIRED: list[dict[str, Any]] = [",
        "_SELF_BUILD_CARDS",
        SELF_BUILD_CARDS_V5,
        "# v5 (2026-09-14): eight NEW self-build reviews over Clean/Regular mode, measured\n"
        "# communication renewal, construction regeneration, weakness adoption, ren5 minting,\n"
        "# humanization skip rules, partial five-curriculum readiness, and REPS authority.\n",
    )

    # Math cards: rebuild with ren5 problem_ids programmatically as source text
    math_cards_src = '''_MATH_CARDS: list[dict[str, Any]] = [
    {
        "topic": "resolving ten newly minted equations and reductions whose declared roots invite substitution checks",
        "scenario": "Every prompt carries one specific ren5 equation or rational reduction from the ground-truth registry; the declared parameters are new, so a memorized older exercise cannot stand in for the work.",
        "constraint": "Do not soften or swap the declared equation; prove each root by substituting it back and each reduced form by expanding it again before the Result line.",
        "proof": "The exact question must resolve to its ren5-alg problem ID in tools/engel_math_problems.py and the Result must agree with the registered symbolic answer.",
        "problem_ids": [f"ren5-alg-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "differentiating and integrating ten newly minted expressions with the inverse operation as witness",
        "scenario": "The ren5 calculus set pairs polynomial and trigonometric derivatives with antiderivatives, factored limits, a second derivative, and one definite integral, all with registered symbolic truth.",
        "constraint": "Do not state a calculus result the inverse operation has not witnessed; differentiate every antiderivative back and substitute every limit's factored form.",
        "proof": "Each delivered question resolves to a decidable ren5-cal ID and its Result is compared symbolically with the registered answer.",
        "problem_ids": [f"ren5-cal-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "evaluating ten newly minted matrix computations spanning determinants, trace, rank, and eigenvalues",
        "scenario": "The ren5 linear set widens past determinants to a trace, a dot product, a matrix-vector component, a rank, eigenvalues, an inverse entry, and a squared norm, each independently registered.",
        "constraint": "Do not answer from a remembered matrix; recompute the declared entries by a second route such as cofactor expansion, elimination, or direct substitution.",
        "proof": "The exact matrix question resolves to ren5-lin ground truth and the stated quantity must match it.",
        "problem_ids": [f"ren5-lin-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "producing exact probabilities for ten newly minted draws, flips, rolls, and joint events",
        "scenario": "Fresh ren5 sample spaces cover die thresholds, coin patterns, marble draws with and without replacement, dice sums, independence, and mutually exclusive unions, all exactly fractional.",
        "constraint": "Do not answer with a decimal or a simulated estimate; enumerate or normalize the declared sample space and keep the fraction exact.",
        "proof": "Each question resolves to a decidable ren5-prb ID and its fraction is compared symbolically to declared ground truth.",
        "problem_ids": [f"ren5-prb-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "confirming ten newly minted divisor, totient, factorization, and residue computations arithmetically",
        "scenario": "The ren5 number set spans gcd, lcm, a prime factorization, a modular power, divisor counts and sums, a totient, a remainder, a next prime, and a smallest prime factor.",
        "constraint": "Do not assert a divisibility or residue claim without recomposing it on the same numbers, multiplying factors back or reducing the residue chain again.",
        "proof": "The exact question resolves to its ren5-num ID and the bounded CAS compares the Result to the registered answer.",
        "problem_ids": [f"ren5-num-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "counting ten newly minted selections, codes, committees, and word arrangements two ways",
        "scenario": "The ren5 counting set fixes small exact answers for binomial choices, shelf orders, no-repeat codes, handshakes, binary strings, a constrained committee, a repeated-letter word, polygon diagonals, and prize assignments.",
        "constraint": "Do not drift the counting convention; honor replacement, order, and distinguishability exactly as each declared question states them, and recount by a second route.",
        "proof": "Every prompt resolves to a ren5-cnt ID and the exact integer is compared to declared ground truth.",
        "problem_ids": [f"ren5-cnt-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "recomputing ten newly minted sequence terms, partial sums, and one convergent series exactly",
        "scenario": "Fresh ren5 sequences give arithmetic and geometric terms, integer sums, a finite geometric series, a Fibonacci value, a recurrence, an infinite geometric sum, a triangular number, and a sum of squares.",
        "constraint": "Do not assume an indexing convention the declared question does not state, and recompute every term chain explicitly before summing.",
        "proof": "Each exact question resolves to a ren5-seq ID and the Result is checked against its registered value.",
        "problem_ids": [f"ren5-seq-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "executing ten newly minted bounded numeric procedures whose exact rational outputs are registered",
        "scenario": "The ren5 numeric set walks a recurrence, one trapezoid application, one Babylonian step, binary and base-7 conversions, a Hamming distance, a checksum, a weighted average, a continued fraction, and one integer power.",
        "constraint": "Do not report more precision than the declared procedure produces; keep every rational output as an exact fraction and rerun the procedure as its own check.",
        "proof": "Every question resolves to a decidable ren5-numc ID and the exact Result is compared symbolically with the registry.",
        "problem_ids": [f"ren5-numc-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
]

'''
    start = text.index("_MATH_CARDS: list[dict[str, Any]] = [")
    end = text.index("_MATH_CARDS_V3_RETIRED: list[dict[str, Any]] = [")
    text = (
        text[:start]
        + "# v5 (2026-09-14): eight NEW hours over the freshly minted ren5-* problem families\n"
        + math_cards_src
        + text[end:]
    )

    path.write_text(text, encoding="utf-8")


def main() -> int:
    mint = json.loads(MINT.read_text(encoding="utf-8"))
    if int(mint.get("count") or 0) != 80:
        raise SystemExit(f"expected 80 ren5 problems, got {mint.get('count')}")

    # backups
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = ROOT / "memory" / "training" / "engel_main" / "generated" / f"v5_backup_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for rel in (
        "tools/engel_math_problems.py",
        "tools/verify_engel_curriculum_renewal.py",
        "tools/engel_curriculum_renewal.py",
    ):
        src = ROOT / rel
        shutil.copy2(src, backup_dir / src.name)

    apply_math_problems(mint["python_snippet"])
    apply_oracle(mint["oracle_snippet"])
    apply_renewal_module()

    print(
        json.dumps(
            {
                "ok": True,
                "backup_dir": str(backup_dir),
                "ren5_count": mint["count"],
                "next": [
                    "python tools/sync_engel_training_assets.py --summary",
                    "python tools/verify_engel_curriculum_renewal.py",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
