# Pre-Registration — Adaptive Quantum Negative-Phase Training for Energy-Based Models

Date: 2026-07-12 (written BEFORE any code; expectations below must never be edited
after results exist)
Status: PRE-REGISTERED, awaiting supervisor buy-in. Code folder (to be created by
the implementing agent): `qsampler_ebm_pilot/` at repo root.
Relationship to the Full-QCNN pilot: independent second contribution; the QCNN
pilot and its ablations (`full_qcnn_pilot/`) continue unchanged and are NOT
modified by this project.

---

## 0. One-page summary (supervisor-facing)

**Research question.** Energy-based models (EBMs) need samples from their own
Boltzmann distribution at every training step (the "negative phase"). Classical
samplers mix slowly on rugged, multimodal energy landscapes. Gate-model
quantum-enhanced MCMC (QeMCMC; Layden et al., Nature 618, 2023) provably
converges and shows better mixing on hard Ising distributions. We ask:

> (Stage 1) Does QeMCMC produce more accurate negative-phase samples and
> gradients than strong classical samplers at matched proposal budgets, and does
> that translate into better EBM training on real crop-image latent codes?
> (Stage 2 — the invention) Can the quantum proposal circuit be **co-adapted
> during training** — its parameters chosen to minimize measured negative-phase
> gradient error — and does that adaptation beat the fixed sampler?

**Novelty claim (verified against literature 2026-07-12; see §2).** NOT "first
quantum sampler for ML" (annealer-based RBM training exists since 2015) and NOT
"first QeMCMC inside a training loop" (Sajjan, Singh & Kais, npj Quantum Inf. 12:93,
2026 — verified — uses QeMCMC in neural-network-quantum-state training for
chemistry). The open slot, and our claim:

> Gate-model QeMCMC as the negative-phase sampler of a classical discrete-latent
> EBM trained on real image-derived codes, with exact-enumeration validation and
> strong matched classical baselines (Stage 1); and a gradient-aware, co-adaptive
> quantum proposal schedule as a new hybrid training algorithm (Stage 2).

**Design in one line.** Frozen image encoder → 16–20-bit discrete latent code →
ONE shared class-conditional EBM p(z, y) → negative-phase sampling by QeMCMC vs
classical samplers → classification via p(y|z).

**The methodological luxury.** At ≤20 bits the state space (≤2^20 ≈ 1.05M states)
is exactly enumerable: exact Boltzmann distribution, exact gradients, exact
sampler bias. Every claim is measured against ground truth — no "samples look
better" hand-waving.

**Honest limits, stated in advance.** (a) On a simulator we measure mixing/sample
quality PER PROPOSAL STEP, never wall-clock speedup — quantum proposals cost more
to simulate by construction. (b) The Stage-2 training signal (exact gradient)
exists only because the model is enumerable; Stage 2 is therefore a MECHANISTIC
study, and whether the learned adaptation transfers to proxy signals
(ESS/autocorrelation) is itself a pre-registered question, not an afterthought.
(c) Real crop codes may yield an easy (smooth) landscape where classical sampling
already suffices — the three-level testbed (§5) makes that outcome a finding, not
a failure.

---

## 1. Hard constraints (binding, as in the QCNN pilot)

1. **True labels only.** All supervision/selection/evaluation uses the trusted
   splits in `full_qcnn_pilot/splits/split_seed{0,1,2}.json` (derived from
   `Data/test.csv`). Never use `Data/train.csv` / `Data/val.csv` labels. Images:
   `Data/test/<id>/<id>.jpg`.
2. **Never touch any `.docx`/`.pdf`.** Only MD/PY/CSV/JSON inside
   `qsampler_ebm_pilot/`; this spec folder under `docs/` is edited only for the
   dated reconciliation/decision notes, never the pre-registered expectations.
3. **Simulator honesty.** Statevector ceiling ~20–25 qubits. No wall-clock
   advantage claims, ever. All sampler comparisons at matched proposal budgets:
   same energy function, initialization, number of proposal steps, sample budget,
   data, and update rule — only the proposal mechanism changes.
4. **No post-result tuning, no test-set peeking, no seed cherry-picking.**
   Selection on val only; test touched once per configuration.
5. **Frozen encoder.** The image encoder is fixed before EBM training begins and
   never fine-tuned (its choice is a Stage-0 decision, logged once). PCA/learned
   features ARE allowed here — unlike the QCNN pilot, the quantum component's job
   is sampling, not classification, so there is no encoding-degeneracy rule.
6. **Tagged artifacts, append-only logs.** Every run writes uniquely named files
   (`{model}_{sampler}_{level}_{seed}_...`); `RESULTS_LOG.md`/`CHANGELOG.md`
   entries are dated and appended, never rewritten. Cross-machine sync via git
   only.

## 2. Prior-art map (gate zero — PASSED 2026-07-12, narrow claim)

- Adachi & Henderson 2015 (arXiv:1510.06356); Benedetti et al. 2016
  (arXiv:1609.02542); Srivastava & Sundararaghavan 2023 — annealer-sampled
  RBM/BM training. Blocks any "first quantum-sampled EBM" claim.
- Layden et al., Nature 618:500 (2023) — gate-model QeMCMC foundation. Sampling
  only; no EBM training, no real data.
- QAOA-MC (arXiv:2305.08789); neural-assisted quantum MCMC (arXiv:2506.01335) —
  sampler improvements, not in-loop EBM training on real data.
- **Sajjan, Singh & Kais, npj Quantum Inf. 12:93 (2026) — VERIFIED 2026-07-12
  via nature.com:** QeMCMC (Trotterized Hamiltonian-evolution proposals, surrogate
  RBM) inside neural-network-quantum-state training for spin/molecular systems.
  Blocks "first QeMCMC in a training loop." Does NOT touch classical image data.
- Multi-mode QA-VAE (arXiv:2604.00919) — real images (CelebA) but annealing.
- **Stage-2 sub-check still owed:** before claiming the adaptive controller as
  new, run one focused search on "adaptive / learned / optimized QeMCMC proposal
  parameters" (Layden already randomizes evolution time t and mixer strength γ;
  tuning them ONLINE from gradient error is believed open but must be confirmed).
  This is Stage-2 gate G4 (§6).

## 3. Architecture (fixed by this pre-registration)

```
Crop image (Data/test/<id>/<id>.jpg)
  → frozen encoder (Stage-0 choice; default: ImageNet-pretrained ResNet-18
    penultimate features, 512-d)
  → binarization to a 16–20-bit code z (default: top-k PCA components fit on
    TRAIN split only, sign/median threshold; k pre-registered per level)
  → ONE shared class-conditional EBM over (z, y): Ising/RBM-form energy
    E_θ(z, y) with biases, pairwise couplings, and class-conditional terms
  → training: maximum likelihood; positive phase from data, negative phase from
    the sampler under test
  → classification: argmax_y p_θ(y | z); report Macro-F1, accuracy, ECE, NLL
    with the same metrics code as the QCNN pilot (reuse
    full_qcnn_pilot/scripts/metrics.py)
```

The quantum circuit NEVER sees the image. Its only job is proposing moves while
sampling from e^{−E_θ}. One shared energy model across all samples (persistent
chains stay meaningful); per-image energy functions are explicitly forbidden.

## 4. Samplers (the only thing that varies)

Classical controls (all mandatory in Stage 1):
- Gibbs / block Gibbs; Metropolis–Hastings (local + uniform proposals);
- persistent contrastive divergence (PCD);
- parallel tempering (the strong baseline — beating only Gibbs is not a result);
- exact enumeration (ground truth, and the "infinite budget" reference).

Quantum sampler:
- Layden-style QeMCMC: proposals from time evolution under H = α H_problem +
  (1−α) H_mixer, Trotterized, measured in the computational basis;
  Metropolis–Hastings accept/reject on top (guarantees correct stationary
  distribution regardless of proposal quality). Stage 1 uses Layden's randomized
  (t, γ) scheme verbatim. Simulated with PennyLane `default.qubit` (broadcast
  where possible — same lesson as the QCNN pilot; never `lightning.qubit` for
  batched work without benchmarking first).

## 5. Three-level testbed (every outcome is a finding)

- **Level A — planted rugged control:** low-temperature spin-glass instances
  (12–16 spins) known to mix poorly classically. Purpose: reproduce the
  Layden-style mixing advantage and validate our implementation. If quantum shows
  no advantage here, the implementation (not the idea) is wrong — stop and debug.
- **Level B — synthetic multimodal codes:** constructed discrete clusters with
  controlled barrier heights and mode imbalance, used as EBM training data.
  Purpose: connect mixing advantage to a learning problem at known difficulty.
- **Level C — real crop latent codes:** codes from §3 on the trusted splits.
  Purpose: determine whether real data enters the regime where sampling quality
  matters.

Interpretation table (pre-registered): helps A+B+C = strong result; A+B only =
crop landscape insufficiently rugged (honest, expected-plausible); A only =
mechanism real but does not transfer to learning; nowhere = implementation or
assumption failure (report as such).

## 6. Stages and kill gates

- **G0 (PASSED 2026-07-12):** literature slot open under the narrow claim (§2).
- **Stage 0 (agent, ~days):** scaffold `qsampler_ebm_pilot/` (README, HANDOFF,
  RESULTS_LOG, CHANGELOG, scripts/); build codes for Level C; enumerate-exact
  utilities; verify code-quality (train a logistic head on the 20-bit codes —
  it must beat majority-class meaningfully or the codes carry no signal).
- **G1 — "is an EBM worthwhile here?" (end week 1):** classical-sampled EBM on
  Level C vs logistic regression, small MLP, naive Bayes on the same codes. ALSO
  measure landscape ruggedness of the trained EBM (mode count / barrier estimate
  via enumeration). If the EBM is far worse than the simple baselines OR its
  landscape is near-unimodal, STOP Stage-1-on-C and re-scope to Levels A+B only
  (still a reportable mechanistic thesis).

### 2026-07-12 reconciliation note - quantitative G1 proceed/stop rule

This dated amendment was added after Stage-0 diagnostics were seen and before
the reconciled rerun. It is an operational proceed/stop rule, not a scientific
claim, and does not alter Section 8 or any pre-registered expectation.

G1 PASS requires both: the shared EBM mean validation Macro-F1 across seeds
0/1/2 is within 0.10 of the best simple-baseline mean, and exact enumeration
finds at least 5 local modes on at least 2 of 3 seeds. Otherwise G1 fails. The
reconciled rerun uses a class-weighted small-MLP loss and leaves test untouched.
- **G2 — mixing reproduction (end week 2):** QeMCMC on Level A shows the expected
  mixing advantage (spectral gap / autocorrelation vs classical proposals) at
  12–16 spins. If not, STOP and debug; no Stage-1 training runs until G2 passes.

### 2026-07-12 reconciliation note - G2 metric amendment (censored IAT, median, magnetization observable)

This dated amendment was made after observing the inf-poisoned 2026-07-12 G2 run
(`results/qemcmc_exact_level-a_all_verdict.json`, `passed: false`,
`qemcmc`/`local` mean IAT both `inf`) and BEFORE any rerun. It is an operational
metric-definition fix, not a scientific claim, and does not alter Section 8 or
any pre-registered expectation.

Inspection of the per-chain mixing CSV showed the `inf` verdict was a metric
artifact, not a mixing failure: per chain, QeMCMC beat local Metropolis in 6 of
9 head-to-head comparisons (IAT 5-10 vs 15-35, acceptance 0.23-0.42). Two chains
had zero post-burn-in energy variance for different reasons — `local`@16
spins/seed 0 (acceptance 0.023) genuinely froze in a local minimum, i.e. slow
classical mixing that the estimator scored as unmeasurable instead of bad;
`qemcmc`@12 spins/seed 1 (acceptance 0.38) was moving between degenerate
equal-energy states, so the energy observable alone could not see that the
chain was mixing. `autocorrelation_time` returned `inf` on zero variance in
either case, and the gate aggregated across seeds with a mean, so a single
`inf` poisoned the whole sampler's score.

The amendment, effective for all G2 reruns from this date forward:

(a) **Censored IAT.** A chain with zero post-burn-in variance in an observable
returns an IAT equal to the post-burn-in trace length (the standard treatment
for stuck/degenerate chains — "at least as long as the trace," not "undefined")
instead of `inf`.

(b) **Median aggregation.** Cross-seed aggregation uses the median instead of
the mean, so one still-extreme chain cannot dominate the comparison.

(c) **Second observable.** Magnetization IAT (mean spin per step, from the same
chains, no extra proposal budget) is added alongside energy IAT, so mixing that
is invisible to a degenerate energy trace (the qemcmc@12/seed1 case above) is
still measurable.

(d) **Gate rule.** G2 passes iff, for every spin count in {12, 14, 16}, QeMCMC's
median IAT is lower than both local's and uniform's median IAT, on BOTH
observables (energy and magnetization). Parallel tempering remains reported,
not gate-defining, as originally specified.

- **G3 — Stage-1 plug-in complete (~week 4):** stable end-to-end EBM training
  with QeMCMC negative phase on A/B/C; full metric suite (§7) vs all classical
  controls, 3 seeds. This is the mandatory baseline AND the fallback thesis.

### 2026-07-13 decision note - Stage-1 bit width

Stage 1 uses 16-bit codes on Levels A, B, and C, within the pre-registered
16-20-bit range. This decision was recorded before any Stage-1 run. G2 measured
approximately 3.3 simulator seconds per exact QeMCMC proposal at 16 bits; the
20-bit state space is at least 20 times more costly in the measured simulator
path and would make matched in-loop proposal budgets infeasible. Sixteen bits
also keep exact enumeration at 2^16 = 65,536 states, allowing the exact
negative-phase gradient to remain the per-update primary reference. Existing
20-bit Level-C artifacts remain unchanged as the G1 record; Stage 1 uses newly
tagged 16-bit artifacts fit from each trusted TRAIN partition only.

### 2026-07-13 decision note (later) - GPU backend adoption and 20-bit supersession

Supersedes the bit-width note above; recorded BEFORE any completed official
Stage-1 matrix. Two facts changed since the morning note: (a) a GPU port of the
exact QeMCMC proposal (CuPy Chebyshev evolution, RTX 5070) passed numerical
acceptance against the SciPy reference (90/90 cases, worst TV 2.5e-13) and
measured 102x at 16 bits, 763x at 20 bits (0.144 s/proposal), 82x on the
realistic Stage-1 update shape — clearing the pre-registered >=2x adoption
rule; (b) the 2026-07-13 power outage killed the g3-v1 CPU run of Level B-easy
mid-matrix, so no completed official matrix exists under g3-v1.

Decisions, all within the pre-registered 16-20-bit range and unchanged §8:
1. The official Stage-1 matrix reruns on the GPU backend under tag
   **g3-v2-gpu** at **20-bit** codes on all levels (the top of the registered
   range, now affordable: a 20-bit QeMCMC run is minutes, not hours).
2. The interrupted 16-bit g3-v1 artifacts are retained untouched as a
   cross-backend/cross-width consistency record, not as official results.
3. The per-update exact-enumeration reference (2^20 = 1,048,576 states) must
   be vectorized (GPU or batched CPU) and its per-update cost logged; the
   exact gradient remains the primary reference as registered.
4. A scaling-ladder extension (22-bit on the local RTX 5070; 24-bit on the lab
   PC RTX 4090, reduced sampler set) is planned as a separate pre-registered
   note AFTER the g3-v2-gpu matrix completes; nothing beyond 20 bits enters
   the official Stage-1 claim.
5. Backend stays fixed within a tagged matrix; the sampler comparison remains
   mixing/quality per proposal step — the GPU speedup is an engineering fact
   about simulation cost, never a quantum wall-clock claim.
- **G4 — Stage-2 entry gate:** the adaptive-QeMCMC mini literature check (§2) is
  clean, AND G3 shows a measurable sampler-quality difference somewhere (else
  there is no signal for the controller to exploit — report and stop).
- **Stage 2 (~weeks 4–8, the invention):**
  1. **Gradient-aware sampler objective:** choose/adapt proposal parameters
     (t, γ, depth, proposal locality) to minimize ‖∇θL_sampled − ∇θL_exact‖²,
     computable exactly at ≤20 bits.
  2. **Adaptive controller:** parameter schedule driven by measured landscape
     state (temperature/ruggedness proxies) across training.
  3. **Budget-aware switching:** classical proposals on easy landscapes, quantum
     on hard — decided online.
  Evaluation: adaptive vs fixed QeMCMC vs best classical, same budgets, 3 seeds,
  on all three levels. **Transfer sub-question (pre-registered, addresses the
  scaling paradox):** re-run the controller using only proxy signals
  (ESS/autocorrelation, no exact gradient) and report how much of the adaptive
  gain survives — this is the honest answer to "the method trains where it isn't
  needed."

### 2026-07-14 note - G4 passed; Stage 2 pre-registered in a separate document

G0-G4 have all passed (verdicts dated in `qsampler_ebm_pilot/RESULTS_LOG.md`).
The Stage-2 design is pre-registered in
`docs/still_exploring/quantum_sampler_ebm/STAGE2_ADAPTIVE_PREREG.md`
(2026-07-14, before any Stage-2 code). That document instantiates the three
mechanisms above — the gradient-aware objective as a bandit reward, the
adaptive controller as a discounted-UCB policy over (t, γ) cells, and
budget-aware switching as a classical arm of the same controller — and adds
one dated new factor motivated by the G3 finding that PCD's chain persistence
beat per-step mixing in-loop: a persistent-chain QeMCMC variant. Section 8
below is unchanged.

## 7. Metrics (primary chain, in causal order)

1. Negative-phase gradient error vs exact gradient (primary);
2. effective sample size per proposal step; autocorrelation time;
3. TV distance / KL to the exact Boltzmann distribution; mode coverage;
4. EBM training stability and convergence (loss curves across seeds);
5. held-out negative log-likelihood (exactly computable at ≤20 bits);
6. downstream Macro-F1 / accuracy / ECE / NLL on the trusted test split.

Classification accuracy is the LAST link, not the headline. "Quantum mixes
better but classification is unchanged" is a publishable mechanistic result.

## 8. Pre-registered expectations (do not edit after results exist)

- Level A: QeMCMC mixing advantage over local/uniform classical proposals —
  expected (this reproduces the literature); parallel tempering may still match
  it — genuinely uncertain, and that comparison is itself a contribution.
- Level C: trained-EBM landscape likely NOT rugged enough for the quantum
  proposal to matter at 16–20 bits; Stage-1 plug-in tie on crop data is the
  modal expected outcome.
- Stage 2: adaptation expected to reduce gradient error vs fixed (t, γ) on
  Levels A/B; transfer under proxy-only signals expected PARTIAL; crop-level
  gains uncertain.
- Nothing here is expected to demonstrate quantum advantage, and no such claim
  will be made under any outcome.

## 9. Team split (4 people)

A: quantum sampler + Stage-2 controller (critical path). B: classical samplers +
exact-enumeration ground truth (full role — the B-QUAD lesson). C: EBM training
loop, metrics, experiment orchestration. D: data/codes/splits, logging
discipline, writing. Weekly gate reviews against §6.

## 10. Deliverables

`qsampler_ebm_pilot/` mirroring the QCNN pilot: HANDOFF.md, RESULTS_LOG.md,
CHANGELOG.md, scripts/, results/ (per-run CSV/JSON + summary tables),
SAMPLER_REPORT.md (Stage 1) and ADAPTIVE_REPORT.md (Stage 2) with the §5
interpretation table filled in, and dated honest log entries after every gate.

## Hard don'ts

- No wall-clock/speedup claims; no "first quantum sampler for ML" phrasing.
- No per-image energy functions; no encoder fine-tuning after Stage 0.
- No new baselines/mechanisms mid-study; changes require a dated reconciliation
  note here BEFORE the affected runs (wire-conflict lesson from ABLATIONS.md).
- No editing §8 after any result exists. If a result contradicts an expectation,
  that IS the finding.
