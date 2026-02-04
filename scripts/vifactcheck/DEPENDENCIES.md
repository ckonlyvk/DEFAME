# ViFactCheck Benchmark Dependencies

## Required Dependencies

Add the following to your `requirements.txt`:

```
# For loading ViFactCheck dataset from Hugging Face
datasets>=2.14.0

# Already included in DEFAME (verify versions)
transformers>=4.30.0
torch>=2.0.0
pandas>=1.5.0
```

## Installation

To install the datasets library:

```bash
pip install datasets
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

## Notes

- `datasets` library is required to load the ViFactCheck benchmark from Hugging Face
- The dataset identifier is: `tranthaihoa/vifactcheck`
- Available splits: `train`, `test`, `dev`
- The dataset will be automatically downloaded on first use and cached locally
