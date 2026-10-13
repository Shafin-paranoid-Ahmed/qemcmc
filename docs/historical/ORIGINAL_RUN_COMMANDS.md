> Historical research record. Original machine paths and commands are retained as provenance. Use the standalone [README](../../README.md) and runbook for current setup.

# Run Commands

Status as of 2026-09-07: Stage-0 gates, 84 Stage-1 runs, 60 Stage-2 runs plus
the reproduction guard, and 18 runs at 22 bits are complete. Earlier gate and
pending-run wording below is historical; preserve its exact reproduction
parameters and do not restart completed grids automatically. No 24-bit result
artifacts exist here. The July research-PC record confirms RTX 4090 hardware,
but current availability and the separate G6b gate still require verification.
See [README](ORIGINAL_README.md) and [the ladder report](../../results/LADDER_REPORT.md).

Run from repository root with the explicit project interpreter:

```powershell
$PY = ".\.venv-e1\Scripts\python.exe"
& $PY .\qsampler_ebm_pilot\scripts\test_exact.py
& $PY .\qsampler_ebm_pilot\scripts\build_codes.py --seeds 0 1 2 --bits 20
& $PY .\qsampler_ebm_pilot\scripts\gate_g1.py --seeds 0 1 2
```

Run G2 only if G1 passes:

```powershell
& $PY .\qsampler_ebm_pilot\scripts\benchmark_qemcmc.py --spins 12
& $PY .\qsampler_ebm_pilot\scripts\gate_g2.py --spins 12 14 16 --seeds 0 1 2
```

Stage-1 commands are appended only after both gates pass.

## READY TO RUN — G2 rerun commands (2026-07-12, post metric-amendment)

The 2026-07-12 G2 run (`results/qemcmc_exact_level-a_all_mixing.csv` /
`_all_verdict.json`) returned `passed: false` with `inf` mean IATs — a metric
artifact (mean poisoned by degenerate-energy chains), not a mixing failure; see
the 2026-07-12 reconciliation note in `QSAMPLER_EBM_PREREG.md` §6 and
`gate_g2.py` for the fix (censored IAT, median aggregation, magnetization
observable, per-spin-count gate rule). Those old files are left untouched —
this rerun writes new `_v2_` tagged files.

Run from the repo root with the explicit project interpreter:

```powershell
$PY = "WORKSPACE\.venv-e1\Scripts\python.exe"
& $PY "WORKSPACE\qsampler_ebm_pilot\scripts\gate_g2.py" --spins 12 14 16 --seeds 0 1 2 --steps 3000 --burn-in 500
```

- **Expected wall-clock: ~10-11 hours total.** The 16-spin QeMCMC chains alone
  are ~3 hours each (3 seeds x 16 spins = 9 hours of that); this is expected and
  accepted — do not downscale steps or trim the 16-spin case to save time.
- **Resume after any crash:** just rerun the exact same command. Chains
  (identified by spins/seed/sampler) whose row already exists in
  `qemcmc_exact_level-a_v2_all_mixing.csv` are skipped automatically; a
  `resuming: N chains already complete` line prints at startup, and each
  finished chain flushes its row to disk immediately (a crash at hour 9 does
  not lose the first 9 hours).
- **Per-chain progress** prints as each chain finishes: sampler, spins, seed,
  elapsed seconds, acceptance, energy IAT, magnetization IAT.
- **Expected output files** in `qsampler_ebm_pilot/results/`:
  - `qemcmc_exact_level-a_v2_all_mixing.csv` — per-chain rows (36 total: 3 spin
    counts x 3 seeds x 4 samplers), including the new
    `magnetization_iat_steps`, `magnetization_ess_per_proposal`, and
    `elapsed_seconds` columns.
  - `qemcmc_exact_level-a_v2_all_verdict.json` — the G2 verdict under the
    amended per-spin-count, dual-observable, median rule.


## READY TO RUN — G2 v3 completion run (2026-07-12)

The v2 run was contaminated at 16 spins by a resume under the wrong step
budget (see RESULTS_LOG.md). The 27 valid 3000-step chains were copied into
`results/qemcmc_exact_level-a_v3_all_mixing.csv`; this command resumes from
them and runs only the 9 missing 16-spin chains:

```powershell
$PY = "WORKSPACE\.venv-e1\Scripts\python.exe"
& $PY "WORKSPACE\qsampler_ebm_pilot\scripts\gate_g2.py" --spins 12 14 16 --seeds 0 1 2 --steps 3000 --burn-in 500 --tag v3
```

- Startup must print `resuming: 27 chains already complete` — if it errors
  about mismatched steps/burn-in instead, the flags above were mistyped.
- **Expected wall-clock: ~7-8 hours** (three 16-spin QeMCMC chains at
  ~2.3-2.8 h each; the six classical chains take seconds).
- Crash recovery: rerun the exact same command; completed chains are skipped.
  Rerunning with different `--steps`/`--burn-in` now hard-errors instead of
  silently mixing budgets.
- Output: `qemcmc_exact_level-a_v3_all_mixing.csv` (36 rows, all at 3000/500)
  and `qemcmc_exact_level-a_v3_all_verdict.json` — the actual G2 verdict.

## READY TO RUN — Stage 1 (G3) (2026-07-13)

These commands are run manually. Run one level per overnight session from
the repository root. Fixed matched budget (superseded 2026-07-13 BEFORE any
run — see RESULTS_LOG.md): **100 updates, 1 chain, 32 proposal steps = 3,200
proposal events per run**. Rationale: 40 updates risked stopping before the
EBM landscape becomes rugged (couplings start near zero; the multimodality G1
observed develops with training), which would trivially tie all samplers and
void the G4 entry signal. Tag: g3-v1.

**Parallel-seed layout:** each run pins exactly one CPU core (G2 observation),
so run the three seeds in three separate PowerShell windows simultaneously —
level wall-clock becomes one seed's time: ~2.8 h measured, ~4.7 h conservative.
Keep the machine plugged in, High Performance power plan, no sleep.

Common setup (paste in EACH window, then the window's seed line):

    $PY = "WORKSPACE\.venv-e1\Scripts\python.exe"
    $SCRIPT = "WORKSPACE\qsampler_ebm_pilot\scripts\stage1_train.py"
    $SAMPLERS = @("gibbs","mh-local","mh-uniform","pcd","pt","qemcmc","exact")
    function Run-Stage1Seed($level, $seed) {
        foreach ($sampler in $SAMPLERS) {
            & $PY $SCRIPT --level $level --sampler $sampler --seed $seed --updates 100 --chains 1 --proposal-steps 32 --tag g3-v1
            if ($LASTEXITCODE -ne 0) { throw "Stage-1 failed: $level/$sampler/seed$seed" }
        }
    }

Night 1 — Level B easy (window 1/2/3 respectively):

    Run-Stage1Seed b-easy 0
    Run-Stage1Seed b-easy 1
    Run-Stage1Seed b-easy 2

Night 2 — Level B hard: same three lines with `b-hard`.

Night 3 — Level C crop codes: same three lines with `c`.

Optional Night 4 — Level A learning arms, only after C and if budget allows:
same three lines with `a`.

Sequential fallback (one window, ~8.5 h measured / ~14 h conservative per
level): `foreach ($seed in 0,1,2) { Run-Stage1Seed <level> $seed }`.

Resume: rerun the exact same seed line. Completed runs print `already
complete`; incomplete runs resume from their JSON state. Any change to level,
sampler, seed, updates, chains, proposal-steps, or tag hard-errors before work.
At 100 updates the measured QeMCMC estimate is ~2.8 h per seed (component
estimate ~3.9 h); with three seeds in parallel windows that is also the level
wall-clock. Seeds are fully independent processes — running them concurrently
does not interact with resume-safety.
If a crash occurs after final test metrics were committed but before terminal
metadata, the identical command recovers metadata without rereading test. If it
instead errors that final evaluation started without committed metrics, stop:
do not delete state or rerun test; preserve the artifacts for a dated manual
reconciliation.

Expected files per configuration:

- `results/stage1_{sampler}_level-{level}_{seed}_g3-v1_history.csv`
- `results/stage1_{sampler}_level-{level}_{seed}_g3-v1_state.json`
- `results/stage1_{sampler}_level-{level}_{seed}_g3-v1_metadata.json`

After all manual runs complete:

    & $PY "WORKSPACE\qsampler_ebm_pilot\scripts\finalize_stage1.py" --tag g3-v1

## READY TO RUN — GPU backend benchmark (authoritative block)

Expected runtime: approximately 20-60 minutes; n=20 CPU SciPy may dominate.
Do not change the proposal count below. Run this in PowerShell:

```powershell
$env:CUPY_CACHE_DIR = "WORKSPACE\.venv-gpu\cupy_cache"
$env:TEMP = "WORKSPACE\.venv-gpu\tmp"
$env:TMP = "WORKSPACE\.venv-gpu\tmp"
& "WORKSPACE\.venv-gpu\Scripts\python.exe" "WORKSPACE\qsampler_ebm_pilot\scripts\gpu_bench\bench.py" --proposals 20 --spins 12 14 16 18 20 --stage-proposals 32 --stage-repeats 3 --seed 20260713
if ($LASTEXITCODE -ne 0) { throw "GPU backend benchmark failed; preserve the console output" }
```

Expected outputs are
`qsampler_ebm_pilot/results/gpu_bench/gpu_backend_benchmark.csv` and
`qsampler_ebm_pilot/results/gpu_bench/gpu_backend_verdict.json`. The latter applies the recorded
acceptance-plus-2x decision rule; no backend adoption occurs in this task.

## READY TO RUN — Stage 1 g3-v2-gpu (GPU, 20-bit)

This official matrix was run manually. Run the following single sequential
PowerShell block from the repository root. All seven arms use the GPU venv as
their top-level interpreter. QeMCMC proposal distributions and the 20-bit exact
reference use CuPy; final classification metrics are delegated internally to
the unchanged metrics implementation in `.venv-e1`, so no per-arm interpreter
split or new installation is required.

Measured projection: **about 5-6 hours for the complete 84-run matrix** on the
RTX 5070 if run sequentially. A four-class QeMCMC run projects to about 17.5
minutes; Level C projects to about 20.5 minutes because 25 class-conditioned
proposal diagonals are rebuilt. Classical/exact arms are dominated by the exact
reference and project to roughly 1-1.5 minutes per run. These are engineering
simulation-cost estimates only, never sampler wall-clock advantage claims.

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$SCRIPT = Join-Path $ROOT "qsampler_ebm_pilot\scripts\stage1_train.py"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

$LEVELS = @("a", "b-easy", "b-hard", "c")
$SAMPLERS = @("gibbs", "mh-local", "mh-uniform", "pcd", "pt", "qemcmc", "exact")

foreach ($level in $LEVELS) {
    foreach ($sampler in $SAMPLERS) {
        foreach ($seed in 0, 1, 2) {
            & $PY $SCRIPT `
                --level $level `
                --sampler $sampler `
                --seed $seed `
                --updates 100 `
                --chains 1 `
                --proposal-steps 32 `
                --backend gpu `
                --bits 20 `
                --tag g3-v2-gpu
            if ($LASTEXITCODE -ne 0) {
                throw "Stage-1 failed: level=$level sampler=$sampler seed=$seed"
            }
        }
    }
}
```

Resume after interruption by rerunning the exact same complete block. Finished
configurations print `already complete`; an incomplete configuration resumes
from its state JSON. Any backend, bit-width, update, chain, proposal-step,
level, sampler, seed, or tag mismatch hard-errors before work. Never point this
block at `g3-v1`, and never delete or move those retained 16-bit partials.

Expected files for each of 84 configurations:

- `results/stage1_{sampler}_level-{level}_{seed}_g3-v2-gpu_history.csv`
- `results/stage1_{sampler}_level-{level}_{seed}_g3-v2-gpu_state.json`
- `results/stage1_{sampler}_level-{level}_{seed}_g3-v2-gpu_metadata.json`

After all 84 runs complete, close Stage 1 with:

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
& $PY (Join-Path $ROOT "qsampler_ebm_pilot\scripts\finalize_stage1.py") --tag g3-v2-gpu
if ($LASTEXITCODE -ne 0) { throw "Stage-1 finalization failed; preserve all artifacts" }
```

The finalizer requires all four levels, seven samplers, three seeds, one
100x1x32 budget, backend `gpu`, and bit width 20 before writing
`stage1_summary_g3-v2-gpu.csv`, `stage1_causal_summary_g3-v2-gpu.csv`, and the
generated report tables. Interpretation and verdict placeholders remain empty
until the matrix actually completes.

## READY TO RUN — Stage 2 stage2-v1-gpu (2026-07-14)

No command in this section was launched during implementation. Run the reproduction guard
first. Run G5 only if the guard passes, and run the full matrix only if G5
passes under the locked Stage-2 rule.

### 1. Reproduction guard — fixed QeMCMC, Level C, seed 0

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$SCRIPT = Join-Path $ROOT "qsampler_ebm_pilot\scripts\stage1_train.py"
$RESULTS = Join-Path $ROOT "qsampler_ebm_pilot\results"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

& $PY $SCRIPT `
    --level c `
    --sampler qemcmc `
    --seed 0 `
    --updates 100 `
    --chains 1 `
    --proposal-steps 32 `
    --backend gpu `
    --bits 20 `
    --tag stage2-v1-gpu
if ($LASTEXITCODE -ne 0) {
    throw "Stage-2 reproduction guard run failed; preserve its artifacts"
}

$BASELINE = Import-Csv (Join-Path $RESULTS "stage1_qemcmc_level-c_0_g3-v2-gpu_history.csv")
$REPRO = Import-Csv (Join-Path $RESULTS "stage1_qemcmc_level-c_0_stage2-v1-gpu_history.csv")
$BASELINE_MEAN = [double](($BASELINE | Measure-Object -Property gradient_error -Average).Average)
$REPRO_MEAN = [double](($REPRO | Measure-Object -Property gradient_error -Average).Average)
$RELATIVE_DIFFERENCE = [Math]::Abs($REPRO_MEAN - $BASELINE_MEAN) / [Math]::Abs($BASELINE_MEAN)
[pscustomobject]@{
    baseline_mean_gradient_error = $BASELINE_MEAN
    reproduction_mean_gradient_error = $REPRO_MEAN
    relative_difference = $RELATIVE_DIFFERENCE
} | Format-List
if ($RELATIVE_DIFFERENCE -gt 0.01) {
    throw "Reproduction guard FAILED: mean gradient error differs by more than 1%"
}
```

### 2. Gate G5 — adaptive QeMCMC, exact reward, Level A, seed 0

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$SCRIPT = Join-Path $ROOT "qsampler_ebm_pilot\scripts\stage1_train.py"
$RESULTS = Join-Path $ROOT "qsampler_ebm_pilot\results"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

& $PY $SCRIPT `
    --level a `
    --sampler adaptive-qemcmc `
    --seed 0 `
    --updates 100 `
    --chains 1 `
    --proposal-steps 32 `
    --backend gpu `
    --bits 20 `
    --tag stage2-v1-gpu
if ($LASTEXITCODE -ne 0) {
    throw "Stage-2 G5 run failed; preserve its artifacts"
}

$ROWS = Import-Csv (Join-Path $RESULTS "stage1_adaptive-qemcmc_level-a_0_stage2-v1-gpu_history.csv")
$EARLY_REWARD = [double](($ROWS | Where-Object { [int]$_.update -le 50 } | Measure-Object -Property raw_reward -Average).Average)
$LATE_ROWS = @($ROWS | Where-Object { [int]$_.update -ge 51 })
$LATE_REWARD = [double](($LATE_ROWS | Measure-Object -Property raw_reward -Average).Average)
$EXPECTED_ARMS = @(
    "qemcmc-t-low-gamma-low",
    "qemcmc-t-low-gamma-high",
    "qemcmc-t-high-gamma-low",
    "qemcmc-t-high-gamma-high",
    "classical-local"
)
$ARM_FREQUENCIES = @($EXPECTED_ARMS | ForEach-Object {
    $arm = $_
    $count = @($LATE_ROWS | Where-Object { $_.chosen_arm -eq $arm }).Count
    [pscustomobject]@{ arm = $arm; frequency = $count / $LATE_ROWS.Count }
})
$ARM_FREQUENCIES | Format-Table -AutoSize
[pscustomobject]@{ updates_1_50_mean_reward = $EARLY_REWARD; updates_51_100_mean_reward = $LATE_REWARD } | Format-List
if (-not ($ARM_FREQUENCIES | Where-Object { $_.frequency -lt 0.1 -or $_.frequency -gt 0.4 })) {
    throw "G5 FAILED: late arm distribution stayed inside [0.1, 0.4] for every arm"
}
if ($LATE_REWARD -le $EARLY_REWARD) {
    throw "G5 FAILED: mean reward did not improve in updates 51-100"
}
```

### 3. Full Stage-2 matrix — 5 samplers x 4 levels x 3 seeds

Paste the common setup into each of three PowerShell windows, then run one
seed line per window. The G5 configuration already completed above will print
`already complete` in the seed-0 window.

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$SCRIPT = Join-Path $ROOT "qsampler_ebm_pilot\scripts\stage1_train.py"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

$LEVELS = @("level-a", "level-b-easy", "level-b-hard", "level-c")
$SAMPLERS = @(
    "adaptive-qemcmc",
    "adaptive-qemcmc-p",
    "qemcmc-p",
    "adaptive-qemcmc-proxy",
    "adaptive-qemcmc-p-proxy"
)

function Run-Stage2Seed([int]$seed) {
    foreach ($registeredLevel in $LEVELS) {
        $level = $registeredLevel -replace "^level-", ""
        foreach ($sampler in $SAMPLERS) {
            & $PY $SCRIPT `
                --level $level `
                --sampler $sampler `
                --seed $seed `
                --updates 100 `
                --chains 1 `
                --proposal-steps 32 `
                --backend gpu `
                --bits 20 `
                --tag stage2-v1-gpu
            if ($LASTEXITCODE -ne 0) {
                throw "Stage-2 failed: level=$level sampler=$sampler seed=$seed"
            }
        }
    }
}
```

Window 1:

```powershell
Run-Stage2Seed 0
```

Window 2:

```powershell
Run-Stage2Seed 1
```

Window 3:

```powershell
Run-Stage2Seed 2
```

Resume after interruption by rerunning the identical seed line in that window.
Completed configurations print `already complete`; incomplete configurations
resume from their JSON state. Any budget, backend, width, sampler-variant,
reward-signal, or persistence mismatch hard-errors before training.

## READY TO RUN ? Scaling ladder 22-bit rung (2026-07-15)

No official run was launched during implementation. Run these blocks in order. The
code-file tag identifies the generated dataset; the separate `--tag` on the
18-run matrix identifies training artifacts.

### 1. Generate the 22-bit Level-C code files

> **2026-07-15 correction:** code generation runs under **.venv-e1** (torch /
> torchvision / sklearn — the environment that built the original 20-bit
> codes). `.venv-gpu` is the CuPy sampler environment and lacks sklearn; the
> first attempt failed there with ModuleNotFoundError before writing any
> artifact. Blocks 2–3 below correctly stay on `.venv-gpu`.

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-e1\Scripts\python.exe"
$BUILD = Join-Path $ROOT "qsampler_ebm_pilot\scripts\build_codes.py"

& $PY $BUILD `
    --seeds 0 1 2 `
    --bits 22 `
    --batch-size 128 `
    --tag stage1-22bit-ladder22-v1-gpu
if ($LASTEXITCODE -ne 0) {
    throw "22-bit code generation failed; preserve all artifacts and stop"
}
```

Expected code-file tag: `stage1-22bit-ladder22-v1-gpu`. This is deliberately
different from the training run-artifact tag `ladder22-v1-gpu` below.

### 2. Run G6a at 22 bits

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$GATE = Join-Path $ROOT "qsampler_ebm_pilot\scripts\gate_g6.py"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

& $PY $GATE --bits 22
if ($LASTEXITCODE -ne 0) {
    throw "G6a failed; preserve its verdict/artifacts and do not run the 22-bit matrix"
}
```

### 3. Run the exact 18-run 22-bit matrix

Run only after the 22-bit G6a verdict passes.

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$SCRIPT = Join-Path $ROOT "qsampler_ebm_pilot\scripts\stage1_train.py"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

$SAMPLERS = @(
    "exact",
    "qemcmc",
    "mh-uniform",
    "pcd",
    "qemcmc-p",
    "adaptive-qemcmc-p-proxy"
)

foreach ($sampler in $SAMPLERS) {
    foreach ($seed in 0, 1, 2) {
        & $PY $SCRIPT `
            --level c `
            --sampler $sampler `
            --seed $seed `
            --updates 100 `
            --chains 1 `
            --proposal-steps 32 `
            --backend gpu `
            --bits 22 `
            --tag ladder22-v1-gpu
        if ($LASTEXITCODE -ne 0) {
            throw "22-bit ladder run failed: sampler=$sampler seed=$seed; preserve artifacts"
        }
    }
}
```

## READY TO RUN ? Conditional scaling ladder 24-bit rung (2026-07-15)

No official run was launched during implementation. This rung is conditional on every
G6b item. These commands use the research-PC root from the binding prereg and
must not be redirected to the 22-bit local-machine artifacts.

### 1. Capture the RTX 4090 environment record

```powershell
$ROOT = "WORKSPACE"
$RESULTS = Join-Path $ROOT "qsampler_ebm_pilot\results"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

$GPU_RECORD = & nvidia-smi `
    --query-gpu=name,driver_version,memory.total `
    --format=csv,noheader,nounits
if ($LASTEXITCODE -ne 0 -or -not ($GPU_RECORD -match "RTX 4090")) {
    throw "G6b requires nvidia-smi confirmation of an RTX 4090"
}
$CUPY_RECORD = & $PY -c "import cupy as cp; print(cp.__version__); print(cp.cuda.runtime.runtimeGetVersion()); print(cp.cuda.runtime.getDeviceCount())"
if ($LASTEXITCODE -ne 0) {
    throw "G6b requires a working CUDA/CuPy environment"
}
[ordered]@{
    captured_at = (Get-Date).ToString("o")
    project_root = $ROOT
    nvidia_smi = @($GPU_RECORD)
    cupy_cuda = @($CUPY_RECORD)
} | ConvertTo-Json -Depth 4 | Set-Content `
    -LiteralPath (Join-Path $RESULTS "gate_g6b_24bit_environment.json") `
    -Encoding utf8
```

### 2. Generate the 24-bit Level-C code files

> **2026-07-15 correction (same as the 22-bit block):** code generation runs
> under the torch/sklearn environment (**.venv-e1** on the lab PC), NOT
> `.venv-gpu` (CuPy only, no sklearn).

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-e1\Scripts\python.exe"
$BUILD = Join-Path $ROOT "qsampler_ebm_pilot\scripts\build_codes.py"

& $PY $BUILD `
    --seeds 0 1 2 `
    --bits 24 `
    --batch-size 128 `
    --tag stage1-24bit-ladder24-v1-gpu
if ($LASTEXITCODE -ne 0) {
    throw "24-bit code generation failed; preserve all artifacts and stop"
}
```

Expected code-file tag: `stage1-24bit-ladder24-v1-gpu`. This is deliberately
different from the training run-artifact tag `ladder24-v1-gpu` below.

### 3. Run the G6b 20-bit cross-machine reproduction guard

The original `g3-v2-gpu` Level-C seed-0 history must be present on the research
PC before this block is run.

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$SCRIPT = Join-Path $ROOT "qsampler_ebm_pilot\scripts\stage1_train.py"
$RESULTS = Join-Path $ROOT "qsampler_ebm_pilot\results"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

& $PY $SCRIPT `
    --level c `
    --sampler qemcmc `
    --seed 0 `
    --updates 100 `
    --chains 1 `
    --proposal-steps 32 `
    --backend gpu `
    --bits 20 `
    --tag g6b-crossmachine-v1-gpu
if ($LASTEXITCODE -ne 0) {
    throw "G6b cross-machine reproduction run failed; preserve artifacts"
}

$BASELINE = Import-Csv (Join-Path $RESULTS "stage1_qemcmc_level-c_0_g3-v2-gpu_history.csv")
$REPRO = Import-Csv (Join-Path $RESULTS "stage1_qemcmc_level-c_0_g6b-crossmachine-v1-gpu_history.csv")
$BASELINE_MEAN = [double](($BASELINE | Measure-Object -Property gradient_error -Average).Average)
$REPRO_MEAN = [double](($REPRO | Measure-Object -Property gradient_error -Average).Average)
$RELATIVE_DIFFERENCE = [Math]::Abs($REPRO_MEAN - $BASELINE_MEAN) / [Math]::Abs($BASELINE_MEAN)
$CROSS_MACHINE_GUARD = [ordered]@{
    captured_at = (Get-Date).ToString("o")
    baseline_mean_gradient_error = $BASELINE_MEAN
    reproduction_mean_gradient_error = $REPRO_MEAN
    relative_difference = $RELATIVE_DIFFERENCE
    tolerance_inclusive = 0.01
    passed = ($RELATIVE_DIFFERENCE -le 0.01)
}
$CROSS_MACHINE_GUARD | ConvertTo-Json | Set-Content `
    -LiteralPath (Join-Path $RESULTS "gate_g6b_20bit_crossmachine_guard.json") `
    -Encoding utf8
[pscustomobject]$CROSS_MACHINE_GUARD | Format-List
if ($RELATIVE_DIFFERENCE -gt 0.01) {
    throw "G6b FAILED: 20-bit cross-machine mean gradient error differs by more than 1%"
}
```

### 4. Run G6b numerics/VRAM/timing at 24 bits

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$GATE = Join-Path $ROOT "qsampler_ebm_pilot\scripts\gate_g6.py"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

& $PY $GATE --bits 24
if ($LASTEXITCODE -ne 0) {
    throw "G6b failed; preserve its verdict/artifacts and do not run the 24-bit matrix"
}
```

### 5. Run the exact 18-run 24-bit matrix

Run only after the environment, cross-machine, and 24-bit gate blocks all pass.

```powershell
$ROOT = "WORKSPACE"
$PY = Join-Path $ROOT ".venv-gpu\Scripts\python.exe"
$SCRIPT = Join-Path $ROOT "qsampler_ebm_pilot\scripts\stage1_train.py"
$env:CUPY_CACHE_DIR = Join-Path $ROOT ".venv-gpu\cupy_cache"
$env:TEMP = Join-Path $ROOT ".venv-gpu\tmp"
$env:TMP = Join-Path $ROOT ".venv-gpu\tmp"

$SAMPLERS = @(
    "exact",
    "qemcmc",
    "mh-uniform",
    "pcd",
    "qemcmc-p",
    "adaptive-qemcmc-p-proxy"
)

foreach ($sampler in $SAMPLERS) {
    foreach ($seed in 0, 1, 2) {
        & $PY $SCRIPT `
            --level c `
            --sampler $sampler `
            --seed $seed `
            --updates 100 `
            --chains 1 `
            --proposal-steps 32 `
            --backend gpu `
            --bits 24 `
            --tag ladder24-v1-gpu
        if ($LASTEXITCODE -ne 0) {
            throw "24-bit ladder run failed: sampler=$sampler seed=$seed; preserve artifacts"
        }
    }
}
```
