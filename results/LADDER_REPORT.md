# Scaling-Ladder Report — 20 → 22 bit

Status: **22-bit rung complete, 2026-07-16.** 18/18 runs (6 samplers × 3
seeds) completed and validated at 22 bits under gate G6a (PASSED
2026-07-15). Answers the pre-registered decision rules of
`docs/still_exploring/quantum_sampler_ebm/SCALING_LADDER_PREREG.md` §4.
The 24-bit rung remains **conditional on gate G6b**. September 7 status
correction: the July 11 research-PC environment record confirms a 24-GB RTX
4090; the earlier statement that its hardware was unconfirmed is superseded.
This does not establish current availability or passage of the separate G6b
feasibility/numerics gate. No 24-bit artifacts are present in this checkout.
Per the prereg, a one-rung ladder is an honest
pre-registered outcome and is reported as such here.

## Primary comparison (Level C, median-across-seeds mean gradient error)

| Sampler | 20-bit | 22-bit | Notes |
|---|---|---|---|
| exact | 0.0000 | 0.0000 | ground-truth reference |
| qemcmc (fixed, fresh) | 5.296 | 6.006 | finding 1 under test |
| mh-uniform | 7.458 | 8.466 | best classical fresh-chain comparator |
| pcd | 11.474 | 13.137 | best classical persistent comparator |
| qemcmc-p | 5.209 | 5.853 | finding 2 under test |
| adaptive-qemcmc-p-proxy | 5.511 | 6.279 | deployable invention variant |

(20-bit columns: qemcmc/mh-uniform/pcd from g3-v2-gpu, qemcmc-p/proxy from
stage2-v1-gpu. Absolute magnitudes are NOT comparable across rungs — larger
state space, different learned couplings, per prereg §5 limit 2 — only
within-rung orderings and margins are.)

## Pre-registered decision rules (§4), answered

**Rule 1 — "Finding 1 survives" (qemcmc beats mh-uniform): YES.** At 22 bits
qemcmc 6.006 vs mh-uniform 8.466 — a **29.1% relative margin**, essentially
identical to the 20-bit margin (28.9%: 5.296 vs 7.458). No per-seed overlap.
The quantum sampler's fresh-chain gradient-accuracy advantage on real crop
codes is **stable under the width increase**, neither growing nor shrinking —
answering the §6 genuinely-uncertain question in the "near its best size,
holds flat" direction.

**Rule 2 — "Finding 2 survives" (persistent quantum beats PCD): YES,
decisively.** min(qemcmc, qemcmc-p) = 5.853 vs PCD 13.137 — a **55% relative
margin**, wider than the 20-bit 55% (5.209 vs 11.474 = 55%) in absolute terms
and identical in relative terms. Persistent QeMCMC continues to dominate the
best classical persistent sampler on real codes at the larger width.

**Rule 3 — proxy control at scale (within 5% of qemcmc-p):
7.3% — just OUTSIDE the band, reported as the scaling behavior with no
re-tuning.** adaptive-qemcmc-p-proxy 6.279 vs qemcmc-p 5.853. At 20 bits the
proxy variant was within ~5.8% of qemcmc-p; at 22 bits the budget-free
controller costs a slightly larger 7.3% relative to plain persistence. The
honest reading, consistent with the Stage-2 finding that persistence (not
adaptation) carries the gain: the online controller's exploration overhead is
not repaid on the smooth crop-code landscape, and that small cost grows mildly
with width. The controller still beats every classical sampler (proxy 6.279 <
mh-uniform 8.466 < pcd 13.137) — it is not harmful, just not additive over
persistence. No hyperparameters were touched.

**Rule 4 — trend statement.** Both quantum findings hold flat in relative
terms from 20→22 bits; the classical comparators (mh-uniform, pcd) degrade at
the same rate as the quantum samplers, so the orderings are preserved
end-to-end. No extrapolation beyond the measured widths is claimed.

## Code quality (prereg §2.2)

22-bit Level-C codes: val linear-probe macro-F1 0.459/0.455/0.445 (majority
0.159), PCA explained variance 0.655. Healthy codes, no degenerate/dead bits;
the +2 nested PCA directions (bits 0–19 bit-identical to the 20-bit codes,
per the 2026-07-14 nesting correction) add explained variance as expected.

## Verdict vs pre-registered expectations (§6)

| Locked expectation | Outcome |
|---|---|
| Finding 1 survives at 22 bits (possibly reduced margin) | CONFIRMED; margin held flat (29.1% vs 28.9%), not reduced |
| Finding 2 survives; persistence delta stays small on C | CONFIRMED (55% margin vs PCD; qemcmc-p vs qemcmc gap small: 5.853 vs 6.006) |
| Proxy-adaptive within 5% of qemcmc-p | NOT met — 7.3%, slightly outside; reported as scaling behavior, no re-tune |
| Wider codes have more low-usage bits | Not observed as degeneracy; codes healthy (see above) |
| qemcmc-vs-mh-uniform margin — direction uncertain | Resolved: margin holds flat with width (the "near best size" reading) |

## Bottom line

The Stage-1/Stage-2 quantum-sampler findings are **not artifacts of the
20-bit enumeration size** — they reproduce at 22 bits with stable relative
margins. The one movement is that the online controller's small overhead
relative to plain persistence grows mildly with width (5.8% → 7.3%), which
strengthens rather than weakens the Stage-2 honest conclusion that
persistence is the load-bearing effect. Pending the 24-bit rung (conditional
on the 4090), the ladder confirms the findings are width-robust across the
sizes we can ground-truth.
