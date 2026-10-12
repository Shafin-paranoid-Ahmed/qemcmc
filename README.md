# QEMCMC and energy-based models

Standalone quantum-enhanced MCMC simulator study with Ising energy-based models,
classical sampling controls, persistence/adaptation ablations, and GPU scaling.

## Research status

Imported results cover 84 Stage-1 runs, 60 Stage-2 runs plus a reproduction guard,
and 18 runs at 22 bits. No completed 24-bit artifacts are included. Simulator
evidence concerns sampling/gradient accuracy at matched proposal budgets;
persistence explains most Stage-2 improvement. These are not hardware-speedup,
quantum-advantage, or superior crop-classification claims.

See [Stage 1](results/SAMPLER_REPORT.md), [Stage 2](results/ADAPTIVE_REPORT.md),
[the ladder report](results/LADDER_REPORT.md), and [registered protocols](docs/protocols/).

## CPU install and verification (PowerShell)

```powershell
py -3.10 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe scripts/run_tests.py
& .\.venv\Scripts\python.exe scripts/smoke_test.py
```

Tests and the small synthetic smoke require no crop images or quantum hardware.
They do not launch the historical benchmark grid. Python 3.10 is the verified
source CPU interpreter. See VALIDATION.md for extraction checks and limitations.

## Inputs and independent operation

The original split manifests and unmodified metric implementation are included
locally with their hashes in SOURCE_MANIFEST.json. There is no runtime dependency
on QCNN or the thesis repository. Historical code tables are included in
`results/`; the CPU sampler/EBM can use them without regenerating image features.

For image-code regeneration only, install `requirements-images.txt`, obtain the
original Dacon dataset under its terms, and set `QEMCMC_DATA_ROOT` to the folder
containing `test/<id>/<id>.jpg`. Default: `./data`. ResNet-18 pretrained weights
may be downloaded by torchvision on the first feature-extraction run. PCA must
remain fit on each seed's training partition. Keep `splits/` unchanged.

## Optional GPU backend

The GPU backend uses a separate environment. The extraction smoke passed with
Python 3.12.10, CuPy 14.1.1, and CUDA 13 packages; `requirements-gpu.txt` records
that observed stack. Install it in a compatible Python 3.12 environment with a
supported NVIDIA driver. This is a tested existing environment, not a verified
fresh-install recipe. This optional stack is not needed for CPU tests. Set
`QEMCMC_METRICS_PYTHON` to the absolute CPU-environment Python path when GPU
classification metrics need the pinned scikit-learn environment. Otherwise the
bridge uses the running interpreter, which must have the CPU requirements.
GPU cache defaults to `.cache/cupy`; normal OS temporary-directory settings are
preserved. Numerical acceptance scripts must pass on the target GPU before
claiming GPU reproduction. See [RUN_COMMANDS.md](RUN_COMMANDS.md).

## Layout and provenance

`scripts/` contains samplers, EBM training, metrics, tests, and `gpu_bench/`.
`splits/` holds frozen manifests; `results/` contains historical evidence;
`docs/protocols/` preserves preregistrations. Existing result metadata retains
original machine paths and source-commit provenance.

[PROVENANCE.md](PROVENANCE.md) explains extraction and attribution.
[NOTICE.md](NOTICE.md) records licensing status. Full experiment reruns can be
expensive; use a disposable checkout to avoid overwriting historical outputs.
