from __future__ import annotations

import argparse

from common import RESULTS, write_json, write_rows
from gate_g2 import autocorrelation_time, run_chain
from qemcmc import ExactQuantumProposal, layden_reference_instance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=2000)
    parser.add_argument("--burn-in", type=int, default=200)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    args = parser.parse_args()
    bias, coupling, beta = layden_reference_instance()
    quantum = ExactQuantumProposal(bias, coupling)
    rows = []
    for seed in args.seeds:
        for sampler in ("local", "uniform", "qemcmc"):
            trace, acceptance, seconds = run_chain(
                sampler, bias, coupling, beta, args.steps, 7000 + seed, quantum
            )
            tau = autocorrelation_time(trace[args.burn_in:])
            rows.append({
                "reference": "Layden Supplement Eq. S26 at Fig. 4 T=0.1",
                "seed": seed, "sampler": sampler, "proposal_steps": args.steps,
                "burn_in": args.burn_in, "energy_iat_steps": tau,
                "ess_per_proposal": 1.0 / tau, "acceptance": acceptance,
                "sampler_seconds": seconds,
            })
    write_rows(RESULTS / "qemcmc_exact_level-a-reference_all_mixing.csv", rows)
    means = {
        sampler: sum(r["energy_iat_steps"] for r in rows if r["sampler"] == sampler) / len(args.seeds)
        for sampler in ("local", "uniform", "qemcmc")
    }
    passed = means["qemcmc"] < min(means["local"], means["uniform"])
    verdict = {
        "passed": bool(passed), "reference": "Layden Supplement Eq. S26",
        "temperature": 0.1, "mean_energy_iat_steps": means,
        "rule": "qualitative published-instance reproduction: QeMCMC IAT below local and uniform",
    }
    write_json(RESULTS / "qemcmc_exact_level-a-reference_all_verdict.json", verdict)
    print(verdict)


if __name__ == "__main__":
    main()
