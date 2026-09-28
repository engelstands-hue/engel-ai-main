#!/usr/bin/env python3
"""D-lane (2026-07-10): GGUF-backed speculative-decoding drafter.

Wraps a small same-tokenizer model (qwen2.5-0.5b) as a llama-cpp-python
LlamaDraftModel so the CPU big lane (qwen2.5-7b + LoRA) can accept multi-token
drafts per decode step. The 0.5B proposes greedily; the 7B target verifies —
output is identical to non-speculative decoding, only faster when drafts hit.

Efficiency note: Llama.generate(reset=True) reuses the longest common prefix of
its KV cache, so each draft round only evaluates the handful of new tokens the
target just accepted — no O(n^2) re-evaluation.

Fail-open: any construction error is caught by the caller and the lane serves
without a drafter.
"""
from __future__ import annotations

import numpy as np
import numpy.typing as npt

from llama_cpp import Llama
from llama_cpp.llama_speculative import LlamaDraftModel


class GgufDraftModel(LlamaDraftModel):
    def __init__(
        self,
        model_path: str,
        num_pred_tokens: int = 5,
        n_ctx: int = 4096,
        n_threads: int = 6,
    ):
        self.llm = Llama(
            model_path=model_path,
            n_ctx=int(n_ctx),
            n_gpu_layers=0,
            n_threads=int(n_threads),
            verbose=False,
        )
        self.num_pred_tokens = max(1, int(num_pred_tokens))

    def __call__(self, input_ids: npt.NDArray[np.intc], /, **kwargs) -> npt.NDArray[np.intc]:
        try:
            out: list[int] = []
            for token in self.llm.generate(tokens=input_ids.tolist(), temp=0.0, reset=True):
                out.append(int(token))
                if len(out) >= self.num_pred_tokens:
                    break
            return np.array(out, dtype=np.intc)
        except Exception:
            # a failed draft round must never kill the target generation
            return np.array([], dtype=np.intc)
