# Extraction validation - 2026-10-12

Verified from the final standalone local directory before initial publication.

- `scripts/run_tests.py`: 14 CPU unit tests PASS.
- `scripts/smoke_test.py`: PASS for seed 0/1/2 split loading/disjointness,
  local subprocess metric equality, and a normalized four-spin proposal.
- `scripts/gpu_bench/test_gpu_proposal.py`: PASS in the existing GPU environment;
  dense four-spin total variation difference was 2.136e-13.
- GPU environment observed: Python 3.12.10, CuPy 14.1.1 (cupy-cuda13x),
  NumPy 2.5.1, SciPy 1.16.3. The recorded optional requirements match these
  installed versions and their CUDA runtime/NVRTC packages.

- All selected source-file hashes verified against the source checkout and the
  snapshot manifest. Result CSV/JSON, figures, checkpoints, split files, and the
  metrics implementation remain byte-identical to their selected source files.
- All Python files parsed successfully; executable scripts contain no old
  machine-root paths or sibling thesis experiment-folder dependencies.
- All relative Markdown file links resolved locally.
- Reviewed selected paths, sizes, and common credential patterns before staging.
  No matching credential patterns were found; this is not an exhaustive security audit.

CPU checks used the existing research Python 3.10.20 interpreter and installed
dependencies (NumPy 1.26.4, SciPy 1.15.3, scikit-learn 1.7.2; QCNN additionally
Torch 2.11.0+cu128 and PennyLane 0.42.3). The interpreter was outside these new
repositories, but the tested project code and frozen inputs were inside them.
No fresh dependency installation, full model retraining, dataset regeneration,
full GPU acceptance matrix, or large scaling experiment was performed.

Initial sandbox runs hit Windows temporary-directory permissions; relevant
checks passed when rerun outside those restrictions. CPU unittest discovery also
imported the optional GPU module, so the documented CPU entry point explicitly
loads the four CPU test modules instead.

## Publication verification

Public repository: https://github.com/Shafin-paranoid-Ahmed/qemcmc

A fresh HTTPS clone of commit `d9475b603dba1d0cec811d26fefdf4bfcc4aab13` was downloaded from GitHub.
All 827 source-manifest hashes matched. The documented
CPU/synthetic checks passed again from that clone with PYTHONPATH cleared.
The original clone attempt used SSH and failed host-key verification; publication
succeeded through authenticated HTTPS without disabling host verification.
The local TokenSave integration added an ignore entry during clone inspection;
`.tokensave` is now included in the published ignore file.
Only documentation and this ignore entry changed after the verified code commit.
