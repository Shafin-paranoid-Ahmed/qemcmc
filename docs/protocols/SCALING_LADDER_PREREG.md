# Scaling-Ladder Pre-Registration — 20 → 22 → 24-bit Codes

Date: 2026-07-14 (written AFTER Stage-2 verdicts were logged, BEFORE any
ladder implementation or run; parent-prereg §11.4 planned this document).
Parent: `QSAMPLER_EBM_PREREG.md`. Stage-2 spec and verdicts:
`STAGE2_ADAPTIVE_PREREG.md`, `results/ADAPTIVE_REPORT.md`. All parent hard
don'ts inherited (no wall-clock/advantage claims, append-only logs, no
editing locked expectations after results exist).

## 0. Question under test (no new claim)

The ladder makes NO new mechanism claim. It tests whether the two logged
empirical findings survive as the code width grows toward the practical
exact-enumeration ceiling:

1. **Stage-1 Level-C headline (G3):** fixed QeMCMC produces the most
   accurate negative-phase gradients of all fresh-chain approximate
   samplers on real crop codes (20-bit: 5.30 vs mh-uniform 7.37, PCD 11.48).
2. **Stage-2 finding:** persistent-chain QeMCMC matches-or-beats PCD, and
   the persistence effect on Level C is small (qemcmc-p 5.21 vs fixed 5.30).

Both were measured only at 20 bits. A reviewer's obvious question — "does
this die at the next size up?" — is answered here with two rungs: **22-bit
on the local RTX 5070** and **24-bit on the lab RTX 4090 (conditional,
§3.G6b — that machine's GPU is still unconfirmed by nvidia-smi)**. 24 bits
(~16.7M states) is the last rung where exact-enumeration ground truth
remains cheap per update; the ladder therefore ends there by design.

## 1. What is fixed by prior stages (not re-litigated)

- Primary metric: negative-phase gradient error vs exact enumeration
  (G3 §3 caveat: TV/KL/mode-coverage are degenerate at 32 samples).
- Budget: 100 updates × 1 chain × 32 proposals, seeds 0/1/2, GPU backend.
- QeMCMC proposal law: randomized (t, γ) with TIME_RANGE (2, 20),
  GAMMA_RANGE (0.25, 0.6) — the Stage-1 fixed law, unchanged.
- Level C data path: frozen encoder from Stage 0, `build_codes.py`
  quantization, same splits, true labels only.

## 2. Design

### 2.1 Rungs and tags

| Rung | Bits | Machine | Tag | Status |
|---|---|---|---|---|
| 0 | 20 | local RTX 5070 | g3-v2-gpu / stage2-v1-gpu | DONE (reused, no rerun) |
| 1 | 22 | local RTX 5070 | ladder22-v1-gpu | this prereg |
| 2 | 24 | lab RTX 4090 | ladder24-v1-gpu | CONDITIONAL on §3.G6b |

### 2.2 Level and codes

**Level C only.** It carries both findings under test; Levels A/B are
synthetic controls whose Stage-1/2 story (persistence dominates) does not
change with width in a way this thesis needs to establish. New code files
are generated at 22 and 24 bits with the SAME frozen encoder, splits, and
quantization procedure (`build_codes.py`), tagged like the existing 16/20-bit
files. Code-quality metrics (bit usage, per-class code entropy, duplicate
rate) are logged exactly as at 20 bits and reported as-is; if wider codes
are degenerate (e.g. dead bits), that is reported, not tuned away.

### 2.3 Sampler set (reduced, per parent §11.4)

| # | Sampler | Why it is on the ladder |
|---|---|---|
| 1 | exact | ground-truth reference (defines gradient error = 0) |
| 2 | qemcmc (fixed, fresh) | finding 1 under test |
| 3 | mh-uniform | best classical fresh-chain sampler on C at 20 bits — the comparator for finding 1 |
| 4 | pcd | best classical persistent sampler — the comparator for finding 2 |
| 5 | qemcmc-p | finding 2 under test |
| 6 | adaptive-qemcmc-p-proxy | the deployable invention variant (proxy reward, no oracle), carried to report whether lossless proxy control survives scaling |

Dropped: gibbs, mh-local, pt (dominated at 20 bits on C), the exact-reward
adaptive variants (oracle study, completed in Stage 2), fresh adaptive
variants (adaptation-alone verdict already negative and logged).

6 samplers × 3 seeds = **18 runs per rung** (36 if the 24-bit rung fires).

### 2.4 Budget and projected cost (estimates, not gates)

Identical scientific budget (100 × 1 × 32). From the logged GPU benchmark
(single proposal: 0.044 s at 18 bits, 0.144 s at 20 → ×~3.3 per +2 bits)
and measured 18–25 min per 20-bit run: quantum runs ≈ 60–90 min each at 22
bits (9 quantum runs ≈ 10–14 h on the 5070) and ≈ 3–6 h each at 24 bits
(≈ 30–50 h on the 4090). Classical runs are minutes. Exact enumeration per
update: 0.087 s at 20 bits → ≈ 1.4 s at 24 bits — ground truth stays cheap.
VRAM: the evolution is state-vector-bound (2^22 complex128 = 64 MiB, 2^24
= 256 MiB per workspace vector) — comfortable on 12 GiB, comfortable on the
4090's 16+ GiB if G6b confirms it.

## 3. Gates (before any official ladder run)

**G6a — 22-bit feasibility and numerics (local).**
(a) `--bits 22` smoke (3 updates, qemcmc, level-c, seed 0) completes with
the budget guard clean and peak VRAM < 80% of the device.
(b) Numerical self-consistency at 22 bits, since the 20-bit CPU-vs-GPU
acceptance (worst TV 2.5e-13) cannot be repeated in reasonable time on the
weak CPU: (i) Chebyshev degree-doubling check — proposal distribution TV
between degree D and 2D below 1e-10 across 20 random (t, γ, state) draws;
(ii) state-norm drift < 1e-12 per evolution. Failure = stop and debug; no
tolerance loosening without a dated amendment here.
(c) Per-update wall time ≤ 2 min at 22 bits; if exceeded, STOP and report
(the 24-bit rung would be infeasible and the ladder redesign goes through a
dated amendment, not silent downscaling).

**G6b — 24-bit entry (lab, all required).**
(a) `nvidia-smi` output from the lab PC confirming the RTX 4090 (this has
NEVER been verified), captured into an `environment.json` like the 5070's.
(b) A working CUDA/CuPy environment on that machine; G6a checks (a)/(b)
repeated there at 24 bits, plus per-update wall time ≤ 6 min.
(c) **Cross-machine guard:** the 20-bit fixed-qemcmc Level-C seed-0 run
rerun on the 4090 must reproduce the g3-v2-gpu mean gradient error within
1% (bit-identity is NOT expected across GPU architectures; the Stage-2
guard's bit-identity standard applies only same-machine). Failure = stop;
diagnose before any 24-bit run counts.
If any part of G6b fails or the 4090 does not materialize, the 22-bit rung
alone is the ladder result and is reported as such — a one-rung ladder is
an honest, pre-registered possible outcome.

## 4. Metrics and pre-registered decision rules

Primary: median-across-seeds mean gradient error over all 100 updates,
Level C, per rung. Secondary: updates 51–100. Fixed now:

1. **"Finding 1 survives" (per rung):** qemcmc beats mh-uniform (best
   classical fresh-chain) on the primary metric at that rung. The 20-bit
   margin is 28% relative (5.30 vs 7.37); the rung's margin is reported
   next to it. Shrinking-but-positive = survives; sign flip = does not.
2. **"Finding 2 survives" (per rung):** min(qemcmc, qemcmc-p) beats pcd on
   the primary metric.
3. **Proxy control at scale:** adaptive-qemcmc-p-proxy within 5% of
   qemcmc-p on the primary metric (the Stage-2 lossless-transfer result
   restated as a bound). Outside 5% in either direction is reported as the
   scaling behavior of the controller — no re-tuning.
4. **Trend statement:** a 20/22/24 table of all samplers' primary values.
   Trends are DESCRIBED; no extrapolation beyond 24 bits is claimed under
   any outcome.
5. Downstream NLL/Macro-F1 reported last, no headline (parent §7).

## 5. Honest limits, stated in advance

1. Two (at most three) points do not establish an asymptotic scaling law
   and none will be claimed; the ladder answers "does the finding survive
   the sizes we can ground-truth," nothing more.
2. Rung-to-rung comparisons are of the same pipeline at different widths.
   Absolute gradient-error magnitudes are not comparable across rungs
   (larger state spaces, different learned couplings); only within-rung
   sampler orderings and margins are.

   **2026-07-14 correction (before any ladder run, code verified):** an
   earlier draft of this limit called the wider codes "NEW datasets, not
   refinements of the 20-bit codes." That is factually wrong and is
   corrected here. `build_codes.py` encodes via `PCA(n_components=bits)`
   sign codes on frozen ResNet features, and sklearn PCA components are
   nested — the first 20 components of a 22-component fit are identical to a
   20-component fit. So the 22-bit code IS the 20-bit code with 2 appended
   bits, and 24-bit is that plus 2 more; bits 0–19 are bit-identical across
   rungs. This is a cleaner design than the draft claimed (the added bits
   are strictly additional PCA directions, not a re-quantization), and the
   implementation must preserve it (no re-seeding or reshuffling that would
   break the nesting). It does NOT make absolute magnitudes comparable —
   the enumerated landscape and the learned model still differ by width —
   so the within-rung-only comparison rule above stands unchanged.
3. The 24-bit rung inherits cross-machine risk (different GPU, driver,
   CuPy build); the §3.G6b guard bounds but does not eliminate it.
4. All comparisons remain per-proposal-step quality on a simulator.

## 6. Pre-registered expectations (locked 2026-07-14, never edited)

- Finding 1 survives at 22 bits (modal expectation), possibly with a
  reduced margin as the enumerable landscape grows relative to a fixed
  32-proposal budget.
- Finding 2 survives at both rungs; on Level C the persistence delta stays
  small (as in Stage 2).
- Proxy-adaptive stays within the 5% band of qemcmc-p.
- Wider codes are expected to have more low-usage bits (quantizer spreading)
  — a data-quality observation, reported alongside rule 4.
- Genuinely uncertain: whether the qemcmc-vs-mh-uniform margin grows or
  shrinks with width. Either direction is a reportable thesis result
  (growing = the quantum proposal exploits structure that widens with the
  code; shrinking = the 20-bit result is near its best size).

## 7. Deliverables and handoff

- Implementation by Codex from this spec; smokes and unit tests only —
  **ALL official run commands are appended to RUN_COMMANDS.md and launched
  by the user, never by an agent** (standing run-ownership protocol).
- Code: extend `--bits` choices with 22/24 + code-file tag mapping in
  `read_dataset`; `build_codes.py` invocations at 22/24 bits; G6a/G6b check
  scripts writing verdict JSONs into `results/`; no change to samplers,
  controller, rewards, or the trainer's scientific path.
- `LADDER_REPORT.md` (results/) answering §4, with the 20/22/24 trend table.
- Dated entries in RESULTS_LOG.md/CHANGELOG.md at every gate; artifacts
  tagged ladder22-v1-gpu / ladder24-v1-gpu.

## Hard don'ts (inherited + specific)

- No new samplers, no controller changes, no reward changes, no budget
  changes; the ladder varies EXACTLY ONE thing (bit width).
- No tolerance loosening in G6a/G6b without a dated amendment recorded
  before the affected rerun.
- No editing §6 after any ladder result exists; contradictions ARE findings.
- No asymptotic or quantum-advantage claims at any rung, under any outcome.
- 24-bit rung does not start until every G6b item is logged.
