# Quantum Sampler-in-the-Loop EBM Training — One-Page Summary

*Team summary, 2026-07-14. Full record: `QSAMPLER_EBM_PREREG.md`,
`STAGE2_ADAPTIVE_PREREG.md`, `qsampler_ebm_pilot/results/{SAMPLER,ADAPTIVE}_REPORT.md`.*

## What the experiment is

We train a small **energy-based model (EBM)** on binary codes derived from
our real crop-disease images (a frozen ResNet encoder compresses each image
to a 20-bit code; labels are the true test-set labels). Training an EBM
requires drawing samples from the model's own distribution at every
gradient update — the "negative phase" — and the quality of those samples
directly controls the quality of the learning signal. That sampling step is
where a quantum computer could plausibly help: we plug in a
**quantum-enhanced MCMC sampler (QeMCMC**, Layden et al., Nature 2023),
which proposes moves by evolving a quantum superposition, and compare it
head-to-head against the standard classical samplers (Gibbs, Metropolis
variants, parallel tempering, and persistent contrastive divergence / PCD).

Because our codes are ≤20 bits, we can **enumerate all 2²⁰ states exactly**
— so unlike almost all prior work, every sampler is scored against the
*exact* ground-truth gradient. Everything runs on a simulator (GPU); we
make no speed or "quantum advantage" claims — the question is sample
*quality* at a matched proposal budget.

## The questions (pre-registered before running)

1. **Stage 1:** Inside a real training loop — not on a static benchmark —
   does the quantum sampler produce more accurate gradients than classical
   samplers? Tested on 4 difficulty levels (planted rugged controls,
   synthetic easy/hard, and the real crop codes), 7 samplers, 3 seeds.
2. **Stage 2 (the thesis invention):** Can the quantum proposal be
   **adapted online while the EBM trains** — a bandit controller that picks
   evolution-time/mixing parameters each update, rewarded by gradient
   accuracy? And does a cheap, budget-free reward signal (accepted jump
   distance) work as well as the expensive oracle reward? Prior art
   (QAOA-MC) tunes proposals *offline* for a *fixed* target; ours adapts
   *online* against a *drifting* in-training target.

## The findings

- **Stage 1 headline:** on the real crop codes, QeMCMC delivered the most
  accurate gradients of every approximate sampler — error 5.30 vs 7.37 for
  the best classical, with no overlap across seeds. On the synthetic rugged
  levels, however, PCD won — because its chains persist across updates.
  Sampler choice measurably changes the training signal (≈3× spread).
- **Stage 2 headline:** giving the quantum sampler **persistent chains**
  flips the synthetic levels too: persistent QeMCMC beats PCD on **all
  four levels** (by 13–52%). Honest attribution: persistence, not the
  adaptive controller, carries this win — adaptation alone helped on 2 of
  4 levels and missed its pre-registered overall criterion.
- **The invention's result:** the online controller works as a mechanism
  (it demonstrably learns, e.g. converging on long-evolution/low-mixing
  proposals for the crop codes), and — the practically important part —
  running it on the **free proxy reward matches the exact-gradient oracle
  everywhere** (≥79% transfer, mostly ~100%). The oracle isn't needed.
- Two pre-registered expectations were contradicted and are reported as
  findings (classical-arm usage pattern inverted; adaptation-alone verdict
  negative). All gates G0–G5 passed, with two dated, pre-rerun amendments.

## Why it matters / what's next

This is, to our knowledge, the first exact-ground-truth study of a
gate-model quantum sampler *inside* EBM training on real image-derived
codes, with a pre-registered online adaptation study on top. Next: a
pre-registered scaling ladder (22-bit locally, 24-bit on the lab 4090) to
show the findings survive at the largest sizes we can still ground-truth.
