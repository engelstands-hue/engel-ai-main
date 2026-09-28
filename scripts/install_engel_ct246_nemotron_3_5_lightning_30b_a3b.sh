#!/usr/bin/env bash
set -euo pipefail

# Install NVIDIA Nemotron 3.5 Lightning 30B-A3B (UD-Q4_K_M GGUF) onto CT246's fast SSD.
# Released by NVIDIA 2026-08-11; hybrid Mamba-2 + MoE ("nemotron_h_moe"), 30B total /
# 3B active - the same 30B-A3B shape as the already-proven qwen3-30b-a3b install.
# Mirrors scripts/install_engel_ct246_qwen3_30b_a3b_moe.sh: hostname guard, vault
# refusal, free-space check, resumable hash-verified download, receipt JSON.

if [[ "$(hostname)" != "engel-ai-main" ]]; then
  echo "Refusing model installation outside CT246 engel-ai-main" >&2
  exit 2
fi

root="/opt/engel/models-active/llm/nemotron-3.5-lightning-30b-a3b"
model="$root/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf"
partial="$model.partial"
receipt="/opt/engel/memory/models/ENGEL_NEMOTRON_3_5_LIGHTNING_30B_A3B_INSTALL.json"
# LFS oid from the HF API tree listing (2026-08-13); the download is refused unless
# the bytes hash to exactly this.
sha256="edcb5d4650796ed2fb412498de6f83b585862312c747ddb74f0ea04b22206181"
expected_bytes="25266255936"
url="https://huggingface.co/unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF/resolve/main/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf"

target_source="$(findmnt -n -o SOURCE -T /opt/engel)"
target_path="$(findmnt -n -o TARGET -T /opt/engel)"
case "${target_source,,} ${target_path,,}" in
  *engel-vault*|*powervault*|*/mnt/engel-vault*)
    echo "Refusing PowerVault/external-array model target" >&2
    exit 3
    ;;
esac

available_bytes="$(df --output=avail -B1 /opt/engel | tail -1 | tr -d ' ')"
required_bytes=$((30 * 1024 * 1024 * 1024))
if (( available_bytes < required_bytes )) && [[ ! -f "$model" ]]; then
  echo "Need at least 30 GiB free on CT246 SSD before download" >&2
  exit 4
fi

mkdir -p "$root" "$(dirname "$receipt")"
if [[ -f "$model" ]]; then
  observed="$(sha256sum "$model" | awk '{print $1}')"
  if [[ "$observed" != "$sha256" ]]; then
    echo "Existing model hash mismatch; refusing overwrite" >&2
    exit 5
  fi
else
  curl \
    --fail \
    --location \
    --continue-at - \
    --retry 8 \
    --retry-all-errors \
    --connect-timeout 20 \
    --output "$partial" \
    "$url"
  observed="$(sha256sum "$partial" | awk '{print $1}')"
  if [[ "$observed" != "$sha256" ]]; then
    echo "Downloaded model hash mismatch" >&2
    exit 6
  fi
  mv "$partial" "$model"
fi

chmod 0640 "$model"
observed_bytes="$(stat -c '%s' "$model")"
if [[ "$observed_bytes" != "$expected_bytes" ]]; then
  echo "Model size mismatch: $observed_bytes != $expected_bytes" >&2
  exit 7
fi

cat > "$receipt" <<EOF
{
  "schema": "engel_model_install_receipt_v1",
  "installed_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "model_family": "NVIDIA Nemotron 3.5 Lightning",
  "model_release_date": "2026-08-11",
  "architecture": "nemotron_h_moe (hybrid Mamba-2 + MoE, 30B total / 3B active)",
  "quant": "UD-Q4_K_M",
  "path": "$model",
  "size_bytes": $observed_bytes,
  "sha256": "$observed",
  "source_url": "$url",
  "license": "OpenMDW License Agreement v1.1",
  "recommended_sampling": {"temperature": 1.0, "top_p": 0.95},
  "runtime_note": "Brand-new arch: verify llama-cpp-python/llama.cpp on this host actually supports nemotron_h_moe before wiring into any lane.",
  "wired_into_chat": false
}
EOF

echo "INSTALL_OK $model"
sha256sum "$model"
