> Historical research record. Original machine paths and commands are retained as provenance. Use the standalone [README](../../README.md) and runbook for current setup.

# Quantum-Sampler EBM Pilot

Last updated: 2026-09-07.

Completed: Stage-0 gates, **84 Stage-1 runs**, **60 Stage-2 runs plus a
reproduction guard**, and **18 runs at 22 bits**. No completed 24-bit
artifacts are present in this checkout.

The simulator results support a sampling/gradient-accuracy finding at matched
proposal budgets. Chain persistence explains most of the Stage-2 improvement;
adaptation alone did not meet its overall success rule. This is not evidence
of hardware speedup, quantum advantage, or superior crop classification.

Read [Stage 1](../../results/SAMPLER_REPORT.md), [Stage 2](../../results/ADAPTIVE_REPORT.md),
[22-bit scaling](../../results/LADDER_REPORT.md), and [the results log](../../RESULTS_LOG.md).
The registered protocols are in
[the protocols directory](../protocols/).

Labels come only from the frozen `full_qcnn_pilot/splits/` manifests. The
ResNet-18 encoder is pretrained and frozen; PCA is fit on each seed's training
partition. Keep these results distinct from SSL-HDC and legacy E0–E3.

See [RUN_COMMANDS](ORIGINAL_RUN_COMMANDS.md) for reproduction and [HANDOFF](../../HANDOFF.md)
for continuation. Historical gate commands are not pending work.
