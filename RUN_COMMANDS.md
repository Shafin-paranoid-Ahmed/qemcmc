# Standalone QEMCMC runbook

Run from the repository root after following README.md.

```powershell
$PY = '.\.venv\Scripts\python.exe'
& $PY scripts/run_tests.py
& $PY scripts/smoke_test.py
& $PY scripts/stage1_train.py --help
```

The original experiment budgets, seeds, gates, and continuation commands are in
[the historical runbook](docs/historical/ORIGINAL_RUN_COMMANDS.md). For a deliberate
reproduction, replace `qsampler_ebm_pilot/scripts/` with `scripts/`, the old project
root with this checkout, and the old interpreter with the selected environment.
Preserve all scientific parameters and use a disposable reproduction checkout.

GPU numerical acceptance (requires a configured, compatible GPU environment):

```powershell
$env:QEMCMC_METRICS_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& .\.venv-gpu\Scripts\python.exe scripts/gpu_bench/test_gpu_proposal.py
& .\.venv-gpu\Scripts\python.exe scripts/gpu_bench/acceptance.py
```

These GPU commands are explicit validation tasks, not part of the quick start.
Historical completed grids and the uncompleted 24-bit rung do not run automatically.
