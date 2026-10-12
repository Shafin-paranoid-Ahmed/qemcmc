"""Numerical checks and before/after 20-bit exact-reference timing."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT
RESULTS = PILOT / "results" / "gpu_bench"
os.environ.setdefault("CUPY_CACHE_DIR", str(ROOT / ".cache" / "cupy"))
sys.path.insert(0, str(PILOT / "scripts"))

import numpy as np  # noqa: E402

from exact import all_spins  # noqa: E402
from gpu_bench.gpu_exact import GPUExactReference  # noqa: E402
from stage1_train import SharedIsingEBM, exact_stats  # noqa: E402

MAX_ABS_LIMIT = 1e-10


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    checks = []
    for bits in (12, 16):
        states = all_spins(bits)
        model = SharedIsingEBM(bits, 4, 17)
        _, expected, expected_log_z = exact_stats(model, states)
        reference = GPUExactReference(states)
        _, actual, actual_log_z = reference.stats(model)
        max_abs = float(np.max(np.abs(expected - actual)))
        checks.append({
            "bits": bits,
            "probability_max_abs": max_abs,
            "log_partition_abs": abs(expected_log_z - actual_log_z),
            "passed": bool(max_abs <= MAX_ABS_LIMIT),
        })

    states = all_spins(20)
    model = SharedIsingEBM(20, 4, 17)
    started = time.perf_counter()
    exact_stats(model, states)
    exact_stats(model, states)
    numpy_per_update = time.perf_counter() - started

    reference = GPUExactReference(states)
    reference.stats(model)
    reference.log_partition(model)
    samples = []
    for _ in range(3):
        started = time.perf_counter()
        reference.stats(model)
        reference.log_partition(model)
        samples.append(time.perf_counter() - started)
    gpu_per_update = float(np.median(samples))
    payload = {
        "schema_version": 1,
        "numerical_rule": "max absolute exact-probability difference <= 1e-10",
        "numerical_checks": checks,
        "passed": bool(all(check["passed"] for check in checks)),
        "bits": 20,
        "classes": 4,
        "numpy_legacy_seconds_per_update": numpy_per_update,
        "gpu_seconds_per_update": gpu_per_update,
        "gpu_repeats_seconds": samples,
        "speedup": numpy_per_update / gpu_per_update,
    }
    output = RESULTS / "exact_reference_n20_benchmark.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["passed"]:
        raise SystemExit("GPU exact-reference numerical check failed")


if __name__ == "__main__":
    main()
