"""Complex128 GPU implementation of the QeMCMC proposal distribution.

CuPy 14.1 does not expose ``cupyx.scipy.sparse.linalg.expm_multiply``.  This
module therefore applies ``exp(-i H t)`` with a Chebyshev expansion specialized
to Hermitian H.  Gershgorin bounds map H's spectrum into [-1, 1].  Expansion
order is selected from the absolute Bessel-coefficient tail; the calculation
fails closed unless the computed tail is below ``coefficient_tolerance``.

The Hamiltonian and normalization match scripts/qemcmc.py exactly.  All state
vectors, coefficients, and probabilities use double precision.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import cupy as cp
import numpy as np
from scipy.special import jv

PILOT = Path(__file__).resolve().parents[2]
if str(PILOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PILOT / "scripts"))

from qemcmc import (  # noqa: E402
    GAMMA_RANGE,
    TIME_RANGE,
    index_to_spins,
    spins_to_index,
)


_MATVEC = cp.RawKernel(
    r"""
    #include <cuComplex.h>
    extern "C" __global__
    void scaled_h_matvec(
        const cuDoubleComplex* x,
        const double* diagonal,
        cuDoubleComplex* out,
        const long long size,
        const int n_spins,
        const double mixer_weight,
        const double center,
        const double radius)
    {
        long long i = (long long)blockDim.x * blockIdx.x + threadIdx.x;
        if (i >= size) return;
        cuDoubleComplex acc = make_cuDoubleComplex(0.0, 0.0);
        for (int bit = 0; bit < n_spins; ++bit) {
            acc = cuCadd(acc, x[i ^ (1LL << bit)]);
        }
        cuDoubleComplex diagonal_part =
            cuCmul(make_cuDoubleComplex(diagonal[i] - center, 0.0), x[i]);
        cuDoubleComplex mixer_part =
            cuCmul(make_cuDoubleComplex(mixer_weight, 0.0), acc);
        out[i] = cuCdiv(cuCadd(diagonal_part, mixer_part),
                        make_cuDoubleComplex(radius, 0.0));
    }
    """,
    "scaled_h_matvec",
)


def _alpha(couplings: np.ndarray, fields: np.ndarray) -> float:
    n = int(fields.size)
    norm_sq = float(np.sum(np.triu(couplings, 1) ** 2) + np.sum(fields**2))
    return float(np.sqrt(n) / np.sqrt(norm_sq)) if norm_sq > 0 else 1.0


def problem_energies(couplings: np.ndarray, fields: np.ndarray) -> np.ndarray:
    """Return all Ising energies without materializing an N-by-n spin matrix."""
    couplings = np.asarray(couplings, dtype=np.float64)
    fields = np.asarray(fields, dtype=np.float64)
    n = int(fields.size)
    size = 1 << n
    indices = np.arange(size, dtype=np.uint64)
    energy = np.zeros(size, dtype=np.float64)
    spins = []
    for bit in range(n):
        spin = 1.0 - 2.0 * ((indices >> bit) & 1).astype(np.float64)
        spins.append(spin)
        energy -= fields[bit] * spin
    for i in range(n):
        for j in range(i + 1, n):
            if couplings[i, j] != 0.0:
                energy -= couplings[i, j] * spins[i] * spins[j]
    return energy


def _chebyshev_coefficients(argument: float, tolerance: float) -> np.ndarray:
    """Return coefficients only after a conservative computed-tail check."""
    argument = abs(float(argument))
    max_order = max(128, int(np.ceil(argument + 24.0 * np.sqrt(argument + 1.0) + 128.0)))
    orders = np.arange(max_order + 1)
    magnitudes = 2.0 * np.abs(jv(orders, argument))
    magnitudes[0] *= 0.5

    # The over-resolved final 32 coefficients must already be negligible.  The
    # cumulative tail within the computed range then chooses the smallest safe
    # order.  This is deliberately stricter than the TV acceptance threshold.
    guard = float(np.sum(magnitudes[-32:]))
    if not np.isfinite(guard) or guard > tolerance * 1e-3:
        raise RuntimeError(
            f"Chebyshev tail was not resolved: guard={guard:.3e}, "
            f"tolerance={tolerance:.3e}, max_order={max_order}"
        )
    tail = np.cumsum(magnitudes[::-1])[::-1]
    candidates = np.flatnonzero(tail <= tolerance)
    if candidates.size == 0:
        raise RuntimeError("No Chebyshev order satisfies the convergence criterion")
    order = max(1, int(candidates[0] - 1))
    k = np.arange(order + 1)
    coefficients = 2.0 * ((-1j) ** k) * jv(k, float(argument))
    coefficients[0] *= 0.5
    return coefficients.astype(np.complex128, copy=False)


@dataclass
class GPUExactQuantumProposal:
    """GPU proposal matching ``qemcmc.ExactQuantumProposal.distribution``."""

    couplings: np.ndarray
    fields: np.ndarray
    coefficient_tolerance: float = 1e-12

    def __post_init__(self) -> None:
        self.couplings = np.asarray(self.couplings, dtype=np.float64)
        self.fields = np.asarray(self.fields, dtype=np.float64)
        self.n_spins = int(self.fields.size)
        if self.couplings.shape != (self.n_spins, self.n_spins):
            raise ValueError("couplings must have shape (n_spins, n_spins)")
        if self.n_spins > 24:
            raise ValueError("GPU proposal is intentionally limited to <=24 spins")
        self.size = 1 << self.n_spins
        self.alpha = _alpha(self.couplings, self.fields)
        self.problem_energy_cpu = problem_energies(self.couplings, self.fields)
        self.problem_energy = cp.asarray(self.problem_energy_cpu, dtype=cp.float64)

    def rebuild_problem_diagonal(
        self, couplings: np.ndarray, fields: np.ndarray
    ) -> None:
        """Replace theta-dependent problem energies once per training update."""
        couplings = np.asarray(couplings, dtype=np.float64)
        fields = np.asarray(fields, dtype=np.float64)
        if couplings.shape != self.couplings.shape or fields.shape != self.fields.shape:
            raise ValueError("rebuild cannot change the number of spins")
        self.couplings = couplings
        self.fields = fields
        self.alpha = _alpha(couplings, fields)
        self.problem_energy_cpu = problem_energies(couplings, fields)
        self.problem_energy = cp.asarray(self.problem_energy_cpu, dtype=cp.float64)

    def _scaled_matvec(
        self,
        vector: cp.ndarray,
        diagonal: cp.ndarray,
        gamma: float,
        center: float,
        radius: float,
    ) -> cp.ndarray:
        out = cp.empty_like(vector)
        threads = 256
        blocks = (self.size + threads - 1) // threads
        _MATVEC(
            (blocks,),
            (threads,),
            (
                vector,
                diagonal,
                out,
                np.int64(self.size),
                np.int32(self.n_spins),
                np.float64(gamma),
                np.float64(center),
                np.float64(radius),
            ),
        )
        return out

    def distribution(self, state_index: int, evolution_time: float, gamma: float) -> np.ndarray:
        if not 0 <= state_index < self.size:
            raise ValueError("state_index is outside the Hilbert space")
        if not TIME_RANGE[0] <= evolution_time <= TIME_RANGE[1]:
            raise ValueError(f"evolution_time must lie in {TIME_RANGE}")
        if not GAMMA_RANGE[0] <= gamma <= GAMMA_RANGE[1]:
            raise ValueError(f"gamma must lie in {GAMMA_RANGE}")

        diagonal_cpu = (1.0 - gamma) * self.alpha * self.problem_energy_cpu
        diagonal = (1.0 - gamma) * self.alpha * self.problem_energy
        lower = float(np.min(diagonal_cpu) - gamma * self.n_spins)
        upper = float(np.max(diagonal_cpu) + gamma * self.n_spins)
        center = 0.5 * (lower + upper)
        radius = 0.5 * (upper - lower)
        if radius == 0.0:
            result = np.zeros(self.size, dtype=np.float64)
            result[state_index] = 1.0
            return result

        coefficients = _chebyshev_coefficients(
            evolution_time * radius, self.coefficient_tolerance
        )
        coefficients_gpu = cp.asarray(coefficients, dtype=cp.complex128)
        vector0 = cp.zeros(self.size, dtype=cp.complex128)
        vector0[state_index] = 1.0
        result = coefficients_gpu[0] * vector0
        if coefficients.size > 1:
            vector1 = self._scaled_matvec(vector0, diagonal, gamma, center, radius)
            result += coefficients_gpu[1] * vector1
            for order in range(2, coefficients.size):
                vector2 = 2.0 * self._scaled_matvec(
                    vector1, diagonal, gamma, center, radius
                ) - vector0
                result += coefficients_gpu[order] * vector2
                vector0, vector1 = vector1, vector2
        result *= cp.exp(cp.asarray(-1j * evolution_time * center, dtype=cp.complex128))
        probabilities = cp.abs(result) ** 2
        probabilities /= cp.sum(probabilities)
        cp.cuda.get_current_stream().synchronize()
        return cp.asnumpy(probabilities)

    def propose(
        self, state: np.ndarray, rng: np.random.Generator
    ) -> tuple[np.ndarray, float, float]:
        """Use the registered Layden parameter draws and return a measured state."""
        gamma = rng.uniform(*GAMMA_RANGE)
        evolution_time = rng.uniform(*TIME_RANGE)
        probability = self.distribution(
            spins_to_index(state), evolution_time, gamma
        )
        index = int(rng.choice(len(probability), p=probability))
        return index_to_spins(index, self.n_spins), evolution_time, gamma


def synchronize() -> None:
    cp.cuda.get_current_stream().synchronize()
