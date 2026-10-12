from __future__ import annotations

import argparse
import csv
import gc
import json
import sys
import threading
import time
from datetime import datetime

import cupy as cp
import numpy as np
from scipy.special import jv

from common import RESULTS, write_json
from gpu_bench.gpu_proposal import (
    GPUExactQuantumProposal,
    _chebyshev_coefficients,
)
from qemcmc import GAMMA_RANGE, TIME_RANGE, planted_instance
import stage1_train


TV_LIMIT = 1e-10
NORM_DRIFT_LIMIT = 1e-12
VRAM_FRACTION_LIMIT = 0.80
NUMERICAL_DRAWS = 20
SMOKE_UPDATES = 3
REGISTERED_UPDATES = 100
REGISTERED_CHAINS = 1
REGISTERED_PROPOSAL_STEPS = 32
WALL_TIME_CEILINGS_SECONDS = {22: 120.0, 24: 360.0}


def _evolve_at_degree(
    proposal: GPUExactQuantumProposal,
    state_index: int,
    evolution_time: float,
    gamma: float,
    degree: int,
) -> cp.ndarray:
    diagonal_cpu = (1.0 - gamma) * proposal.alpha * proposal.problem_energy_cpu
    diagonal = (1.0 - gamma) * proposal.alpha * proposal.problem_energy
    lower = float(np.min(diagonal_cpu) - gamma * proposal.n_spins)
    upper = float(np.max(diagonal_cpu) + gamma * proposal.n_spins)
    center = 0.5 * (lower + upper)
    radius = 0.5 * (upper - lower)
    if radius == 0.0:
        result = cp.zeros(proposal.size, dtype=cp.complex128)
        result[state_index] = 1.0
        return result

    orders = np.arange(degree + 1)
    coefficients = 2.0 * ((-1j) ** orders) * jv(
        orders, evolution_time * radius
    )
    coefficients[0] *= 0.5
    coefficients_gpu = cp.asarray(coefficients, dtype=cp.complex128)
    vector0 = cp.zeros(proposal.size, dtype=cp.complex128)
    vector0[state_index] = 1.0
    result = coefficients_gpu[0] * vector0
    if degree >= 1:
        vector1 = proposal._scaled_matvec(
            vector0, diagonal, gamma, center, radius
        )
        result += coefficients_gpu[1] * vector1
        for order in range(2, degree + 1):
            vector2 = 2.0 * proposal._scaled_matvec(
                vector1, diagonal, gamma, center, radius
            ) - vector0
            result += coefficients_gpu[order] * vector2
            vector0, vector1 = vector1, vector2
    result *= cp.exp(
        cp.asarray(-1j * evolution_time * center, dtype=cp.complex128)
    )
    cp.cuda.get_current_stream().synchronize()
    return result


def _numerical_checks(bits: int) -> dict:
    fields, couplings, _ = planted_instance(bits, 0)
    proposal = GPUExactQuantumProposal(couplings, fields)
    rng = np.random.default_rng(606 + bits)
    draws = []
    for draw in range(NUMERICAL_DRAWS):
        evolution_time = float(rng.uniform(*TIME_RANGE))
        gamma = float(rng.uniform(*GAMMA_RANGE))
        state_index = int(rng.integers(proposal.size))
        diagonal = (1.0 - gamma) * proposal.alpha * proposal.problem_energy_cpu
        lower = float(np.min(diagonal) - gamma * bits)
        upper = float(np.max(diagonal) + gamma * bits)
        radius = 0.5 * (upper - lower)
        degree = len(
            _chebyshev_coefficients(
                evolution_time * radius, proposal.coefficient_tolerance
            )
        ) - 1
        state_d = _evolve_at_degree(
            proposal, state_index, evolution_time, gamma, degree
        )
        state_2d = _evolve_at_degree(
            proposal, state_index, evolution_time, gamma, 2 * degree
        )
        norm_d = float(cp.linalg.norm(state_d).item())
        norm_2d = float(cp.linalg.norm(state_2d).item())
        probability_d = cp.abs(state_d) ** 2
        probability_d /= cp.sum(probability_d)
        probability_2d = cp.abs(state_2d) ** 2
        probability_2d /= cp.sum(probability_2d)
        tv = 0.5 * float(cp.sum(cp.abs(probability_d - probability_2d)).item())
        draws.append({
            "draw": draw,
            "evolution_time": evolution_time,
            "gamma": gamma,
            "state_index": state_index,
            "degree_d": degree,
            "degree_2d": 2 * degree,
            "tv_d_vs_2d": tv,
            "norm_drift_d": abs(norm_d - 1.0),
            "norm_drift_2d": abs(norm_2d - 1.0),
        })
        del state_d, state_2d, probability_d, probability_2d

    max_tv = max(row["tv_d_vs_2d"] for row in draws)
    max_norm_drift = max(
        max(row["norm_drift_d"], row["norm_drift_2d"])
        for row in draws
    )
    return {
        "draws": draws,
        "draw_count": NUMERICAL_DRAWS,
        "max_tv_d_vs_2d": max_tv,
        "tv_limit_exclusive": TV_LIMIT,
        "chebyshev_degree_doubling_passed": max_tv < TV_LIMIT,
        "max_state_norm_drift": max_norm_drift,
        "norm_drift_limit_exclusive": NORM_DRIFT_LIMIT,
        "state_norm_passed": max_norm_drift < NORM_DRIFT_LIMIT,
    }


def _monitor_device_memory(stop: threading.Event, sample: dict) -> None:
    while not stop.is_set():
        free, total = cp.cuda.runtime.memGetInfo()
        sample["total_bytes"] = int(total)
        sample["peak_used_bytes"] = max(
            sample["peak_used_bytes"], int(total - free)
        )
        stop.wait(0.02)


def _run_training_smoke(bits: int, invocation_tag: str) -> dict:
    level = "a" if bits == 12 else "c"
    cp.get_default_memory_pool().free_all_blocks()
    gc.collect()
    free, total = cp.cuda.runtime.memGetInfo()
    memory = {
        "total_bytes": int(total),
        "baseline_used_bytes": int(total - free),
        "peak_used_bytes": int(total - free),
    }
    stop = threading.Event()
    monitor = threading.Thread(
        target=_monitor_device_memory, args=(stop, memory), daemon=True
    )
    monitor.start()
    argv = [
        "stage1_train.py",
        "--level", level,
        "--sampler", "qemcmc",
        "--seed", "0",
        "--updates", str(REGISTERED_UPDATES),
        "--chains", str(REGISTERED_CHAINS),
        "--proposal-steps", str(REGISTERED_PROPOSAL_STEPS),
        "--backend", "gpu",
        "--bits", str(bits),
        "--tag", invocation_tag,
        "--max-updates-this-invocation", str(SMOKE_UPDATES),
    ]
    original_argv = sys.argv
    try:
        sys.argv = argv
        stage1_train.main()
    finally:
        sys.argv = original_argv
        stop.set()
        monitor.join()
        free, total = cp.cuda.runtime.memGetInfo()
        memory["peak_used_bytes"] = max(
            memory["peak_used_bytes"], int(total - free)
        )

    history_path = RESULTS / (
        f"stage1_qemcmc_level-{level}_0_{invocation_tag}_history.csv"
    )
    with history_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    elapsed = [float(row["elapsed_seconds"]) for row in rows]
    per_update_seconds = [
        value - (elapsed[index - 1] if index else 0.0)
        for index, value in enumerate(elapsed)
    ]
    peak_fraction = memory["peak_used_bytes"] / memory["total_bytes"]
    ceiling = WALL_TIME_CEILINGS_SECONDS.get(bits)
    max_update_seconds = max(per_update_seconds)
    return {
        "level": level,
        "sampler": "qemcmc",
        "seed": 0,
        "registered_budget": {
            "updates": REGISTERED_UPDATES,
            "chains": REGISTERED_CHAINS,
            "proposal_steps": REGISTERED_PROPOSAL_STEPS,
        },
        "completed_smoke_updates": len(rows),
        "requested_smoke_updates": SMOKE_UPDATES,
        "run_artifact_tag": invocation_tag,
        "history": str(history_path),
        "per_update_seconds": per_update_seconds,
        "max_update_seconds": max_update_seconds,
        "wall_time_ceiling_seconds": ceiling,
        "wall_time_passed": ceiling is None or max_update_seconds <= ceiling,
        **memory,
        "peak_vram_fraction": peak_fraction,
        "vram_fraction_limit_exclusive": VRAM_FRACTION_LIMIT,
        "vram_passed": peak_fraction < VRAM_FRACTION_LIMIT,
        "three_update_smoke_passed": len(rows) == SMOKE_UPDATES,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bits", type=int, choices=(12, 16, 22, 24), required=True)
    args = parser.parse_args()
    if cp.cuda.runtime.getDeviceCount() < 1:
        raise RuntimeError("gate G6 requires a CUDA device")

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    invocation_tag = f"g6-{args.bits}bit-{timestamp}-smoke"
    verdict_path = RESULTS / f"gate_g6_{args.bits}bit_{timestamp}_verdict.json"
    device_id = cp.cuda.Device().id
    properties = cp.cuda.runtime.getDeviceProperties(device_id)
    raw_name = properties["name"]
    gpu_name = raw_name.decode() if isinstance(raw_name, bytes) else str(raw_name)
    verdict = {
        "gate": "G6a" if args.bits == 22 else "G6b" if args.bits == 24 else "G6-development-smoke",
        "bits": args.bits,
        "timestamp": timestamp,
        "gpu_name": gpu_name,
        "cuda_device_id": device_id,
        "code_file_tag": stage1_train.STAGE1_LEVEL_C_CODE_TAGS.get(args.bits),
        "fixed_tolerances": {
            "tv_exclusive": TV_LIMIT,
            "state_norm_drift_exclusive": NORM_DRIFT_LIMIT,
            "peak_vram_fraction_exclusive": VRAM_FRACTION_LIMIT,
        },
    }
    try:
        training = _run_training_smoke(args.bits, invocation_tag)
        numerical = _numerical_checks(args.bits)
        gpu_identity_passed = args.bits != 24 or "RTX 4090" in gpu_name
        verdict.update({
            "training_smoke": training,
            "numerical_checks": numerical,
            "gpu_identity_required": "RTX 4090" if args.bits == 24 else None,
            "gpu_identity_passed": gpu_identity_passed,
        })
        verdict["passed"] = bool(
            training["three_update_smoke_passed"]
            and training["vram_passed"]
            and training["wall_time_passed"]
            and numerical["chebyshev_degree_doubling_passed"]
            and numerical["state_norm_passed"]
            and gpu_identity_passed
        )
    except Exception as error:
        verdict.update({
            "passed": False,
            "error_type": type(error).__name__,
            "error": str(error),
        })
    write_json(verdict_path, verdict)
    print(json.dumps({"verdict": str(verdict_path), **verdict}, indent=2))
    if not verdict["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
