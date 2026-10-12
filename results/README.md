# Results

Generated artifacts use `{model}_{sampler}_{level}_{seed}_*` filenames.

Current coverage (2026-09-07): 84 Stage-1 histories, 60 Stage-2 histories plus
one reproduction-guard history, and 18 histories at 22 bits. No 24-bit result
is present. Read [Stage 1](SAMPLER_REPORT.md), [Stage 2](ADAPTIVE_REPORT.md),
and [the scaling ladder](LADDER_REPORT.md); tagged smoke/older outputs are
not extra official runs. Findings concern simulator sampling quality, not
hardware speedup or a downstream classification win.
