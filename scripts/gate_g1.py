from __future__ import annotations

import argparse
import time

import numpy as np
from scipy.special import logsumexp, softmax
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.naive_bayes import BernoulliNB
from sklearn.neural_network import MLPClassifier
from sklearn.utils.class_weight import compute_sample_weight

from common import RESULTS, read_codes, seed_all, write_json, write_rows
from exact import all_spins, local_modes


def ece(probability: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    confidence, prediction = probability.max(1), probability.argmax(1)
    total = 0.0
    for low, high in zip(np.linspace(0, 1, bins + 1)[:-1], np.linspace(0, 1, bins + 1)[1:]):
        mask = (confidence > low) & (confidence <= high)
        if mask.any():
            total += mask.mean() * abs((prediction[mask] == labels[mask]).mean() - confidence[mask].mean())
    return float(total)


class SharedIsingEBM:
    """One joint p(z,y), with shared z-z energy and class-conditional fields."""

    def __init__(self, bits: int, classes: int, seed: int):
        rng = seed_all(seed)
        self.b = np.zeros(bits)
        self.j = rng.normal(0, 0.005, (bits, bits))
        self.j = np.triu(self.j, 1); self.j += self.j.T
        self.u = np.zeros((classes, bits))
        self.c = np.zeros(classes)

    def energy(self, s: np.ndarray, y: np.ndarray) -> np.ndarray:
        return -(s @ self.b) - 0.5 * np.einsum("bi,ij,bj->b", s, self.j, s) - np.sum(self.u[y] * s, axis=1) - self.c[y]

    def probabilities(self, s: np.ndarray) -> np.ndarray:
        return softmax(s @ self.u.T + self.c, axis=1)

    def fit(self, s: np.ndarray, y: np.ndarray, epochs: int, chains: int, lr: float, seed: int) -> dict:
        rng = seed_all(seed)
        classes, bits = self.u.shape
        # Stable discriminative initialization; subsequent updates are joint
        # maximum-likelihood PCD estimates, not per-image energies.
        init = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed).fit(s, y)
        self.u[:] = init.coef_ / 2.0
        self.c[:] = init.intercept_
        replicas = 6
        temperatures = np.geomspace(1.0, 4.0, replicas)
        chain_s = rng.choice((-1.0, 1.0), size=(replicas, chains, bits))
        chain_y = rng.integers(classes, size=(replicas, chains))
        positive_b = s.mean(0)
        positive_j = np.einsum("bi,bj->ij", s, s) / len(s)
        positive_u = np.zeros_like(self.u)
        positive_c = np.bincount(y, minlength=classes) / len(y)
        for label in range(classes):
            positive_u[label] = s[y == label].sum(0) / len(s)
        history = []
        for epoch in range(epochs):
            # Persistent local Metropolis sweeps at each temperature.
            for _ in range(2):
                for replica, temperature in enumerate(temperatures):
                    for bit in rng.permutation(bits):
                        proposal = chain_s[replica].copy(); proposal[:, bit] *= -1
                        delta = self.energy(proposal, chain_y[replica]) - self.energy(chain_s[replica], chain_y[replica])
                        accept = rng.random(chains) < np.exp(np.minimum(0.0, -delta / temperature))
                        chain_s[replica, accept] = proposal[accept]
                    proposal_y = rng.integers(classes, size=chains)
                    delta = self.energy(chain_s[replica], proposal_y) - self.energy(chain_s[replica], chain_y[replica])
                    accept = rng.random(chains) < np.exp(np.minimum(0.0, -delta / temperature))
                    chain_y[replica, accept] = proposal_y[accept]
                # Adjacent parallel-tempering swaps; proposal count is logged.
                for replica in range(replicas - 1):
                    e0 = self.energy(chain_s[replica], chain_y[replica])
                    e1 = self.energy(chain_s[replica + 1], chain_y[replica + 1])
                    log_accept = (1 / temperatures[replica] - 1 / temperatures[replica + 1]) * (e0 - e1)
                    accept = np.log(rng.random(chains)) < np.minimum(0.0, log_accept)
                    tmp_s = chain_s[replica, accept].copy(); tmp_y = chain_y[replica, accept].copy()
                    chain_s[replica, accept] = chain_s[replica + 1, accept]
                    chain_y[replica, accept] = chain_y[replica + 1, accept]
                    chain_s[replica + 1, accept] = tmp_s; chain_y[replica + 1, accept] = tmp_y
            ns, ny = chain_s[0], chain_y[0]
            negative_b = ns.mean(0)
            negative_j = np.einsum("bi,bj->ij", ns, ns) / len(ns)
            negative_u = np.zeros_like(self.u)
            negative_c = np.bincount(ny, minlength=classes) / len(ny)
            for label in range(classes):
                negative_u[label] = ns[ny == label].sum(0) / len(ns)
            rate = lr / np.sqrt(1 + epoch / 20)
            self.b += rate * (positive_b - negative_b)
            self.j += rate * (positive_j - negative_j)
            self.j = np.triu(self.j, 1); self.j += self.j.T
            self.u += rate * (positive_u - negative_u)
            self.c += rate * (positive_c - negative_c)
            history.append({"epoch": epoch + 1, "learning_rate": rate, "cold_mean_energy": float(self.energy(ns, ny).mean())})
        return {"history": history, "replicas": replicas, "temperatures": temperatures.tolist(), "local_steps_per_epoch": 2 * replicas * (bits + 1) * chains, "swap_attempts_per_epoch": 2 * (replicas - 1) * chains}


def evaluate(name: str, probability: np.ndarray, labels: np.ndarray, seed: int) -> dict:
    prediction = probability.argmax(1)
    return {"seed": seed, "model": name, "sampler": "pcd_pt" if name == "ising_ebm" else "none", "level": "level-c",
            "macro_f1": float(f1_score(labels, prediction, average="macro")), "accuracy": float(accuracy_score(labels, prediction)),
            "nll": float(log_loss(labels, probability, labels=np.arange(probability.shape[1]))), "ece": ece(probability, labels)}


def ruggedness(model: SharedIsingEBM) -> dict:
    states = all_spins(len(model.b))
    base = -(states @ model.b) - 0.5 * np.einsum("bi,ij,bj->b", states, model.j, states)
    marginal_energy = base - logsumexp(states @ model.u.T + model.c, axis=1)
    modes = local_modes(marginal_energy, len(model.b))
    barriers = []
    for mode in modes:
        neighbors = [mode ^ (1 << bit) for bit in range(len(model.b))]
        barriers.append(float(min(marginal_energy[neighbors]) - marginal_energy[mode]))
    shifted = np.exp(-(marginal_energy - marginal_energy.min())); probability = shifted / shifted.sum()
    return {"mode_count": int(len(modes)), "top_mode_mass": float(probability[modes].max()),
            "median_single_flip_exit_barrier": float(np.median(barriers)), "max_single_flip_exit_barrier": float(np.max(barriers))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--chains", type=int, default=256)
    args = parser.parse_args()
    rows, rugged_rows = [], []
    for seed in args.seeds:
        x, y, partition = read_codes(seed); s = 2.0 * x - 1.0
        train, val = partition == "train", partition == "val"
        models = {
            "logistic": LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed),
            "small_mlp": MLPClassifier(hidden_layer_sizes=(32,), max_iter=1000, early_stopping=True, random_state=seed),
            "naive_bayes": BernoulliNB(),
        }
        for name, model in models.items():
            if name == "small_mlp":
                weights = compute_sample_weight("balanced", y[train])
                model.fit(x[train], y[train], sample_weight=weights)
            else:
                model.fit(x[train], y[train])
            rows.append(evaluate(name, model.predict_proba(x[val]), y[val], seed))
        ebm = SharedIsingEBM(s.shape[1], len(np.unique(y)), seed)
        started = time.perf_counter(); metadata = ebm.fit(s[train], y[train], args.epochs, args.chains, 0.015, seed)
        rows.append(evaluate("ising_ebm", ebm.probabilities(s[val]), y[val], seed))
        rugged = {"seed": seed, **ruggedness(ebm)}; rugged_rows.append(rugged)
        write_rows(RESULTS / f"ising-ebm_pcd-pt_level-c_{seed}_reconciled-history.csv", metadata.pop("history"))
        write_json(RESULTS / f"ising-ebm_pcd-pt_level-c_{seed}_reconciled-metadata.json", {**metadata, **rugged, "train_seconds": time.perf_counter() - started, "shared_energy_model": True})
    write_rows(RESULTS / "ising-ebm_pcd-pt_level-c_all_reconciled-baselines.csv", rows)
    write_rows(RESULTS / "ising-ebm_pcd-pt_level-c_all_reconciled-ruggedness.csv", rugged_rows)
    ebm_f1 = np.mean([r["macro_f1"] for r in rows if r["model"] == "ising_ebm"])
    best_simple = max(np.mean([r["macro_f1"] for r in rows if r["model"] == name]) for name in ("logistic", "small_mlp", "naive_bayes"))
    seeds_with_five_modes = sum(r["mode_count"] >= 5 for r in rugged_rows)
    passed = (best_simple - ebm_f1 <= 0.10) and seeds_with_five_modes >= 2
    verdict = {"gate": "G1", "passed": bool(passed), "mean_ebm_macro_f1": ebm_f1, "mean_best_simple_macro_f1": best_simple,
               "macro_f1_gap_threshold": 0.10, "seeds_with_at_least_five_modes": seeds_with_five_modes,
               "required_seeds_with_at_least_five_modes": 2,
               "rule": "pass iff shared EBM mean validation Macro-F1 is within 0.10 of best simple mean and >=5 modes occur on >=2/3 seeds",
               "threshold_provenance": "2026-07-12 reconciliation after Stage-0 diagnostics; operational only"}
    write_json(RESULTS / "ising-ebm_pcd-pt_level-c-all_reconciled-verdict.json", verdict)
    print(verdict)


if __name__ == "__main__":
    main()
