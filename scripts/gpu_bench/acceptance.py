"""Mandatory numerical-acceptance matrix for the GPU QeMCMC backend."""

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
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PILOT / "scripts"))

import cupy as cp  # noqa: E402
import numpy as np  # noqa: E402

from gpu_proposal import GPUExactQuantumProposal  # noqa: E402
from qemcmc import (  # noqa: E402
    ExactQuantumProposal,
    GAMMA_RANGE,
    TIME_RANGE,
    index_to_spins,
    layden_reference_instance,
    planted_instance,
)

TV_LIMIT = 1e-8


def _cases() -> list[tuple[str, np.ndarray, np.ndarray, int]]:
    bias, coupling, _ = layden_reference_instance()
    cases = [("layden-reference-n10", bias, coupling, 613)]
    for n in (12, 14, 16):
        for seed in (0, 1, 2):
            bias, coupling, _ = planted_instance(n, seed)
            state_index = int(np.random.default_rng(10_000 + n * 10 + seed).integers(1 << n))
            cases.append((f"planted-n{n}-seed{seed}", bias, coupling, state_index))
    return cases


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    time_grid = np.linspace(TIME_RANGE[0], TIME_RANGE[1], 3)
    gamma_grid = np.linspace(GAMMA_RANGE[0], GAMMA_RANGE[1], 3)
    rows: list[dict] = []
    worst: dict | None = None
    started_all = time.perf_counter()

    for case_name, bias, coupling, state_index in _cases():
        cpu = ExactQuantumProposal(bias, coupling)
        gpu = GPUExactQuantumProposal(coupling, bias)
        state = index_to_spins(state_index, len(bias))
        for evolution_time in time_grid:
            for gamma in gamma_grid:
                started = time.perf_counter()
                expected = cpu.distribution(state, float(evolution_time), float(gamma))
                actual = gpu.distribution(state_index, float(evolution_time), float(gamma))
                tv = 0.5 * float(np.sum(np.abs(expected - actual)))
                row = {
                    "case": case_name,
                    "n_spins": int(len(bias)),
                    "state_index": int(state_index),
                    "evolution_time": float(evolution_time),
                    "gamma": float(gamma),
                    "tv_distance": tv,
                    "passed": bool(tv <= TV_LIMIT),
                    "elapsed_seconds": float(time.perf_counter() - started),
                }
                rows.append(row)
                if worst is None or tv > worst["tv_distance"]:
                    worst = row
                print(
                    f"{case_name} t={evolution_time:.2f} gamma={gamma:.3f} "
                    f"TV={tv:.3e}",
                    flush=True,
                )

    assert worst is not None
    payload = {
        "schema_version": 1,
        "acceptance_rule": "TV distance <= 1e-8 for every case/grid point",
        "tv_limit": TV_LIMIT,
        "grid_points_per_instance": 9,
        "instance_count": len(_cases()),
        "comparison_count": len(rows),
        "passed": bool(all(row["passed"] for row in rows)),
        "worst_case": worst,
        "elapsed_seconds": float(time.perf_counter() - started_all),
        "gpu": cp.cuda.runtime.getDeviceProperties(0)["name"].decode(),
        "cupy_version": cp.__version__,
        "cuda_runtime_version": int(cp.cuda.runtime.runtimeGetVersion()),
        "driver_version": int(cp.cuda.runtime.driverGetVersion()),
        "rows": rows,
    }
    output = RESULTS / "numerical_acceptance.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {output}")
    if not payload["passed"]:
        raise SystemExit(
            f"FAIL: worst TV={worst['tv_distance']:.3e} exceeds {TV_LIMIT:.1e}"
        )
    print(f"PASS: worst TV={worst['tv_distance']:.3e}")


if __name__ == "__main__":
    main()
