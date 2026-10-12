"""Six-case SciPy acceptance extension for planted 20-spin proposals."""

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
from qemcmc import ExactQuantumProposal, index_to_spins, planted_instance  # noqa: E402

TV_LIMIT = 1e-8
# Keep the six-case extension at the registered lower time boundary: the
# 2^20 SciPy Krylov reference is the validation bottleneck, not the GPU path.
PARAMETERS = ((2.0, 0.25), (2.0, 0.60))


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    started_all = time.perf_counter()
    for seed in (0, 1, 2):
        bias, coupling, _ = planted_instance(20, seed)
        cpu = ExactQuantumProposal(bias, coupling)
        gpu = GPUExactQuantumProposal(coupling, bias)
        rng = np.random.default_rng(20_000 + seed)
        for case_index, (evolution_time, gamma) in enumerate(PARAMETERS):
            state_index = int(rng.integers(1 << 20))
            state = index_to_spins(state_index, 20)
            started = time.perf_counter()
            expected = cpu.distribution(state, evolution_time, gamma)
            cpu_seconds = time.perf_counter() - started
            started = time.perf_counter()
            actual = gpu.distribution(state_index, evolution_time, gamma)
            gpu_seconds = time.perf_counter() - started
            tv = 0.5 * float(np.sum(np.abs(expected - actual)))
            row = {
                "case": f"planted-n20-seed{seed}-case{case_index}",
                "seed": seed,
                "state_index": state_index,
                "evolution_time": evolution_time,
                "gamma": gamma,
                "tv_distance": tv,
                "passed": bool(tv <= TV_LIMIT),
                "scipy_seconds": cpu_seconds,
                "gpu_seconds": gpu_seconds,
            }
            rows.append(row)
            print(
                f"{row['case']} TV={tv:.3e} "
                f"SciPy={cpu_seconds:.1f}s GPU={gpu_seconds:.3f}s",
                flush=True,
            )
    worst = max(rows, key=lambda row: row["tv_distance"])
    payload = {
        "schema_version": 1,
        "acceptance_rule": "TV distance <= 1e-8 for every planted 20-spin case",
        "tv_limit": TV_LIMIT,
        "comparison_count": len(rows),
        "passed": bool(all(row["passed"] for row in rows)),
        "worst_case": worst,
        "elapsed_seconds": time.perf_counter() - started_all,
        "gpu": cp.cuda.runtime.getDeviceProperties(0)["name"].decode(),
        "cupy_version": cp.__version__,
        "rows": rows,
    }
    output = RESULTS / "numerical_acceptance_n20.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {output}")
    if not payload["passed"]:
        raise SystemExit(f"FAIL: worst TV={worst['tv_distance']:.3e}")


if __name__ == "__main__":
    main()
