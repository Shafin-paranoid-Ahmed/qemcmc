# Validation record

## Fresh install (2026-10-13)

A new virtual environment was created with the pinned `requirements.txt`
versions (NumPy 1.26.4, SciPy 1.15.3, scikit-learn 1.7.2) on **Python 3.12**
(Windows 11, CPU only; the documented target is Python 3.10), with PYTHONPATH cleared:

- `scripts/run_tests.py`: 14 CPU unit tests PASS.
- `scripts/smoke_test.py`: PASS (frozen splits, local metrics subprocess parity,
  four-spin quantum proposal). No files were written to the repository.

## Earlier checks (2026-10-12, existing environments)

- `scripts/run_tests.py`: 14 CPU unit tests PASS; `scripts/smoke_test.py`: PASS for
  seed 0/1/2 split loading/disjointness, local subprocess metric equality, and a
  normalized four-spin proposal. CPU environment: Python 3.10.20.
- `scripts/gpu_bench/test_gpu_proposal.py`: PASS in the GPU environment;
  dense four-spin total variation difference was 2.136e-13.
- GPU environment observed: Python 3.12.10, CuPy 14.1.1 (cupy-cuda13x),
  NumPy 2.5.1, SciPy 1.16.3. The recorded optional requirements match these
  installed versions and their CUDA runtime/NVRTC packages.
- Result CSV/JSON, figures, split files, and the metrics implementation were
  hash-checked; see [MANIFEST.json](MANIFEST.json).
- All Python files parsed successfully; executable scripts contain no
  machine-specific absolute paths. All relative Markdown links resolved locally.
- Selected paths, sizes, and common credential patterns were reviewed. No matching
  credential patterns were found; this is not an exhaustive security audit.
- A fresh HTTPS clone from GitHub passed the same CPU/synthetic checks.

## Not performed

No full model retraining, dataset regeneration, full GPU acceptance matrix, or
large scaling experiment was rerun.

## Notes

CPU unittest discovery also imports the optional GPU module, so the documented
CPU entry point loads the four CPU test modules explicitly.
