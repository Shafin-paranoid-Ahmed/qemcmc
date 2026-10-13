> Historical research record. Original machine paths and commands are retained as provenance. Use the standalone [README](README.md) and runbook for current setup.

# Change Log

## 2026-07-12 — Initial Stage-0 scaffold

- Created the pilot layout and run documentation.
- Added frozen ResNet-18/PCA code generation, exact-enumeration utilities,
  classical baselines and shared class-conditional Ising EBM training.
- Added planted Level-A instances, local/uniform proposals, and PennyLane
  Layden-style Hamiltonian-evolution proposals with matched-budget evaluation.

## 2026-07-12 — G2 metric amendment (censored IAT, median, magnetization observable)

- First G2 attempt returned `passed: false` with `inf` mean IATs for both
  qemcmc and local — a mean-aggregation artifact from degenerate/stuck chains,
  not a real mixing failure (see reconciliation note in
  `docs/still_exploring/quantum_sampler_ebm/QSAMPLER_EBM_PREREG.md` §6 and the
  matching entry in `RESULTS_LOG.md`).
- `scripts/gate_g2.py`: IAT is now censored at the post-burn-in trace length
  instead of returning `inf`; cross-seed aggregation uses the median; a
  magnetization trace/IAT is recorded alongside energy from the same chains;
  the gate rule is now per-spin-count (12/14/16) and requires QeMCMC's median
  IAT below local's and uniform's on both observables.
- Added resume-safe execution (skip chains already present in the tagged CSV
  on restart) and per-chain progress printing. Outputs now use a `--tag`
  (default `v2`); the original inf-poisoned run's files are untouched.
- Smoke-verified at `--spins 12 --seeds 0 --steps 200 --burn-in 50`; smoke
  artifacts deleted after verification. No Stage-1 runs and no full G2 rerun
  were launched — commands handed off to the author in `RUN_COMMANDS.md`.


## 2026-07-12 (later)

- `scripts/gate_g2.py`: resume now hard-errors if the tagged CSV's existing
  rows were produced under a different `--steps`/`--burn-in` than the current
  invocation (root cause of the v2 16-spin contamination — a relaunch with the
  old 600-step command silently mixed budgets).
- Seeded `results/qemcmc_exact_level-a_v3_all_mixing.csv` with the 27 valid
  3000/500 rows from v2; v2 files kept untouched as the contaminated record.
  v3 completion command handed to the author in RUN_COMMANDS.md (~7-8 h, nine
  16-spin chains).

## 2026-07-13

- G2 v3 completion run finished (author-launched): 36/36 chains at matched
  3000/500. **G2 PASSED** — verdict, per-spin medians, mechanism reading, and
  honesty bounds recorded in RESULTS_LOG.md. Stage 1 unlocked.

- Added the authorized 2026-07-13 Stage-1 16-bit decision note without editing
  pre-registered expectations.
- Added tagged 16-bit Level-C artifacts while preserving the 20-bit G1 record.
- Added fixed Level-B easy/hard generators and six dataset artifacts.
- Added stage1_train.py with seven sampler arms, exact causal metrics,
  validation selection, final test evaluation, per-update progress, and strict
  resume budget guards.
- Added benchmark_stage1.py, selected the matched 40x4x8 budget before smokes,
  and smoke-verified every sampler without launching a full run.
- Added the READY TO RUN Stage-1 matrix, SAMPLER_REPORT.md placeholder, and
  finalize_stage1.py aggregation helper.
- Added an engineering-only invocation pause control and verified a genuine
  interrupted-state resume from update 1 to update 2 under an unchanged budget.
- Updated the finalizer to populate generated report tables while leaving all
  interpretation and verdict text explicitly empty.
- Corrected exact-enumeration state indexing for TV/KL and mode coverage,
  changed IAT to within-chain median aggregation, paired sampled states with
  their contemporaneous labels, and added train NLL plus both-observable ESS.
- Made state/history flushing crash-consistent by retaining the last history row
  in resume state, reran all seven smokes, and refreshed the split-out timing
  benchmark (proposal, QeMCMC rebuild, fixed exact metrics).
- Reconciliation: the two preceding repeated correction pairs are one
  accidentally duplicated append, not two engineering events.
- Repaired PT to count alternating random replica moves/adjacent exchanges,
  including cold-replica exchanges, with beta-tempered label updates and no
  hidden proposal events; reran an 8-event PT smoke.
- Moved the all-sampler benchmark mode into the requested
  benchmark_qemcmc.py, added a crash-fail-safe final-test marker, and expanded
  finalize_stage1.py to require the complete matrix and aggregate all causal
  and across-seed stability metrics.
- Added test_stage1.py regression coverage for exact-state indexing and
  within-chain IAT aggregation.
- Corrected exact-enumeration state indexing for TV/KL and mode coverage,
  changed IAT to within-chain median aggregation, paired sampled states with
  their contemporaneous labels, and added train NLL plus both-observable ESS.
- Made state/history flushing crash-consistent by retaining the last history row
  in resume state, reran all seven smokes, and refreshed the split-out timing
  benchmark (proposal, QeMCMC rebuild, fixed exact metrics).
- Final append-only reconciliation: the repeated correction bullets above are
  accidental duplicates of one event; no second benchmark/run occurred.
- Amended the still-unlaunched matched budget shape from 40x4x8 to 40x1x32,
  preserving 1,280 events while providing 32 ordered observations per chain.
- Changed the sampled negative phase to use all visited state/label pairs, so
  gradient error, TV/KL, and IAT/ESS use the same 32-event sample.
- Added matrix-wide canonical budget enforcement to finalize_stage1.py.
- Measured a real complete 1x32 update for every arm; QeMCMC took 107.126 s,
  while classical/exact arms took 0.493-0.516 s in the update body. These are
  timing/smoke diagnostics only.
- Added and verified benchmark_qemcmc.py --stage1-full-updates: it invokes the
  real update path, pauses before test, records body/invocation timing, and
  automatically quarantines its tagged artifacts.
- Moved completed/final-recovery checks ahead of dataset loading so completed
  reruns and committed-metric recovery do not reread the test artifact.
- Added majority-class Macro-F1 to the 16-bit code-quality artifacts and
  clarified that the logistic head beats majority on Macro-F1, not accuracy.

## 2026-07-13 (later)

- Stage-1 matched budget superseded pre-run: 100 updates x 1 chain x 32 steps
  (was 40 updates; ruggedness-development rationale in RESULTS_LOG.md).
  RUN_COMMANDS.md Stage-1 block rewritten for the new budget and a
  parallel-seed launch layout (three windows, one seed each; level = one
  overnight session). No code changes; no runs launched.

## 2026-07-13 — Isolated GPU backend benchmark scaffold

- Created the separate `.venv-gpu` CUDA environment; `.venv-e1` was untouched.
- Added only `scripts/gpu_bench/` code: a complex128 Hermitian Chebyshev GPU
  proposal, dense unit test, fixed numerical-acceptance matrix, and the
  author-launched CPU/GPU timing suite.
- Added isolated records under `results/gpu_bench/`; numerical acceptance
  passed with worst TV 2.501e-13. The performance verdict remains pending the
  manual command, and no existing sampler/training file was modified.
- Review-hardened the author benchmark to require every registered spin size,
  validate the acceptance artifact fields, and time four class-conditioned
  diagonal rebuilds followed by a genuinely sequential 32-proposal chain.

## 2026-07-13 (GPU adoption)

- GPU backend benchmark returned 102x (n=16) / 763x (n=20) per proposal and
  82x on the realistic Stage-1 shape; adoption rule met. Decision notes added
  to RESULTS_LOG.md and the prereg doc: official Stage-1 matrix = g3-v2-gpu,
  GPU backend, 20-bit codes. g3-v1 16-bit partials retained as a record.

## 2026-07-13 (Stage-1 g3-v2-gpu integration)

- Added independent `--backend {cpu,gpu}` and `--bits {16,20}` Stage-1 flags;
  CPU/16 remain defaults. Backend and width are resume-guarded and recorded in
  histories/final metadata.
- Routed only QeMCMC proposal generation through the accepted CuPy Chebyshev
  class; accept/reject, sampler state updates, budgets, and classical sampler
  implementations remain shared. Added a CuPy exact-enumeration reference for
  the explicit GPU backend because the 20-bit NumPy update exceeded 2 seconds.
- Kept final classification metrics byte-identical by delegating from the GPU
  interpreter to the unchanged Full-QCNN metrics module in `.venv-e1`.
- Extended tagged Level-B generation to 20 bits and added a validated exact-copy
  retag mode for the existing train-only-PCA Level-C 20-bit G1 artifacts.
- Extended the SciPy reference ceiling to 20 spins and vectorized its all-state
  construction (verified zero numerical difference) for acceptance testing.
- Added n=20 six-case proposal acceptance and exact-reference numerical/timing
  scripts and artifacts under `results/gpu_bench/`.
- Updated the finalizer to require Level A, enforce backend/width consistency,
  and support no-write validation. Added the complete manual 84-run command
  block and finalization command to `RUN_COMMANDS.md`.
- Re-ran all seven explicit GPU/20-bit smokes plus resume and mismatch guards;
  quarantined all smoke/benchmark run artifacts. No official matrix was run.

## 2026-07-14

- Official Stage-1 matrix (g3-v2-gpu) completed by the author (84/84) and
  finalized. G3 PASSED; G4 entry condition met. Verdict, causal-chain tables,
  and the PCD-vs-QeMCMC transfer finding recorded in RESULTS_LOG.md.

## 2026-07-14 — Stage-2 adaptive controller implementation

- Extended the single `stage1_train.py` training path with the five locked
  Stage-2 sampler identities; no training loop was forked.
- Added the frozen five-arm discounted-UCB controller, exact/proxy rewards,
  persistent-QeMCMC state handling, controller state resume, and per-update
  controller history columns.
- Extended resume budgets with sampler variant, reward signal, and persistence.
- Added controller and sampler-configuration regression tests.
- Passed five 12-bit GPU completion smokes, a hard-error budget-mismatch smoke,
  and an interrupt/resume comparison whose final model, chains, RNG, and
  controller state matched an uninterrupted run. Smoke artifacts were removed
  after verification. No official Stage-2 run was launched during implementation.
- Appended the reproduction guard, G5, and three-window full-matrix commands to
  `RUN_COMMANDS.md`.

## 2026-07-14 — Stage-1 and Stage-2 reports finalized

- `results/ADAPTIVE_REPORT.md` written (Stage-2 deliverable, spec §8): §4
  decision rules answered from the complete 60-run stage2-v1-gpu matrix,
  interpretation table, arm-frequency diagnostics, weak-arm-separation note
  carried from the G5 amendment, contradicted classical-arm expectation
  reported per the hard don'ts, §7 expectation-vs-outcome table.
- `results/adaptive_arm_trajectory.png` generated (rolling 20-update arm
  selection frequency, exact-reward variants, pooled seeds; first 8 updates
  masked where the rolling window is degenerate). Script-generated from the
  tagged history CSVs; analysis-only, no run code touched.
- `results/SAMPLER_REPORT.md` interpretation and §1–§6 sections filled from
  the G3 verdict logged in RESULTS_LOG.md and the generated g3-v2-gpu
  tables; TV-degeneracy phrasing corrected against the data (PCD Level-A
  TV 0.59, fresh-chain samplers ≈1). Generated tables untouched.
- Analysis environment: pandas and matplotlib installed into .venv-gpu
  (analysis-only additions; no training/runtime dependency changed).

## 2026-07-15 ? Scaling-ladder implementation handoff

- Extended Stage-1 Level-C code routing with distinct 22-bit and 24-bit
  code-file tags while keeping training run-artifact tags separate.
- Widened code generation only to the registered 22/24-bit rungs and raised
  the existing exact/GPU input guards to 24 bits; the proposal law, controller,
  rewards, and budgets are unchanged.
- Added `gate_g6.py` with a three-update Level-C QeMCMC smoke under the
  registered 100x1x32 budget, device peak-VRAM measurement, 20-draw Chebyshev
  degree-doubling and state-norm checks, and fixed 22/24-bit wall ceilings.
- Added unit coverage for 22/24-bit tagged dataset routing and the existing
  bit-width resume-budget hard error.
- Appended manual 22/24-bit code generation, G6a/G6b, and exact 18-run rung
  matrices to `RUN_COMMANDS.md`.
- No official run was launched during implementation.

## 2026-09-07 — Current documentation restored

- README/handoff/results index now describe completed Stages 1/2 and the
  22-bit ladder, replacing the old Stage-0-only state.
- Marked runbook gate commands as reproduction history.
- Corrected the ladder report's outdated "4090 unconfirmed" wording using
  the July research-PC record; current availability and G6b passage are not
  inferred from that historical hardware check. No 24-bit results found here.
- No experiment, scientific artifact, protocol, or code changed.
