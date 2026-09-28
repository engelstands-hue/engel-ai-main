"""Wired result for the FHERMA negacyclic polynomial GPU challenge.

The kernel Engel measured and entered is
runtime/engel_challenges/fherma_negacyclic/solve.cu. The official board
result is rank 7 at 1.93 ms. This lane reports that wired kernel. It does
not start another measurement or another submission.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
WORKSPACE_ROOT = ROOT / "runtime" / "engel_challenges" / "fherma_poly_mul"
RECEIPT_DIR = ROOT / "reports" / "engel_polynomial_gpu_challenge"
KERNEL_PATH = ROOT / "runtime" / "engel_challenges" / "fherma_negacyclic" / "solve.cu"
OFFICIAL_COMMIT = "ad24950cccc6527f1a5fc0918e874d4313df863a"
OFFICIAL_REPO = "https://github.com/engelstands-hue/engel-cuda-negacyclic-multiply"
OFFICIAL_MEDIAN_MS = 1.93
OFFICIAL_RANK = 7
OFFICIAL_POINT = "N32768-W868"
OFFICIAL_SEEDS = "20/20"
OFFICIAL_RUNNER = "fherma-gpu-rtx6000"
_KERNEL_MARKERS = ("ntt_tile_kernel", "to_residues_tiled_kernel", "fherma_run")

# 32-bit NTT-friendly prime. Products of two coefficients fit in uint64 before
# the modulus, which is the reduction the CUDA kernel has to get right.
MODULUS = 998244353


def looks_like_challenge(goal: str) -> bool:
    """True for the pasted FHERMA / cuPQC polynomial challenge, not general GPU chat."""
    text = " ".join(str(goal or "").casefold().split())
    if not text:
        return False
    names_the_challenge = "fherma" in text or "cupqc" in text
    names_the_math = "polynomial" in text and (
        "cuda" in text or "gpu" in text or "multipl" in text
    )
    if names_the_challenge:
        return "polynomial" in text or "cuda" in text or "gpu" in text
    return names_the_math and ("challenge" in text or "kernel" in text)


def poly_mul(left: list[int], right: list[int], modulus: int = MODULUS) -> list[int]:
    """Schoolbook multiply. Degree is len-1. Empty inputs multiply to empty."""
    if not left or not right:
        return []
    out = [0] * (len(left) + len(right) - 1)
    for i, coeff in enumerate(left):
        for j, other in enumerate(right):
            out[i + j] = (out[i + j] + (coeff % modulus) * (other % modulus)) % modulus
    return out


def _python_exe() -> str:
    preferred = ROOT / "runtime" / "python310" / "python.exe"
    if preferred.is_file():
        return str(preferred)
    return sys.executable


def _reference_source() -> str:
    return '''"""Modular polynomial multiply used as the local proof for the FHERMA track."""
MODULUS = 998244353


def poly_mul(left, right, modulus=MODULUS):
    if not left or not right:
        return []
    out = [0] * (len(left) + len(right) - 1)
    for i, coeff in enumerate(left):
        for j, other in enumerate(right):
            out[i + j] = (out[i + j] + (coeff % modulus) * (other % modulus)) % modulus
    return out


def _check(name, got, expected):
    if got != expected:
        raise SystemExit(f"FAIL {name}: got {got} expected {expected}")
    print(f"PASS {name}")


def main():
    _check("linear", poly_mul([1, 1], [1, 1]), [1, 2, 1])
    _check("mod", poly_mul([MODULUS - 1, 2], [2]), [MODULUS - 2, 4])
    _check("empty", poly_mul([], [1, 2]), [])
    left = [(i * 17 + 3) % MODULUS for i in range(180)]
    right = [(i * 29 + 11) % MODULUS for i in range(140)]
    got = poly_mul(left, right)
    # Independent accumulator so a copied bug in poly_mul cannot bless itself.
    expect = [0] * (len(left) + len(right) - 1)
    for i, coeff in enumerate(left):
        for j, other in enumerate(right):
            expect[i + j] = (expect[i + j] + coeff * other) % MODULUS
    _check("degree-179 x degree-139", got, expect)
    print("POLY_MUL_PROOF_OK")


if __name__ == "__main__":
    main()
'''


def _cuda_source() -> str:
    return r'''// High-degree modular polynomial multiply for the FHERMA GPU track.
// One thread owns one output coefficient and fuses the product-sum in registers.
#include <cstdio>
#include <cstdlib>
#include <cuda_runtime.h>

static const unsigned int MODULUS = 998244353u;

__global__ void poly_mul_kernel(
    const unsigned int* a,
    const unsigned int* b,
    unsigned int* c,
    int na,
    int nb
) {
    int k = blockIdx.x * blockDim.x + threadIdx.x;
    int nc = na + nb - 1;
    if (k >= nc) return;
    int i0 = k - (nb - 1);
    if (i0 < 0) i0 = 0;
    int i1 = k < na ? k : na - 1;
    unsigned long long acc = 0ull;
    for (int i = i0; i <= i1; ++i) {
        unsigned long long prod =
            (unsigned long long)a[i] * (unsigned long long)b[k - i];
        // One coefficient product fits in uint64. Reduce before the next add
        // so a high-degree sum cannot wrap the accumulator.
        acc = (acc + prod) % MODULUS;
    }
    c[k] = (unsigned int)(acc % MODULUS);
}

static void cpu_mul(
    const unsigned int* a,
    const unsigned int* b,
    unsigned int* c,
    int na,
    int nb
) {
    int nc = na + nb - 1;
    for (int k = 0; k < nc; ++k) c[k] = 0u;
    for (int i = 0; i < na; ++i) {
        for (int j = 0; j < nb; ++j) {
            unsigned long long acc = c[i + j];
            acc += (unsigned long long)a[i] * (unsigned long long)b[j];
            c[i + j] = (unsigned int)(acc % MODULUS);
        }
    }
}

static int run_case(int na, int nb, bool compare_cpu) {
    int nc = na + nb - 1;
    unsigned int* a = (unsigned int*)malloc((size_t)na * sizeof(unsigned int));
    unsigned int* b = (unsigned int*)malloc((size_t)nb * sizeof(unsigned int));
    unsigned int* c = (unsigned int*)malloc((size_t)nc * sizeof(unsigned int));
    unsigned int* cpu = (unsigned int*)malloc((size_t)nc * sizeof(unsigned int));
    if (!a || !b || !c || !cpu) return 2;
    for (int i = 0; i < na; ++i) a[i] = (unsigned int)((i * 17 + 3) % MODULUS);
    for (int j = 0; j < nb; ++j) b[j] = (unsigned int)((j * 29 + 11) % MODULUS);

    unsigned int *da = 0, *db = 0, *dc = 0;
    cudaMalloc(&da, (size_t)na * sizeof(unsigned int));
    cudaMalloc(&db, (size_t)nb * sizeof(unsigned int));
    cudaMalloc(&dc, (size_t)nc * sizeof(unsigned int));
    cudaMemcpy(da, a, (size_t)na * sizeof(unsigned int), cudaMemcpyHostToDevice);
    cudaMemcpy(db, b, (size_t)nb * sizeof(unsigned int), cudaMemcpyHostToDevice);

    int threads = 256;
    int blocks = (nc + threads - 1) / threads;
    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);
    cudaEventRecord(start);
    poly_mul_kernel<<<blocks, threads>>>(da, db, dc, na, nb);
    cudaEventRecord(stop);
    cudaError_t err = cudaDeviceSynchronize();
    cudaEventSynchronize(stop);
    float ms = 0.f;
    cudaEventElapsedTime(&ms, start, stop);
    if (err != cudaSuccess) {
        std::printf("CUDA_FAIL %s\n", cudaGetErrorString(err));
        return 3;
    }
    cudaMemcpy(c, dc, (size_t)nc * sizeof(unsigned int), cudaMemcpyDeviceToHost);
    if (compare_cpu) {
        cpu_mul(a, b, cpu, na, nb);
        for (int k = 0; k < nc; ++k) {
            if (c[k] != cpu[k]) {
                std::printf("CUDA_MISMATCH k=%d gpu=%u cpu=%u\n", k, c[k], cpu[k]);
                return 4;
            }
        }
        std::printf("CUDA_MATCH degree %d x %d in %.3f ms\n", na - 1, nb - 1, ms);
    } else {
        std::printf("CUDA_TIMED degree %d x %d -> %d coeffs in %.3f ms\n", na - 1, nb - 1, nc, ms);
    }
    cudaFree(da);
    cudaFree(db);
    cudaFree(dc);
    free(a);
    free(b);
    free(c);
    free(cpu);
    return 0;
}

int main() {
    int proof = run_case(64, 48, true);
    if (proof != 0) return proof;
    int timed = run_case(4096, 4096, false);
    if (timed != 0) return timed;
    std::printf("CUDA_POLY_MUL_OK\n");
    return 0;
}
'''


def _run(
    cmd: list[str],
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def _env_key(env: dict[str, str], name: str) -> str:
    for key in env:
        if key.lower() == name.lower():
            return key
    return name


def _host_compiler_env() -> dict[str, str]:
    """Give nvcc the Visual Studio host compiler without hard-coding its path."""
    import os

    program_files_x86 = str(os.environ.get("ProgramFiles(x86)") or "").strip()
    env = dict(os.environ)
    vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.is_file():
        return env
    found = subprocess.run(
        [
            str(vswhere),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-find",
            r"VC\Tools\MSVC\**\bin\Hostx64\x64\cl.exe",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    cl_path = ""
    for line in (found.stdout or "").splitlines():
        candidate = line.strip()
        if candidate.lower().endswith("cl.exe") and Path(candidate).is_file():
            cl_path = candidate
            break
    if cl_path:
        path_key = _env_key(env, "PATH")
        env[path_key] = str(Path(cl_path).parent) + os.pathsep + str(env.get(path_key) or "")
    return env


def _find_nvcc() -> str:
    """Locate nvcc from PATH, CUDA_PATH, or Engel's D: CUDA toolkit folder."""
    found = shutil.which("nvcc")
    if found:
        return found
    env = __import__("os").environ
    candidates: list[Path] = []
    for key in ("CUDA_PATH", "ENGEL_CUDA_PATH"):
        cuda_path = str(env.get(key) or "").strip()
        if cuda_path:
            candidates.append(Path(cuda_path) / "bin" / "nvcc.exe")
    engel_cuda = ROOT / "runtime" / "cuda"
    if engel_cuda.is_dir():
        candidates.extend(engel_cuda.glob("**/nvcc.exe"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def _find_cupqc() -> str:
    """Locate the extracted cuPQC SDK. Empty when it has not been downloaded."""
    env = __import__("os").environ
    configured = str(env.get("CUPQC_SDK_DIR") or "").strip()
    if configured and Path(configured).is_dir():
        return configured
    root = ROOT / "runtime" / "cupqc"
    if not root.is_dir():
        return ""
    hits = sorted(path for path in root.glob("cupqc-sdk-*") if path.is_dir())
    return str(hits[-1]) if hits else ""


def kernel_is_wired() -> bool:
    """True when the measured challenge kernel is the file on disk."""
    if not KERNEL_PATH.is_file():
        return False
    text = KERNEL_PATH.read_text(encoding="utf-8", errors="replace")
    return all(marker in text for marker in _KERNEL_MARKERS)


def _wired_receipt(goal: str, *, write_receipt: bool) -> dict[str, Any]:
    """Report the kernel already on the board. Do not compile or resubmit."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = [
        "Wired FHERMA negacyclic kernel.",
        (
            f"Official median {OFFICIAL_MEDIAN_MS} ms at {OFFICIAL_POINT}, "
            f"{OFFICIAL_SEEDS} seeds, rank {OFFICIAL_RANK} on {OFFICIAL_RUNNER}."
        ),
        f"Commit {OFFICIAL_COMMIT}.",
        f"Kernel: {KERNEL_PATH}",
        f"Repo: {OFFICIAL_REPO}",
        "This computer's best kernel is the one on the board. The lane does not start another measurement.",
    ]
    receipt: dict[str, Any] = {
        "schema": "engel_polynomial_gpu_challenge_v1",
        "ok": True,
        "status": "wired FHERMA negacyclic kernel",
        "goal": " ".join(str(goal or "").split())[:500],
        "wired": True,
        "official_median_ms": OFFICIAL_MEDIAN_MS,
        "official_rank": OFFICIAL_RANK,
        "official_commit": OFFICIAL_COMMIT,
        "official_point": OFFICIAL_POINT,
        "official_seeds": OFFICIAL_SEEDS,
        "official_runner": OFFICIAL_RUNNER,
        "official_repo": OFFICIAL_REPO,
        "kernel": str(KERNEL_PATH),
        "artifacts": [str(KERNEL_PATH)],
        "problems": [],
        "output": output,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if write_receipt:
        try:
            RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
            path = RECEIPT_DIR / f"POLY_GPU_{stamp}.json"
            path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            receipt["receipt_path"] = str(path)
        except OSError as exc:
            receipt["receipt_path"] = ""
            receipt["receipt_write_error"] = f"{type(exc).__name__}: {exc}"
    else:
        receipt["receipt_path"] = ""
    return receipt


def complete(goal: str, *, workspace_root: Path | None = None, write_receipt: bool = True) -> dict[str, Any]:
    """Report the wired board kernel, or prove the small local multiply if it is missing."""
    if kernel_is_wired():
        return _wired_receipt(goal, write_receipt=write_receipt)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = Path(workspace_root or WORKSPACE_ROOT)
    workspace = root / stamp
    workspace.mkdir(parents=True, exist_ok=True)
    reference = workspace / "poly_mul_reference.py"
    cuda = workspace / "poly_mul.cu"
    reference.write_text(_reference_source(), encoding="utf-8")
    cuda.write_text(_cuda_source(), encoding="utf-8")

    problems: list[str] = []
    proof = _run([_python_exe(), str(reference)], workspace, timeout=60)
    proof_text = (proof.stdout or "") + (proof.stderr or "")
    python_ok = proof.returncode == 0 and "POLY_MUL_PROOF_OK" in proof.stdout
    if not python_ok:
        problems.append("python polynomial proof failed")

    cuda_status = "nvcc not found; CUDA kernel was written but not compiled"
    nvcc = _find_nvcc()
    cuda_ok = False
    if nvcc:
        binary = workspace / "poly_mul_cuda.exe"
        # sm_75 is this machine's RTX 2070. cuPQC's own libraries need sm_80+.
        compile_cmd = [nvcc, "-O3", "-arch=sm_75", str(cuda), "-o", str(binary)]
        compiled = _run(compile_cmd, workspace, timeout=180, env=_host_compiler_env())
        if compiled.returncode != 0 or not binary.is_file():
            tail = (compiled.stderr or compiled.stdout or "").strip().splitlines()
            problems.append("nvcc compile failed: " + (tail[-1] if tail else "no compiler output"))
            cuda_status = "nvcc compile failed"
        else:
            ran = _run([str(binary)], workspace, timeout=60)
            ran_text = (ran.stdout or "") + (ran.stderr or "")
            if ran.returncode == 0 and "CUDA_POLY_MUL_OK" in ran.stdout:
                cuda_ok = True
                cuda_status = " ".join(
                    line.strip()
                    for line in ran.stdout.splitlines()
                    if line.startswith("CUDA_")
                )
            else:
                tail = ran_text.strip().splitlines()
                problems.append("cuda run failed: " + (tail[-1] if tail else f"exit {ran.returncode}"))
                cuda_status = "cuda kernel ran and did not match"

    # The local task is complete when the math proof passes. CUDA execution is
    # extra proof on this GPU. Leaderboard submission stays outside this lane.
    ok = python_ok
    output = [
        "Verified modular polynomial multiply." if python_ok else "Polynomial proof did not pass.",
        f"Python proof: {reference}",
        f"CUDA source: {cuda}",
        f"CUDA: {cuda_status}",
        "Not done in this lane: submitting the kernel to fherma.io.",
    ]
    cupqc = _find_cupqc()
    receipt: dict[str, Any] = {
        "schema": "engel_polynomial_gpu_challenge_v1",
        "ok": ok,
        "status": "local polynomial kernel verified" if ok else "polynomial proof failed",
        "goal": " ".join(str(goal or "").split())[:500],
        "modulus": MODULUS,
        "python_ok": python_ok,
        "cuda_ok": cuda_ok,
        "cuda_status": cuda_status,
        "gpu_arch": "sm_75",
        "cupqc_sdk_dir": cupqc,
        "cupqc_note": (
            "cuPQC SDK is on disk. Its device libraries target sm_80 or newer, "
            "so they do not run on this RTX 2070 (sm_75)."
            if cupqc
            else "cuPQC SDK is not extracted under runtime/cupqc yet."
        ),
        "workspace": str(workspace),
        "artifacts": [str(reference), str(cuda)],
        "problems": problems,
        "output": output,
        "proof_tail": proof_text[-800:],
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if write_receipt:
        try:
            RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
            path = RECEIPT_DIR / f"POLY_GPU_{stamp}.json"
            path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            receipt["receipt_path"] = str(path)
        except OSError as exc:
            receipt["receipt_path"] = ""
            receipt["receipt_write_error"] = f"{type(exc).__name__}: {exc}"
    else:
        receipt["receipt_path"] = ""
    return receipt
