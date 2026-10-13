> Historical research record. Original machine paths and commands are retained as provenance. Use the standalone [README](README.md) and runbook for current setup.

# Quantum-Sampler EBM Handoff

Last updated: 2026-09-07.

Stages 0, 1, and 2 and the 22-bit ladder are complete. The original
Stage-0-only handoff scope is superseded by the dated preregistrations,
[results log](RESULTS_LOG.md), and completed reports linked in [README](docs/historical/ORIGINAL_README.md).

The 24-bit rung has no completed results here. The research-PC environment
record confirms a 24-GB RTX 4090 on July 11; that historical hardware check
does not by itself pass the rung-specific G6b feasibility/numerics gate.
Verify current machine state and gate artifacts before any authorized run.

Hard invariants remain:

- Use only the existing QCNN split manifests as the label source.
- Keep the encoder frozen and fit code-generation transforms on training data.
- Use the shared class-conditional energy model and matched proposal budgets.
- Report simulator proposal-step quality, not hardware or wall-clock advantage.
- Preserve completed artifacts and exact resume budgets; use the current runbook.
- Append dated logs and keep official launches author-owned.

The dominant Stage-2 finding is persistence, not the adaptive controller.
Do not rewrite negative registered outcomes or infer downstream classification
advantage from the sampler's gradient-accuracy ranking.
