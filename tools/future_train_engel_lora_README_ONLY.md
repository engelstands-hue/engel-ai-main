# Future Train Engel LoRA Runbook - README ONLY

DO NOT RUN YET.
DO NOT RUN WITHOUT EXPLICIT APPROVAL:
APPROVE_ENGEL_LOCAL_LLM_LORA_TRAINING_RUN_V1

This file is documentation only. It is not executable and does not authorize training, downloads, installs, runtime use, provider calls, or deployment.

## Future Hardware Checklist

- Confirm CPU model, RAM, GPU, and VRAM.
- Confirm available disk space for dataset, cache, base model, adapter output, and checkpoints.
- Confirm cooling and power stability for the expected run time.
- Stop if hardware is insufficient.

## Future Environment Setup After Approval

Documentation-only example:

```powershell
# DO NOT RUN YET. Approval required first.
python -m venv .venv-training
.\.venv-training\Scripts\Activate.ps1
```

## Future Package Install Section After Approval

Documentation-only example:

```powershell
# DO NOT RUN YET. Approval required first.
# Example only: install the reviewed training stack after approval.
python -m pip install transformers trl peft accelerate datasets
```

## Future Model Choice Checklist

- Start with Qwen2.5-0.5B class if hardware is limited.
- Consider Qwen2.5-1.5B or 3B only if memory and time allow.
- Treat 7B class as later, heavier, and riskier.
- Confirm license and local file presence.
- Do not download without approval.

## Future Dataset Preparation Command

Documentation-only example:

```powershell
# Safe prep command, not training.
python .\tools\prepare_local_llm_training_dataset.py
python .\tools\verify_local_llm_training_prep.py
```

## Future LoRA Or QLoRA Training Placeholder

Documentation-only placeholder:

```powershell
# DO NOT RUN YET. Approval required first.
python .\tools\future_train_engel_lora.py --model <local-base-model-path> --dataset .\data\local_llm_training\prepared\engel_customer_sft_candidate_v1.jsonl --adapter-out .\models\adapters\engel-style-lora-v1
```

## Future Evaluation Placeholder

Documentation-only placeholder:

```powershell
# DO NOT RUN YET. Approval required first.
python .\tools\future_eval_engel_adapter.py --base <local-base-model-path> --adapter .\models\adapters\engel-style-lora-v1 --prompts .\data\local_llm_training\engel_training_eval_prompts_v1.jsonl
```

## Future Adapter Export Placeholder

Documentation-only placeholder:

```powershell
# DO NOT RUN YET. Approval required first.
python .\tools\future_export_engel_adapter.py --adapter .\models\adapters\engel-style-lora-v1 --manifest .\models\adapters\engel-style-lora-v1\manifest.json
```

## Adapter Merge Warning

Do not merge an adapter into a base model automatically. Any merge requires evaluation, backup, changelog, rollback plan, and separate human approval.

## Future Rollback Plan

- Keep the base model unchanged.
- Store adapter output separately.
- Keep training config, dataset manifest, and eval report.
- If evaluation fails, quarantine the adapter and do not deploy it.

## Future Promotion Checklist

- Evaluation passes rubric.
- Customer-readiness review passes.
- Prompt-injection checks pass.
- Planned-vs-active honesty passes.
- Human approval recorded.
- Backup and rollback ready.
- No trusted-memory write from model output.
