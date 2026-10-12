"""User-launched CPU-vs-GPU backend benchmark.

This script is intentionally not invoked by the implementing agent.  It times
at least 20 complete proposal distributions at each requested size and the
Stage-1 pattern of rebuilding theta's diagonal followed by 32 sequential
proposals.  Comparisons concern backend throughput only; they are not MCMC
mixing or wall-clock-advantage claims.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import platform
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
import scipy  # noqa: E402
from scipy.sparse import diags  # noqa: E402
from scipy.sparse.linalg import expm_multiply  # noqa: E402

from gpu_proposal import GPUExactQuantumProposal, problem_energies  # noqa: E402
from qemcmc import (  # noqa: E402
    GAMMA_RANGE,
    TIME_RANGE,
    mixer_matrix,
    planted_instance,
)


class CPUExactProposal:
    """Production SciPy distribution algorithm without its G2-only size guard.

    The timed path is the same sparse-Hamiltonian expm_multiply call used by
    qemcmc.ExactQuantumProposal. Only the untimed energy-table construction is
    made memory-safe for the exploratory 18/20-spin cases.
    """

    def __init__(self, bias: np.ndarray, coupling: np.ndarray):
        self.n = int(len(bias))
        self.mixer = mixer_matrix(self.n)
        self.rebuild_problem_diagonal(coupling, bias)

    def rebuild_problem_diagonal(
        self, coupling: np.ndarray, bias: np.ndarray
    ) -> None:
        self.bias = np.asarray(bias, dtype=np.float64)
        self.coupling = np.asarray(coupling, dtype=np.float64)
        self.problem_energy = problem_energies(self.coupling, self.bias)
        denominator = np.sqrt(
            np.sum(np.triu(self.coupling, 1) ** 2) + np.sum(self.bias**2)
        )
        self.alpha = float(np.sqrt(self.n) / denominator) if denominator > 0 else 1.0

    def distribution(self, state_index: int, evolution_time: float, gamma: float) -> np.ndarray:
        initial = np.zeros(1 << self.n, dtype=np.complex128)
        initial[state_index] = 1.0
        hamiltonian = (
            (1.0 - gamma) * self.alpha * diags(self.problem_energy)
            + gamma * self.mixer
        )
        evolved = expm_multiply((-1j * evolution_time) * hamiltonian, initial)
        probability = np.abs(evolved) ** 2
        return probability / probability.sum()


def _timed_proposals(
    proposal: CPUExactProposal | GPUExactQuantumProposal,
    schedule: list[tuple[int, float, float]],
) -> list[float]:
    timings = []
    for index, evolution_time, gamma in schedule:
        started = time.perf_counter()
        proposal.distribution(index, evolution_time, gamma)
        if isinstance(proposal, GPUExactQuantumProposal):
            cp.cuda.get_current_stream().synchronize()
        timings.append(float(time.perf_counter() - started))
    return timings


def _summary_row(category: str, n: int, backend: str, timings: list[float]) -> dict:
    return {
        "category": category,
        "n_spins": n,
        "backend": backend,
        "measurements": len(timings),
        "median_seconds": float(np.median(timings)),
        "mean_seconds": float(np.mean(timings)),
        "min_seconds": float(np.min(timings)),
        "max_seconds": float(np.max(timings)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", type=int, default=20)
    parser.add_argument("--spins", type=int, nargs="+", default=[12, 14, 16, 18, 20])
    parser.add_argument("--stage-proposals", type=int, default=32)
    parser.add_argument("--stage-repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260713)
    args = parser.parse_args()
    if args.proposals < 20:
        parser.error("--proposals must be >=20 (pre-registered benchmark minimum)")
    if args.stage_proposals != 32:
        parser.error("--stage-proposals must remain 32 for the Stage-1 shape")
    if args.stage_repeats < 1:
        parser.error("--stage-repeats must be positive")
    required_spins = {12, 14, 16, 18, 20}
    if set(args.spins) != required_spins or len(args.spins) != len(required_spins):
        parser.error("--spins must contain each of 12 14 16 18 20 exactly once")
    return args


def main() -> None:
    args = parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    acceptance_path = RESULTS / "numerical_acceptance.json"
    if not acceptance_path.exists():
        raise SystemExit("Run acceptance.py first; numerical_acceptance.json is missing")
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    expected_cases = {"layden-reference-n10"} | {
        f"planted-n{n}-seed{seed}"
        for n in (12, 14, 16)
        for seed in (0, 1, 2)
    }
    expected_points = {
        (case, round(float(evolution_time), 12), round(float(gamma), 12))
        for case in expected_cases
        for evolution_time in np.linspace(TIME_RANGE[0], TIME_RANGE[1], 3)
        for gamma in np.linspace(GAMMA_RANGE[0], GAMMA_RANGE[1], 3)
    }
    rows_from_acceptance = acceptance.get("rows", [])
    observed_points = {
        (
            row.get("case"),
            round(float(row.get("evolution_time", np.nan)), 12),
            round(float(row.get("gamma", np.nan)), 12),
        )
        for row in rows_from_acceptance
    }
    current_gpu = cp.cuda.runtime.getDeviceProperties(0)["name"].decode()
    acceptance_valid = (
        acceptance.get("passed") is True
        and acceptance.get("tv_limit") == 1e-8
        and acceptance.get("comparison_count") == 90
        and acceptance.get("instance_count") == 10
        and acceptance.get("grid_points_per_instance") == 9
        and acceptance.get("worst_case", {}).get("tv_distance", np.inf) <= 1e-8
        and acceptance.get("gpu") == current_gpu
        and acceptance.get("cupy_version") == cp.__version__
        and acceptance.get("cuda_runtime_version")
        == int(cp.cuda.runtime.runtimeGetVersion())
        and acceptance.get("driver_version") == int(cp.cuda.runtime.driverGetVersion())
        and len(rows_from_acceptance) == 90
        and observed_points == expected_points
        and all(
            row.get("passed") is True
            and float(row.get("tv_distance", np.inf)) <= 1e-8
            for row in rows_from_acceptance
        )
    )
    if not acceptance_valid:
        raise SystemExit(
            "Numerical acceptance provenance is missing, stale, or failed; "
            "the benchmark is not actionable"
        )

    rng = np.random.default_rng(args.seed)
    rows: list[dict] = []
    raw: dict[str, dict] = {}
    suite_started = time.perf_counter()

    for n in args.spins:
        bias, coupling, _ = planted_instance(n, 0)
        cpu = CPUExactProposal(bias, coupling)
        gpu = GPUExactQuantumProposal(coupling, bias)
        schedule = [
            (
                int(rng.integers(1 << n)),
                float(rng.uniform(*TIME_RANGE)),
                float(rng.uniform(*GAMMA_RANGE)),
            )
            for _ in range(args.proposals)
        ]
        # Untimed warm-up compiles the CUDA kernel and primes both algorithms.
        warm = schedule[0]
        cpu.distribution(*warm)
        gpu.distribution(*warm)

        cpu_timings = _timed_proposals(cpu, schedule)
        gpu_timings = _timed_proposals(gpu, schedule)
        rows.append(_summary_row("single_proposal", n, "cpu_scipy", cpu_timings))
        rows.append(_summary_row("single_proposal", n, "gpu_cupy_chebyshev", gpu_timings))
        raw[str(n)] = {"cpu_seconds": cpu_timings, "gpu_seconds": gpu_timings}
        print(
            f"n={n}: CPU median={np.median(cpu_timings):.4f}s, "
            f"GPU median={np.median(gpu_timings):.4f}s, "
            f"speedup={np.median(cpu_timings) / np.median(gpu_timings):.2f}x",
            flush=True,
        )

    # Realistic Stage-1 shape: Stage 1 builds four class-conditioned problem
    # diagonals from shared couplings, then advances one chain through 32
    # proposals. Identical labels, (t, gamma), and inverse-CDF draws are used.
    n = 16
    base_bias, base_coupling, _ = planted_instance(n, 0)
    class_offsets = rng.normal(0.0, 0.05, size=(4, n))
    class_biases = [base_bias + offset for offset in class_offsets]
    cpu = [CPUExactProposal(bias, base_coupling) for bias in class_biases]
    gpu = [GPUExactQuantumProposal(base_coupling, bias) for bias in class_biases]
    cpu_updates: list[float] = []
    gpu_updates: list[float] = []
    for _ in range(args.stage_repeats):
        perturbation = rng.normal(0.0, 0.01, size=(n, n))
        perturbation = np.triu(perturbation, 1)
        coupling = base_coupling + perturbation + perturbation.T
        updated_biases = [
            bias + rng.normal(0.0, 0.01, size=n) for bias in class_biases
        ]
        initial_state = int(rng.integers(1 << n))
        labels = rng.integers(0, 4, size=args.stage_proposals)
        times = rng.uniform(*TIME_RANGE, size=args.stage_proposals)
        gammas = rng.uniform(*GAMMA_RANGE, size=args.stage_proposals)
        uniforms = rng.random(args.stage_proposals)

        def run_update(proposals, is_gpu: bool) -> None:
            for proposal, bias in zip(proposals, updated_biases):
                proposal.rebuild_problem_diagonal(coupling, bias)
            state = initial_state
            for label, evolution_time, gamma, draw in zip(
                labels, times, gammas, uniforms
            ):
                probabilities = proposals[int(label)].distribution(
                    state, float(evolution_time), float(gamma)
                )
                state = int(
                    np.searchsorted(np.cumsum(probabilities), draw, side="right")
                )
                state = min(state, probabilities.size - 1)
            if is_gpu:
                cp.cuda.get_current_stream().synchronize()

        started = time.perf_counter()
        run_update(cpu, False)
        cpu_updates.append(float(time.perf_counter() - started))

        started = time.perf_counter()
        run_update(gpu, True)
        gpu_updates.append(float(time.perf_counter() - started))

    rows.append(_summary_row("rebuild_plus_32", n, "cpu_scipy", cpu_updates))
    rows.append(_summary_row("rebuild_plus_32", n, "gpu_cupy_chebyshev", gpu_updates))
    stage_speedup = float(np.median(cpu_updates) / np.median(gpu_updates))
    adopted = bool(acceptance["passed"] and stage_speedup >= 2.0)

    csv_path = RESULTS / "gpu_backend_benchmark.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "schema_version": 1,
        "decision_rule": (
            "adopt only if numerical acceptance passes everywhere and n=16 "
            "rebuild-plus-32 speedup is >=2x"
        ),
        "verdict": "adopt GPU backend later" if adopted else "stay on CPU",
        "adopt_gpu": adopted,
        "numerical_acceptance_passed": bool(acceptance["passed"]),
        "numerical_acceptance_worst_tv": acceptance["worst_case"]["tv_distance"],
        "stage1_n16_speedup": stage_speedup,
        "parameters": vars(args),
        "environment": {
            "python": platform.python_version(),
            "cupy": cp.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "gpu": cp.cuda.runtime.getDeviceProperties(0)["name"].decode(),
            "gpu_vram_bytes": int(cp.cuda.runtime.getDeviceProperties(0)["totalGlobalMem"]),
            "cuda_runtime_version": int(cp.cuda.runtime.runtimeGetVersion()),
            "driver_version": int(cp.cuda.runtime.driverGetVersion()),
        },
        "summary_rows": rows,
        "raw_single_proposal_timings": raw,
        "raw_stage1_shape": {
            "class_conditioned_diagonals": 4,
            "sequential_proposals_per_update": 32,
            "cpu_seconds": cpu_updates,
            "gpu_seconds": gpu_updates,
        },
        "elapsed_seconds": float(time.perf_counter() - suite_started),
    }
    json_path = RESULTS / "gpu_backend_verdict.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {csv_path}")
    print(f"WROTE {json_path}")
    print(f"VERDICT: {payload['verdict']} (Stage-1 speedup={stage_speedup:.2f}x)")


if __name__ == "__main__":
    main()
