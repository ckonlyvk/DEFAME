# ViFactCheck Benchmark Setup

## Overview

This directory contains the evaluation script for running the ViFactCheck benchmark using DEFAME's Vietnamese-optimized fact-checking procedure.

## Quick Start

1. **Install dependencies** (if not already installed):
   ```bash
   pip install datasets
   ```

2. **Run evaluation**:
   ```bash
   cd /Users/luuthienduc/Documents/GitHub/DEFAME/scripts/vifactcheck
   python evaluate.py
   ```

## Configuration

The evaluation script (`evaluate.py`) is configured with:

- **Benchmark**: `vifactcheck` (loads from HuggingFace: `tranthaihoa/vifactcheck`)
- **Procedure**: `qa_based/vifactcheck` (Vietnamese-optimized QA-based fact-checking)
- **Dataset Split**: `test` (can be changed to `train` or `dev`)
- **Sample Size**: 5 (for initial testing, increase for full evaluation)
- **Workers**: 1 (single worker for testing, increase for faster processing)

## Dataset Information

- **Source**: [tranthaihoa/vifactcheck](https://huggingface.co/datasets/tranthaihoa/vifactcheck) on Hugging Face
- **Size**: 7,232 claim-evidence pairs
- **Language**: Vietnamese
- **Domains**: 12 different topics (politics, health, technology, etc.)
- **Labels**: 
  - 0 = SUPPORTED
  - 1 = REFUTED
  - 2 = NEI (Not Enough Information)

## Customization

To modify the evaluation parameters, edit `evaluate.py`:

```python
evaluate(
    benchmark_name="vifactcheck",
    benchmark_kwargs=dict(variant="test"),  # Change split here
    n_samples=5,  # Increase for full evaluation
    n_workers=1,  # Increase for parallel processing
    # ... other parameters
)
```

## Reference

For more information about ViFactCheck, see:
- Paper: [ViFactCheck (AAAI 2025)](https://ojs.aaai.org/index.php/AAAI/article/view/32008)
- GitHub: [TTHHA/ViFactCheck](https://github.com/TTHHA/ViFactCheck)
- Dataset: [tranthaihoa/vifactcheck](https://huggingface.co/datasets/tranthaihoa/vifactcheck)
