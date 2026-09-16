#!/bin/bash
# Portraiture GPU Embedding Baseline
# Run on GPU server

set -e

echo "=== Portraiture GPU Embedding Baseline ==="
echo "Started: $(date)"

# Check Python
python --version
pip --version

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -q

# Verify GPU
python -c "
import torch
print(f'PyTorch {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'CUDA version: {torch.version.cuda}')
"

# Run embedding baseline
echo "Running embedding baseline..."
python run_embedding.py 2>&1 | tee run.log

echo "=== Done: $(date) ==="
echo "Results in results/"
