from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from common import RESULTS, write_json, write_rows
from qemcmc import ExactQuantumProposal, energy, planted_instance

FIELDS = [
    "spins", "seed", "sampler", "proposal_steps", "burn_in",
    "energy_iat_steps", "magnetization_iat_steps",
    "ess_per_proposal", "magnetization_ess_per_proposal",
    "acceptance", "sampler_seconds", "elapsed_seconds",
]
FLOAT_FIELDS = FIELDS[5:]
INT_FIELDS = ("spins", "seed", "proposal_steps", "burn_in")


def censored_autocorrelation_time(values: np.ndarray, max_lag: int = 500) -> float:
    """IAT censored at the post-burn-in trace length on zero variance (a
    stuck/degenerate chain), instead of inf — 2026-07-12 reconciliation:
    one inf was poisoning the mean across a sampler's seeds."""
    x = np.asarray(values, dtype=float) - np.mean(values)
    variance = np.dot(x, x) / len(x)
    if variance <= 1e-15:
        return float(len(x))
    total = 1.0
    for lag in range(1, min(max_lag, len(x) // 4)):
        rho = np.dot(x[:-lag], x[lag:]) / ((len(x) - lag) * variance)
        if rho <= 0:
            break
        total += 2.0 * rho
    return float(total)


def metropolis(state, current, proposal, bias, coupling, beta, rng):
    candidate = energy(proposal, bias, coupling)
    accepted = rng.random() < np.exp(min(0.0, -beta * (candidate - current)))
    return (proposal, candidate, 1) if accepted else (state, current, 0)


def run_chain(kind, bias, coupling, beta, steps, seed, quantum=None):
    if kind not in {"local", "uniform", "qemcmc", "parallel_tempering"}:
        raise ValueError(f"unknown sampler: {kind}")
    rng = np.random.default_rng(seed)
    n = len(bias)
    initial = rng.choice((-1.0, 1.0), n)
    sampler_seconds = 0.0
    accepted = 0
    energy_trace, magnetization_trace = [], []
    if kind == "parallel_tempering":
        betas = beta / np.geomspace(1.0, 8.0, 8)
        states = np.stack([initial] + [rng.choice((-1.0, 1.0), n) for _ in range(7)])
        energies = np.array([energy(state, bias, coupling) for state in states])
        for step in range(steps):
            if step % 2 == 0:
                replica = int(rng.integers(len(betas)))
                proposal = states[replica].copy()
                proposal[rng.integers(n)] *= -1
                states[replica], energies[replica], hit = metropolis(
                    states[replica], energies[replica], proposal, bias, coupling, betas[replica], rng
                )
                accepted += hit
            else:
                replica = int(rng.integers(len(betas) - 1))
                log_accept = (betas[replica] - betas[replica + 1]) * (
                    energies[replica] - energies[replica + 1]
                )
                if np.log(rng.random()) < min(0.0, log_accept):
                    states[[replica, replica + 1]] = states[[replica + 1, replica]]
                    energies[[replica, replica + 1]] = energies[[replica + 1, replica]]
                    accepted += 1
            energy_trace.append(energies[0])
            magnetization_trace.append(float(np.mean(states[0])))
        return np.asarray(energy_trace), np.asarray(magnetization_trace), accepted / steps, sampler_seconds

    state = initial.copy()
    current = energy(state, bias, coupling)
    for _ in range(steps):
        if kind == "local":
            proposal = state.copy()
            proposal[rng.integers(n)] *= -1
        elif kind == "uniform":
            proposal = rng.choice((-1.0, 1.0), n)
        else:
            started = time.perf_counter()
            proposal, _, _ = quantum.propose(state, rng)
            sampler_seconds += time.perf_counter() - started
        state, current, hit = metropolis(state, current, proposal, bias, coupling, beta, rng)
        accepted += hit
        energy_trace.append(current)
        magnetization_trace.append(float(np.mean(state)))
    return np.asarray(energy_trace), np.asarray(magnetization_trace), accepted / steps, sampler_seconds


def load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = []
        for row in csv.DictReader(handle):
            for key in INT_FIELDS:
                row[key] = int(row[key])
            for key in FLOAT_FIELDS:
                row[key] = float(row[key])
            rows.append(row)
        return rows


def summarize(rows: list[dict], spins: list[int]) -> dict:
    per_spin = {}
    for n in spins:
        entry = {}
        for sampler in ("qemcmc", "local", "uniform", "parallel_tempering"):
            energy_vals = [r["energy_iat_steps"] for r in rows if r["sampler"] == sampler and r["spins"] == n]
            mag_vals = [r["magnetization_iat_steps"] for r in rows if r["sampler"] == sampler and r["spins"] == n]
            if energy_vals:
                entry[sampler] = {
                    "median_energy_iat_steps": float(np.median(energy_vals)),
                    "median_magnetization_iat_steps": float(np.median(mag_vals)),
                }
        per_spin[n] = entry
    return per_spin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spins", nargs="+", type=int, default=[12, 14, 16])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--burn-in", type=int, default=200)
    parser.add_argument("--tag", default="v2", help="output filename tag; never overwrites a prior tagged result")
    args = parser.parse_args()
    reference_path = RESULTS / "qemcmc_exact_level-a-reference_all_verdict.json"
    if not reference_path.exists() or not json.loads(reference_path.read_text())["passed"]:
        raise RuntimeError("published reference validation must pass before G2")

    mixing_path = RESULTS / f"qemcmc_exact_level-a_{args.tag}_all_mixing.csv"
    rows = load_existing(mixing_path)
    mismatched = {(r["proposal_steps"], r["burn_in"]) for r in rows} - {(args.steps, args.burn_in)}
    if mismatched:
        raise RuntimeError(
            f"{mixing_path.name} holds chains at steps/burn-in {sorted(mismatched)} but this run "
            f"uses ({args.steps}, {args.burn_in}); resuming would mix budgets (2026-07-12 v2 "
            "contamination). Use a fresh --tag or match the original flags."
        )
    done = {(r["spins"], r["seed"], r["sampler"]) for r in rows}
    if done:
        print(f"resuming: {len(done)} chains already complete in {mixing_path.name}", flush=True)

    for n in args.spins:
        for seed in args.seeds:
            bias, coupling, beta = planted_instance(n, seed)
            quantum = ExactQuantumProposal(bias, coupling)
            for sampler in ("local", "uniform", "parallel_tempering", "qemcmc"):
                if (n, seed, sampler) in done:
                    continue
                started = time.perf_counter()
                energy_trace, magnetization_trace, acceptance, sampler_seconds = run_chain(
                    sampler, bias, coupling, beta, args.steps, seed + 1000, quantum
                )
                elapsed = time.perf_counter() - started
                tau_energy = censored_autocorrelation_time(energy_trace[args.burn_in:])
                tau_mag = censored_autocorrelation_time(magnetization_trace[args.burn_in:])
                rows.append({
                    "spins": n, "seed": seed, "sampler": sampler,
                    "proposal_steps": args.steps, "burn_in": args.burn_in,
                    "energy_iat_steps": tau_energy, "magnetization_iat_steps": tau_mag,
                    "ess_per_proposal": 1.0 / tau_energy, "magnetization_ess_per_proposal": 1.0 / tau_mag,
                    "acceptance": acceptance, "sampler_seconds": sampler_seconds, "elapsed_seconds": elapsed,
                })
                write_rows(mixing_path, rows, FIELDS)
                print(
                    f"done: sampler={sampler} spins={n} seed={seed} elapsed={elapsed:.1f}s "
                    f"acceptance={acceptance:.3f} energy_iat={tau_energy:.2f} magnetization_iat={tau_mag:.2f}",
                    flush=True,
                )

    per_spin = summarize(rows, args.spins)
    passed = all(
        {"qemcmc", "local", "uniform"} <= per_spin[n].keys()
        and per_spin[n]["qemcmc"]["median_energy_iat_steps"] < per_spin[n]["local"]["median_energy_iat_steps"]
        and per_spin[n]["qemcmc"]["median_energy_iat_steps"] < per_spin[n]["uniform"]["median_energy_iat_steps"]
        and per_spin[n]["qemcmc"]["median_magnetization_iat_steps"] < per_spin[n]["local"]["median_magnetization_iat_steps"]
        and per_spin[n]["qemcmc"]["median_magnetization_iat_steps"] < per_spin[n]["uniform"]["median_magnetization_iat_steps"]
        for n in args.spins
    )
    verdict = {
        "gate": "G2", "passed": bool(passed), "median_iat_by_spins": per_spin,
        "matched_proposal_steps": args.steps, "burn_in": args.burn_in,
        "parallel_tempering_is_reported_not_gate_defining": True,
        "rule": "per spin count, QeMCMC median energy IAT AND median magnetization IAT must both be lower than local's and uniform's",
        "metric_amendment": "2026-07-12 reconciliation: censored IAT (was inf), median aggregation (was mean), magnetization observable added",
    }
    write_json(RESULTS / f"qemcmc_exact_level-a_{args.tag}_all_verdict.json", verdict)
    print(verdict)


if __name__ == "__main__":
    main()
