# Extraction provenance

- Source: https://github.com/yes-yes-company/THESIS, commit `da7ad651d7e3eaebfa2216950a5f2dd0d0640a1a`.
- Source area: `qsampler_ebm_pilot/`, plus its registered specifications.
- Date: 2026-10-12. Clean snapshot; original Git history remains upstream.
- Only tracked source files were selected. Existing unrelated `.gitignore` changes
  and ignored local environments/data/caches were not copied.
- Source files remain untouched. Hashes in SOURCE_MANIFEST.json record both the
  selected original bytes and the extraction's modified bytes.
- Frozen result JSON/CSV files and split manifests are preserved byte for byte.
- Small tracked checkpoints and historical figures are included; raw datasets
  and large ignored training artifacts are excluded.

## Changes for independent operation

Executable paths now resolve from this checkout. The data root is configurable.
New README/runbook/dependency files and a dataset-free smoke check were added.
Historical documentation retains its original commands, with an explicit notice.
Relative Markdown links were relocated; external thesis context links target the
source commit. Scientific algorithms, registered budgets, and splits are unchanged.

QEMCMC vendors the byte-identical QCNN metrics module and seed 0/1/2 manifests.
The metrics subprocess defaults to the current interpreter, with an explicit
QEMCMC_METRICS_PYTHON override for separate GPU/CPU environments. GPU cache paths
are local and operating-system temporary-directory settings are preserved.

## Source contributor record

Names and counts below come from `git shortlog -s HEAD -- <source paths>`;
they attribute the original work, not just this snapshot commit.

```text
22	ParanoidAndroid
```

See NOTICE.md for licensing status and VALIDATION.md for verification evidence.
