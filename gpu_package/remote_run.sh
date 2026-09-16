#!/bin/bash
# Remote execution script for GPU embedding baseline
set -e

# Use HF mirror for Chinese network
export HF_ENDPOINT=https://hf-mirror.com

echo "=== Portraiture GPU Embedding Baseline ==="
echo "Started: $(date)"
echo "Host: $(hostname)"

cd /root/portraiture_gpu/gpu_package

# Check environment
echo ""
echo "--- Environment ---"
python3 -c 'import torch; print("PyTorch:", torch.__version__); print("CUDA:", torch.cuda.is_available()); print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none")'
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || true

# Run benchmark
echo ""
echo "--- Running embedding baseline ---"
python3 run_embedding.py

echo ""
echo "--- Results ---"
ls -la results/
cat results/summary.md

echo ""
echo "=== Done: $(date) ==="
