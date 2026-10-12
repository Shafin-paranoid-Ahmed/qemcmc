# Stage-2 Pre-Registration — Online Gradient-Aware Adaptive QeMCMC for EBM Training

Date: 2026-07-14 (written AFTER gates G0–G4 all passed, BEFORE any Stage-2 code
or run; the expectations in §7 must never be edited after results exist).
Status: PRE-REGISTERED. Parent document:
`docs/still_exploring/quantum_sampler_ebm/QSAMPLER_EBM_PREREG.md` (all of its
hard constraints §1 and hard don'ts remain binding here). This document is the
dated pre-run note required by the parent's amendment rule for every mechanism
and baseline introduced below.

Gate record feeding this spec: G3 verdict (2026-07-14) and G4 verdict
(2026-07-14) in `qsampler_ebm_pilot/RESULTS_LOG.md`.

---

## 0. The claim under test (verbatim from the G4 verdict)

> Online, gradient-error-driven adaptation of gate-model QeMCMC proposal
> parameters inside classical discrete-latent EBM training on real
> image-derived codes, with exact-enumeration ground truth and a
> pre-registered proxy-signal transfer study.

No publication was found occupying this slot as of 2026-07-14 (G4 literature
sub-check). This is the thesis's invention headline. It is a claim about a
**new hybrid training algorithm and its mechanism**, never about quantum
advantage or wall-clock speed.

**Research question, one line.** Layden-style QeMCMC draws its proposal
parameters (evolution time t, mixer weight γ) blindly at random every proposal.
Stage 1 showed sampler identity moves the training signal (3× gradient-error
spread on real crop codes, QeMCMC best). Can a controller that *learns* which
(t, γ) to use — online, while the EBM's landscape drifts under training —
deliver more accurate negative-phase gradients than the blind scheme, at the
identical proposal budget?

## 1. Mandatory prior-art citations and differentiation (from G4)

| Work | What it does | Why it does not occupy the slot |
|---|---|---|
| **QAOA-MC** (arXiv:2305.08789; Phys. Rev. Research 6:033105) — nearest prior art, MUST be cited and differentiated | Optimizes QAOA proposal-circuit parameters for quantum-enhanced MCMC via an acceptance-rate ↔ spectral-gap correlation | (a) OFFLINE per-instance pre-optimization vs our ONLINE adaptation during training; (b) fixed target distribution vs our drifting in-loop EBM target; (c) acceptance-rate objective vs our negative-phase gradient error, exact at ≤20 bits |
| Layden et al., Nature 618:500 (2023) | QeMCMC foundation; randomized (t, γ) per proposal | The fixed randomized scheme is exactly our baseline policy (§3.2) |
| Sajjan, Singh & Kais, npj QI 12:93 (2026) | QeMCMC inside a training loop (NN quantum states, chemistry) | Fixed randomized (t, γ); no adaptation; not image data |
| IQEMC (arXiv:2606.23350) | Irreversible state-dependent quantum proposals | Fixed target; cite as concurrent sampler work |
| QA-enhanced MCMC (Sci. Rep. 2025, s41598-025-07293-y) | Annealer proposals | Fixed target, annealing hardware |
| Classical adaptive-MCMC-for-EBM (arXiv:2010.03587, arXiv:2310.12667) | Learned/adaptive classical samplers for drifting EBM targets | Classical proposals only; motivation support |
| Pasarica & Gelman (2010), expected squared jump distance | Standard adaptive-MCMC tuning objective | Source for our proxy reward (§3.4); classical literature |

## 2. What Stage 1 established (design inputs, not re-litigated)

From the G3 verdict (g3-v2-gpu matrix, 4 levels × 7 samplers × 3 seeds,
100 updates × 1 chain × 32 proposals, 20-bit codes, GPU backend):

1. **Level C (real crop codes):** QeMCMC with blind (t, γ) already produces the
   most accurate gradients of all approximate samplers (5.30 vs 7.37 next
   best). The signal the controller would exploit exists on real data.
2. **Levels A/B:** PCD wins in-loop — chain **persistence across updates**
   matters more than per-step mixing at 32 proposals/update on a
   slowly-drifting landscape. G2's static-landscape advantage does not transfer
   automatically. Stage 2 must therefore treat persistence as an explicit
   design factor, not ignore it.
3. **Metric lesson:** at 32 samples over 2^20 states, TV/KL/mode-coverage are
   degenerate; **gradient error is the informative primary metric** (a moment
   estimate, valid at small sample size), as pre-registered in parent §7.

## 3. Design (fixed by this pre-registration)

### 3.1 What is adapted

The QeMCMC proposal parameters (t, γ) only. The Hamiltonian form, the exact
(non-Trotterized) evolution, the MH accept/reject, the EBM energy form, the
codes, splits, budgets, backend (GPU, CuPy Chebyshev), and bit width (20) are
all frozen at their Stage-1 g3-v2-gpu values. Detailed balance is untouched:
whatever (t, γ) the controller picks, the proposal remains symmetric and MH
correction keeps the chain exact for the *current* energy — adaptation can
only change proposal QUALITY, never correctness of the stationary target.

### 3.2 Arm set and the fixed baseline as a policy

The Stage-1 ranges TIME_RANGE = (2, 20), GAMMA_RANGE = (0.25, 0.6) are
partitioned into a 2×2 grid of cells:

- t-low = (2, 11], t-high = (11, 20]
- γ-low = (0.25, 0.425], γ-high = (0.425, 0.6]

plus one **classical arm**: a local single-bit-flip Metropolis proposal block.
Total **5 arms**. Within a chosen quantum cell, (t, γ) is drawn uniformly (the
Layden randomization survives within-cell). One arm is chosen per EBM update
and used for all 32 proposals of that update (100 controller rounds per run).

Key identity, pre-registered as the central comparison framing: **the Stage-1
fixed sampler (uniform (t, γ) over the full ranges) is exactly the
uniform-random policy over the four quantum cells.** "Adaptive vs fixed" is
therefore "learned policy vs random policy" at identical support and budget.
The classical arm makes the parent's §6 mechanism 3 (budget-aware
classical/quantum switching) a special case of the same controller: choosing
the classical arm IS the switch.

### 3.3 Controller

Discounted UCB (a standard non-stationary bandit; discount handles the
drifting landscape) over the 5 arms. Fixed hyperparameters, pre-registered,
never tuned after results exist:

- discount 0.9; exploration constant c = 1.0 on rewards standardized by
  running mean/std; each arm forced once in the first 5 updates.

Rewards are standardized online so the same hyperparameters serve both reward
signals. No other controller variants, no hyperparameter search. If the
controller underperforms, that is the finding — not a license to tune.

### 3.4 Two reward signals (the transfer sub-study, parent §6)

- **Exact reward (oracle arm of the study):** r_u = −‖ĝ_u − g_exact,u‖₂, the
  per-update negative-phase gradient error already computed for metrics. The
  EBM update itself ALWAYS uses the sampled gradient ĝ_u — the exact gradient
  steers only the controller, never the model. This is the mechanistic
  question: *if* the controller could see the true signal, does adaptation
  help?
- **Proxy reward (deployment-honest arm):** mean accepted Hamming jump
  distance per proposal step (acceptance × Hamming distance; the discrete
  analog of expected squared jump distance, Pasarica & Gelman 2010). Computed
  from the same 32 proposals — zero extra budget, no enumeration required, so
  it survives beyond 20 bits.

Pre-registered transfer question: what fraction of the (fixed − adaptive_exact)
gradient-error gap does adaptive_proxy retain?

### 3.5 Persistence factor (dated introduction, motivated by G3 finding 2)

Two chain regimes for every QeMCMC variant:
- **fresh**: chain re-initialized from data each update (Stage-1 behavior);
- **persistent**: chain state carried across updates (PCD's mechanism, with
  QeMCMC/adaptive proposals instead of local flips).

This factor is new relative to parent §6 and is introduced here, before any
affected run, as the parent's amendment rule requires. Justification: G3
showed persistence is the strongest in-loop effect on Levels A/B; an adaptive
sampler that ignores it would be beaten by PCD for a known, already-published
reason.

### 3.6 Sampler set for Stage 2

New runs (tag **stage2-v1-gpu**):

| # | Sampler | Chains | Proposals | Reward | Purpose |
|---|---|---|---|---|---|
| 1 | adaptive-qemcmc | fresh | controller | exact | core mechanism |
| 2 | adaptive-qemcmc-p | persistent | controller | exact | mechanism + persistence |
| 3 | qemcmc-p | persistent | fixed random (t,γ) | — | isolates persistence from adaptation |
| 4 | adaptive-qemcmc-proxy | fresh | controller | proxy | transfer study |
| 5 | adaptive-qemcmc-p-proxy | persistent | controller | proxy | transfer study |

Reused from g3-v2-gpu without rerun (identical budget, backend, bits, codes):
fixed fresh QeMCMC, PCD (best classical on A/B), mh-uniform (best classical on
C), exact reference. **Reproduction guard:** before any new-sampler run counts,
one config (fixed QeMCMC, Level C, seed 0) is rerun under stage2-v1-gpu and
must reproduce its g3-v2-gpu gradient-error trajectory (same seeds, same code
path ⇒ near-identical; tolerance: mean gradient error within 1%). Failure =
code-path drift; stop and debug before proceeding.

### 3.7 Budgets and matrix

Identical Stage-1 budget: 100 updates × 1 chain × 32 proposals per update,
20-bit codes, GPU backend, resume-safe with the budget-mismatch hard-error
(now also covering reward-signal and persistence flags in the budget dict).
Levels A, B-easy, B-hard, C; seeds 0/1/2.

New runs: 5 samplers × 4 levels × 3 seeds = **60 runs** + 1 reproduction run.
At measured g3-v2-gpu throughput this is hours, not days, on the RTX 5070.
Controller overhead (bandit bookkeeping) is negligible; exact-gradient
computation is already part of the metric pipeline.

## 4. Metrics and pre-registered decision rules

Parent §7 causal chain unchanged; gradient error primary (per §2.3 above).
Per-update logs additionally record: chosen arm, reward, controller value
estimates — the arm-choice trajectory is itself a deliverable (it shows WHAT
the controller learned, e.g. drift from mixing-heavy to exploitation-heavy
arms as the landscape sharpens, and whether choices correlate with the logged
ruggedness proxies — this is how parent §6's "schedule driven by landscape
state" is answered: learned implicitly, reported explicitly).

Decision rules, fixed now:

1. **Primary comparison:** median-across-seeds mean gradient error over all
   100 updates, per level. Secondary: same over updates 51–100 (allows the
   controller its learning transient).
2. **"Adaptation helps" (per level):** adaptive-qemcmc beats fixed QeMCMC on
   the primary comparison. **"Adaptation helps overall":** it does so on ≥2 of
   4 levels and is beaten on none by more than 5%.
3. **"Persistence is the dominant effect":** qemcmc-p accounts for more of the
   improvement over fixed QeMCMC than adaptation does (compare deltas 3-vs-fixed
   and 1-vs-fixed). An honest possible outcome, reported as such.
4. **Beat-the-field check:** best adaptive variant vs PCD per level — did the
   adaptive quantum sampler close the Levels-A/B gap Stage 1 exposed?
5. **Transfer fraction:** (fixed − adaptive_proxy) / (fixed − adaptive_exact)
   on gradient error, per level, when the denominator is positive; reported
   as-is (may be negative — that too is a finding).
6. Downstream NLL/Macro-F1 reported last, per parent §7; no headline from them.

## 5. Stage-2 internal gate (G5 — controller sanity, before the full matrix)

On Level A, seed 0 only: run adaptive-qemcmc (exact reward) once and check
that (a) the run completes with the budget guard clean, (b) the controller's
arm distribution over updates 51–100 differs from uniform (chi-square p <
0.05, or equivalently any arm frequency outside [0.1, 0.4] for 5 arms), and
(c) mean reward over updates 51–100 exceeds that over updates 1–50. This gate
checks the controller is *functioning* (learning something, anything), not
that it wins. If G5 fails: debug the controller implementation; do not touch
rewards/hyperparameters without a dated note here.

### 2026-07-14 amendment — G5 criteria (b)/(c) were miscalibrated; mechanism check moved to a controlled environment

Recorded after the first G5 run (adaptive-qemcmc, Level A, seed 0, tag
stage2-v1-gpu) failed original criteria (b) and (c), and BEFORE any further
Stage-2 run. This is an operational gate-metric fix in the same class as the
G2 censored-IAT amendment; no controller code, reward, hyperparameter, or §7
expectation is changed by it.

Diagnosis from the completed run's own history (retained as an official
stage2-v1-gpu artifact):

- Criterion (c) ("late mean reward > early") tested landscape stationarity,
  not learning: gradient error rises 13.7 → 20.0 over the 100 updates because
  the trained EBM's couplings grow and the landscape sharpens — the same drift
  Stage 1 recorded for every sampler. Under a globally declining reward no
  controller can pass (c); the criterion was structurally impossible, an
  error in this spec's design, not in the implementation.
- Criterion (b) (an arm frequency outside [0.1, 0.4] over updates 51–100)
  presumed a strong arm separation that Level A does not provide: measured
  per-arm mean rewards span −17.3 to −19.4 with per-pull noise SD 3.0–4.6
  (separation ≈ 0.5σ). No 100-round bandit concentrates under that
  signal-to-noise; near-uniform play with a tilt toward the better arms is
  the CORRECT response, and the run shows exactly that tilt (the two
  best-reward arms drew 46 pulls, the two worst 28, ranking almost monotone).

Amended G5, effective from this date:

(a) unchanged — the run completes with the budget guard clean and all
controller log columns populated. Met by the existing run.
(b') mechanism concentration check in a CONTROLLED environment: the unit
tests `ControllerConcentrationTests` (planted 1σ arm separation, stationary
AND drifting reward, 10 seeds) must show the controller concentrating on the
planted arm (argmax of pulls, > 2× mean pulls of the other arms). Result:
planted arm drew ~43/100 pulls vs ~14 for each other arm in both
environments — PASSED 2026-07-14.
(c') the live-run arm-frequency table and per-arm mean rewards are reported
as diagnostics in ADAPTIVE_REPORT.md, not gated — whether live arms separate
enough to exploit is a §4 study question, not a sanity precondition.

G5 verdict under the amended criteria: **PASSED 2026-07-14.** The weak
Level-A arm separation is itself a pre-registered-relevant observation and
must be reported alongside the §4 decision rules.

## 6. Honest limits, stated in advance

1. The exact-reward controller is an **oracle study** — it exists because ≤20
   bits is enumerable. The proxy arm (§3.4) is the pre-registered, honest
   answer to "the method trains where the signal isn't available"; its result,
   whatever it is, goes in the report.
2. One controller, fixed hyperparameters, 100 rounds, 5 arms: statistically
   thin by bandit standards. We claim mechanism demonstration, not controller
   optimality. No post-hoc controller tuning under any outcome.
3. All comparisons remain per-proposal-step quality on a simulator. No
   wall-clock, no quantum-advantage claims, under any outcome (parent §8).
4. Fixed QeMCMC already wins Level C in Stage 1; adaptive may add nothing
   there (limited headroom) while helping most on A/B where QeMCMC trailed
   PCD. The per-level pattern is part of the story either way.

## 7. Pre-registered expectations (locked 2026-07-14, never edited)

- Adaptive (exact reward) reduces gradient error vs fixed QeMCMC on Levels
  A/B — expected (parent §8 already registered this).
- Persistence (qemcmc-p vs fixed) expected to be a large effect on A/B (PCD
  evidence) and small on C.
- adaptive-qemcmc-p expected to be the best quantum variant overall; whether
  it beats PCD on A/B is genuinely uncertain — either outcome is reportable.
- Proxy-signal transfer expected PARTIAL (parent §8): some, not all, of the
  adaptive gain survives without the exact signal.
- Level C: adaptation expected to give at most a small gradient-error
  improvement; downstream classification expected unchanged (differences
  compress at the last link, as in Stage 1).
- Classical-arm usage expected rare on rugged levels (A/B-hard) and more
  frequent on smooth ones — if observed, that is the budget-aware-switching
  result of parent §6.

## 8. Deliverables and handoff

- `qsampler_ebm_pilot/scripts/` gains the controller + persistent-chain
  support behind flags on the existing `stage1_train.py` path (one code path,
  budget-dict extended; no fork of the trainer).
- `ADAPTIVE_REPORT.md` (parent §10) with the §4 decision rules answered and
  the arm-trajectory figure.
- Implementation by the Codex agent from this spec; ALL run commands are
  handed to the user (never executed by the agent); verification of the
  implementation, gate G5 reading, and the final verdicts are done here.
- Append-only logging in `RESULTS_LOG.md`/`CHANGELOG.md` as always; every
  artifact tagged stage2-v1-gpu.

## Hard don'ts (inherited + specific)

- Parent §1 constraints and hard don'ts apply unchanged.
- No controller/reward/hyperparameter changes after any stage2-v1-gpu result
  exists, except via dated note BEFORE affected reruns.
- No editing §7 above, ever, once a result exists.
- g3-v2-gpu artifacts are read-only inputs; never regenerated or modified.
