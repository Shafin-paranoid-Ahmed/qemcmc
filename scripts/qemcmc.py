from __future__ import annotations

import time

import numpy as np
from scipy.sparse import csr_matrix, diags
from scipy.sparse.linalg import expm_multiply


GAMMA_RANGE = (0.25, 0.6)
TIME_RANGE = (2.0, 20.0)


def planted_instance(n: int, seed: int) -> tuple[np.ndarray, np.ndarray, float]:
    rng = np.random.default_rng(seed)
    planted = rng.choice((-1.0, 1.0), n)
    coupling = np.zeros((n, n))
    for i in range(n):
        for offset in (1, 2, 5):
            j = (i + offset) % n
            sign = planted[i] * planted[j]
            if rng.random() < 0.22:
                sign *= -1
            coupling[i, j] += sign
            coupling[j, i] += sign
    return 0.12 * planted, 0.55 * coupling, 2.2


def layden_reference_instance() -> tuple[np.ndarray, np.ndarray, float]:
    """Nature 619 (2023) Supplement Eq. S26, evaluated at Fig. 4 T=0.1."""
    nearest = np.array([
        -0.99121054, 0.84436089, -0.83043895, 0.95766024, -1.02814718,
        1.24969204, 0.81649925, -0.92147578, 1.11394418,
    ])
    bias = np.array([
        0.47921821, 0.10207621, -0.4780673, -0.39407213, 0.15239487,
        0.44938277, 0.91715616, 0.73303354, 0.40145444, 0.55915183,
    ])
    coupling = np.zeros((10, 10))
    for i, value in enumerate(nearest):
        coupling[i, i + 1] = coupling[i + 1, i] = value
    return bias, coupling, 10.0


def energy(state: np.ndarray, bias: np.ndarray, coupling: np.ndarray) -> float:
    return float(-state @ bias - 0.5 * state @ coupling @ state)


def index_to_spins(index: int, n: int) -> np.ndarray:
    bits = (index >> np.arange(n, dtype=np.uint64)) & 1
    return 1.0 - 2.0 * bits.astype(float)


def spins_to_index(state: np.ndarray) -> int:
    bits = (np.asarray(state) < 0).astype(np.uint64)
    return int(np.sum(bits << np.arange(len(bits), dtype=np.uint64)))


def all_energies(bias: np.ndarray, coupling: np.ndarray) -> np.ndarray:
    n = len(bias)
    values = np.arange(1 << n, dtype=np.uint32)[:, None]
    bits = (values >> np.arange(n, dtype=np.uint32)) & 1
    states = 1.0 - 2.0 * bits.astype(np.float64)
    return -(states @ bias) - 0.5 * np.einsum("bi,ij,bj->b", states, coupling, states)


def mixer_matrix(n: int) -> csr_matrix:
    size = 1 << n
    columns = np.arange(size, dtype=np.int64)
    rows = np.concatenate([columns ^ (1 << bit) for bit in range(n)])
    columns = np.tile(columns, n)
    return csr_matrix((np.ones(len(rows)), (rows, columns)), shape=(size, size))


class ExactQuantumProposal:
    """Exact Layden Eq. (5) time evolution, with no product-formula error."""

    def __init__(self, bias: np.ndarray, coupling: np.ndarray):
        self.bias = np.asarray(bias, dtype=float)
        self.coupling = np.asarray(coupling, dtype=float)
        self.n = len(self.bias)
        if not 1 <= self.n <= 20:
            raise ValueError("exact SciPy reference is restricted to 1..20 spins")
        self.problem_energy = all_energies(self.bias, self.coupling)
        denominator = np.sqrt(
            np.sum(np.triu(self.coupling, 1) ** 2) + np.sum(self.bias ** 2)
        )
        self.alpha = np.sqrt(self.n) / denominator
        self.mixer = mixer_matrix(self.n)

    def hamiltonian(self, gamma: float) -> csr_matrix:
        return (1.0 - gamma) * self.alpha * diags(self.problem_energy) + gamma * self.mixer

    def distribution(self, state: np.ndarray, evolution_time: float, gamma: float) -> np.ndarray:
        initial = np.zeros(1 << self.n, dtype=np.complex128)
        initial[spins_to_index(state)] = 1.0
        evolved = expm_multiply((-1j * evolution_time) * self.hamiltonian(gamma), initial)
        probability = np.abs(evolved) ** 2
        return probability / probability.sum()

    def propose(self, state: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, float, float]:
        # Layden et al., Supplement Algorithm S1 lines 4-5 and Eq. (S2):
        # gamma ~ Uniform(0.25, 0.6), t ~ Uniform(2, 20).
        gamma = rng.uniform(*GAMMA_RANGE)
        evolution_time = rng.uniform(*TIME_RANGE)
        probability = self.distribution(state, evolution_time, gamma)
        index = int(rng.choice(len(probability), p=probability))
        return index_to_spins(index, self.n), evolution_time, gamma


def benchmark(proposal: ExactQuantumProposal, repeats: int = 3) -> dict:
    state = np.ones(proposal.n)
    times = []
    for _ in range(repeats):
        started = time.perf_counter()
        proposal.distribution(state, 5.0, 0.42)
        times.append(time.perf_counter() - started)
    return {
        "exact_expm_multiply_seconds_per_proposal": float(np.median(times)),
        "ordered_trotter_used": False,
        "method": "scipy.sparse.linalg.expm_multiply",
    }
