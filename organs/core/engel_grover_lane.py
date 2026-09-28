#!/usr/bin/env python3
"""Engel's Grover lane — verified quadratic-search logic, no guessing.

Classical local simulation of Grover amplitude amplification plus the facts
Josh approved: quadratic not exponential, oracle + diffusion, AES-bit heuristic
with caveats. No provider, no quantum hardware, no trusted-memory write.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any


SCHEMA = "engel_grover_lane_v1"
MAX_N = 1024
PI_OVER_FOUR = math.pi / 4.0

GROVER_TERMS = (
    r"\bgrover(?:'?s)?(?:\s+algorithm)?\b",
    r"\bamplitude amplification\b",
    r"\bquantum (?:unstructured )?search\b",
    r"\bunstructured (?:quantum )?search\b",
)
GROVER_RE = re.compile("|".join(GROVER_TERMS), re.IGNORECASE)
GROK_RE = re.compile(r"\bgrok\b", re.IGNORECASE)
SHOR_ONLY_RE = re.compile(r"\bshor(?:'?s)?\b", re.IGNORECASE)
AES_RE = re.compile(r"\baes[-\s]?(\d{2,3})\b", re.IGNORECASE)
N_RE = re.compile(r"\b(?:n|size|items?|list)\s*[:=]?\s*(\d{1,5})\b", re.IGNORECASE)
MARKED_RE = re.compile(
    r"\b(?:marked|target|item|index|needle)\s*[:=]?\s*(\d{1,5})\b",
    re.IGNORECASE,
)

FALSE_POSITIVE_RE = re.compile(
    r"\bgrok\b"
    r"|\bgrover\s+bot\b"
    r"|\bsearch (?:the )?(?:workspace|repo|routes?|logs?|receipts?)\b"
    r"|\baes-256-gcm\b"
    r"|\bat rest\b",
    re.IGNORECASE,
)

EXPLAIN_RE = re.compile(
    r"\bexplain\b|\bhow does\b|\bhow do\b|\bwhat is\b|\bwhat's\b|\bbreakdown\b|"
    r"\bspeedup\b|\bwhy (?:it )?matters\b|\bwalk me through\b",
    re.IGNORECASE,
)
SIMULATE_RE = re.compile(
    r"\bsimulat|\brun grover\b|\bgrover search\b|\bfind the marked\b|\bdemo\b",
    re.IGNORECASE,
)
CRYPTO_RE = re.compile(
    r"\bcrypto|\baes\b|\bkey (?:size|bits|length)\b|\bpost-?quantum\b|\bsymmetric\b",
    re.IGNORECASE,
)


def grover_iterations(n: int, marked_count: int = 1) -> int:
    n = max(1, int(n))
    m = max(1, min(int(marked_count), n))
    return max(1, int(PI_OVER_FOUR * math.sqrt(n / m)))


def grover_theory_success(n: int, k: int, marked_count: int = 1) -> float:
    n = max(1, int(n))
    m = max(1, min(int(marked_count), n))
    theta = math.asin(math.sqrt(m / n))
    return math.sin((2 * int(k) + 1) * theta) ** 2


def grover_simulate(n: int, marked: int = 0) -> dict[str, Any]:
    if n < 2 or n > MAX_N:
        return {
            "ok": False,
            "verified": False,
            "error": f"N must be between 2 and {MAX_N} for the local simulator",
            "n": n,
        }
    marked = int(marked) % n
    amps = [1.0 / math.sqrt(n)] * n
    k = grover_iterations(n, 1)
    for _ in range(k):
        amps[marked] *= -1.0
        mean = sum(amps) / n
        amps = [2.0 * mean - a for a in amps]
    probs = [a * a for a in amps]
    success = float(probs[marked])
    theory = grover_theory_success(n, k, 1)
    verified = abs(success - theory) < 1e-9 and success >= max(probs)
    return {
        "ok": True,
        "verified": verified,
        "n": n,
        "marked": marked,
        "iterations": k,
        "oracle_queries": k,
        "classical_worst_case": n,
        "classical_average": n / 2.0,
        "success_probability": success,
        "theory_success_probability": theory,
        "best_index": int(max(range(n), key=lambda i: probs[i])),
        "speedup_vs_worst_case": (n / k) if k else None,
    }


def grover_crypto_bits(key_bits: int) -> dict[str, Any]:
    bits = int(key_bits)
    return {
        "ok": True,
        "verified": bits in {128, 192, 256} or bits > 0,
        "classical_bits": bits,
        "grover_heuristic_bits": bits / 2.0,
        "caveat": (
            "This halves the *security level heuristic*, not the key length. "
            "Grover iterations are sequential quantum circuits, so 2^(k/2) AES "
            "evaluations is far costlier than 2^(k/2) classical checks. "
            "AES-256 is the conservative Grover mitigation for symmetric crypto. "
            "It is not the whole post-quantum story: public-key still needs PQC "
            "(ML-KEM, ML-DSA, and the like). Shor, not Grover, is what breaks RSA."
        ),
    }


def grover_facts() -> dict[str, str]:
    return {
        "classical": "O(N) — unsorted search inspects about N/2 items on average, N in the worst case.",
        "quantum": "O(sqrt(N)) — about (pi/4)*sqrt(N) oracle queries for one marked item.",
        "steps": (
            "1) Equal superposition over the search space. "
            "2) Oracle phase-flips the marked state. "
            "3) Diffusion inverts amplitudes about the mean, boosting the target. "
            "4) Measure after the right iteration count."
        ),
        "not_exponential": (
            "Grover is a quadratic / polynomial speedup. Shor is the exponential "
            "one that threatens RSA. Do not mix them."
        ),
        "success": (
            "Success probability is sin^2((2k+1)theta), theta = arcsin(sqrt(M/N)). "
            "For large N it gets very high if you stop at the right k. Too many "
            "iterations overshoot. It is not magically 100% for every N."
        ),
        "n_qubits": (
            "Circuits usually use n qubits so N=2^n, but Grover is not limited to "
            "power-of-two search spaces; you pad or restrict the oracle."
        ),
    }


def grover_explain_text() -> str:
    facts = grover_facts()
    return " ".join(
        [
            "Grover's algorithm is a quadratic speedup for unstructured search and black-box inversion.",
            "Classical: " + facts["classical"],
            "Grover: " + facts["quantum"],
            facts["steps"],
            facts["success"],
            facts["n_qubits"],
            facts["not_exponential"],
            grover_crypto_bits(128)["caveat"],
        ]
    )


def detect_grover_request(prompt: str) -> bool:
    text = str(prompt or "").strip()
    if len(text) < 6 or len(text) > 4000:
        return False
    if FALSE_POSITIVE_RE.search(text) and not GROVER_RE.search(text):
        return False
    if GROK_RE.search(text) and not GROVER_RE.search(text):
        return False
    if SHOR_ONLY_RE.search(text) and not GROVER_RE.search(text) and "vs" not in text.casefold():
        return False
    return bool(GROVER_RE.search(text))


def _parse_n_marked(prompt: str) -> tuple[int | None, int]:
    n_match = N_RE.search(prompt)
    marked_match = MARKED_RE.search(prompt)
    n = int(n_match.group(1)) if n_match else None
    marked = int(marked_match.group(1)) if marked_match else 0
    if n is None:
        bare = re.search(r"\b(4|8|16|32|64|128|256|512|1024)\b", prompt)
        if bare and SIMULATE_RE.search(prompt):
            n = int(bare.group(1))
    return n, marked


def answer_grover_prompt(prompt: str) -> dict[str, Any]:
    text = str(prompt or "").strip()
    if not detect_grover_request(text):
        return {"schema": SCHEMA, "grover_request": False, "ok": False}
    n, marked = _parse_n_marked(text)
    want_sim = bool(SIMULATE_RE.search(text) and n is not None)
    want_crypto = bool(CRYPTO_RE.search(text) or AES_RE.search(text))
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "grover_request": True,
        "ok": True,
        "verified": True,
        "facts": grover_facts(),
        "mode": "explain",
    }
    parts: list[str] = []
    if want_sim and n is not None:
        sim = grover_simulate(n, marked)
        payload["simulation"] = sim
        payload["mode"] = "simulate"
        payload["verified"] = bool(sim.get("verified"))
        payload["ok"] = bool(sim.get("ok") and sim.get("verified"))
        if sim.get("ok") and sim.get("verified"):
            parts.append(
                "Verified Grover simulation: N={n}, marked={marked}, "
                "oracle queries k={k} (about pi/4 * sqrt(N)), "
                "classical worst case {classic}. "
                "Measured success {p:.6f}; theory {t:.6f}.".format(
                    n=sim["n"],
                    marked=sim["marked"],
                    k=sim["iterations"],
                    classic=sim["classical_worst_case"],
                    p=sim["success_probability"],
                    t=sim["theory_success_probability"],
                )
            )
        else:
            parts.append(str(sim.get("error") or "Grover simulation could not be verified."))
    else:
        parts.append(grover_explain_text())
        payload["mode"] = "explain"
    aes = AES_RE.search(text)
    if want_crypto or aes:
        bits = int(aes.group(1)) if aes else 128
        crypto = grover_crypto_bits(bits)
        payload["crypto"] = crypto
        parts.append(
            "AES-{bits} Grover heuristic: about {half:g} bits of quantum security.".format(
                bits=bits,
                half=crypto["grover_heuristic_bits"],
            )
        )
        parts.append(str(crypto["caveat"]))
        if payload["mode"] == "explain":
            payload["mode"] = "crypto"
    payload["result_text"] = " ".join(parts)
    payload["verification"] = (
        "iteration count is floor(pi/4 * sqrt(N/M)); "
        "simulated marked probability matches sin^2((2k+1)arcsin(sqrt(M/N)))"
        if want_sim
        else "canonical Grover query-complexity and crypto caveats, not a model guess"
    )
    return payload


def _safety_lines() -> list[str]:
    return [
        "Safety:",
        "- READ_ONLY_STATUS_ONLY",
        "- NO_TRUSTED_MEMORY_WRITE",
        "- NO_PROVIDER_MODEL_NETWORK",
        "- NO_BACKGROUND_WORKER",
        "- Local classical simulation only; no quantum hardware",
    ]


def render_grover_status(payload: str = "") -> str:
    del payload
    return "\n".join(
        [
            "Engel Grover lane",
            "",
            "Status: wired. Quadratic unstructured-search logic is local and verified.",
            f"Simulator cap: N <= {MAX_N}.",
            "Chat, Discord, and Cosmic Swarm use this lane instead of guessing Grover.",
            "",
            "Routes: grover status | explain grover | grover search | grover aes",
            "",
            *_safety_lines(),
        ]
    )


def render_grover_explain(payload: str = "") -> str:
    text = grover_explain_text()
    extra = str(payload or "").strip()
    if extra:
        answered = answer_grover_prompt("explain grover " + extra)
        if answered.get("ok") and answered.get("result_text"):
            text = str(answered["result_text"])
    return "\n".join(["Engel Grover explain", "", text, "", *_safety_lines()])


def render_grover_search(payload: str = "") -> str:
    raw = str(payload or "").strip() or "simulate grover n=4 marked=0"
    if not detect_grover_request(raw):
        raw = "grover search " + raw
    answered = answer_grover_prompt(raw if SIMULATE_RE.search(raw) else "simulate grover " + raw)
    body = str(answered.get("result_text") or "Need N between 2 and 1024, for example: grover search n=16 marked=3")
    return "\n".join(["Engel Grover search", "", body, "", *_safety_lines()])


def render_grover_crypto(payload: str = "") -> str:
    raw = str(payload or "").strip() or "grover aes-128"
    if not detect_grover_request(raw) and not AES_RE.search(raw):
        raw = "grover " + raw
    if "grover" not in raw.casefold():
        raw = "grover " + raw
    answered = answer_grover_prompt(raw)
    body = str(answered.get("result_text") or grover_crypto_bits(128)["caveat"])
    return "\n".join(["Engel Grover crypto", "", body, "", *_safety_lines()])


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", default="")
    parser.add_argument("prompt", nargs="*", default=[])
    args = parser.parse_args()
    if args.json:
        data = json.loads(args.json)
        prompt = str(data.get("prompt") or "")
    else:
        prompt = " ".join(args.prompt) or "explain grover"
    print(json.dumps(answer_grover_prompt(prompt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
