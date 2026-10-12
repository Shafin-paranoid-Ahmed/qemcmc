from __future__ import annotations

import numpy as np


def all_spins(n_bits: int) -> np.ndarray:
    if not 1 <= n_bits <= 24:
        raise ValueError("exact enumeration is restricted to 1..24 bits")
    values = np.arange(1 << n_bits, dtype=np.uint32)[:, None]
    bits = ((values >> np.arange(n_bits, dtype=np.uint32)) & 1).astype(np.int8)
    return 2.0 * bits - 1.0


def energies(spins: np.ndarray, bias: np.ndarray, coupling: np.ndarray) -> np.ndarray:
    return -(spins @ bias) - 0.5 * np.einsum("bi,ij,bj->b", spins, coupling, spins)


def boltzmann(energy: np.ndarray, beta: float = 1.0) -> tuple[np.ndarray, float]:
    logits = -beta * np.asarray(energy, dtype=np.float64)
    peak = logits.max()
    weights = np.exp(logits - peak)
    log_partition = float(peak + np.log(weights.sum()))
    return weights / weights.sum(), log_partition


def exact_log_likelihood(data: np.ndarray, bias: np.ndarray, coupling: np.ndarray) -> float:
    states = all_spins(data.shape[1])
    _, log_partition = boltzmann(energies(states, bias, coupling))
    return float(np.mean(-energies(data, bias, coupling) - log_partition))


def exact_negative_phase(bias: np.ndarray, coupling: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    states = all_spins(len(bias))
    probability, _ = boltzmann(energies(states, bias, coupling))
    mean = probability @ states
    pair = np.einsum("b,bi,bj->ij", probability, states, states)
    np.fill_diagonal(pair, 0.0)
    return mean, pair


def local_modes(energy: np.ndarray, n_bits: int) -> np.ndarray:
    indices = np.arange(1 << n_bits)
    mask = np.ones(len(indices), dtype=bool)
    for bit in range(n_bits):
        mask &= energy <= energy[indices ^ (1 << bit)]
    return np.flatnonzero(mask)
