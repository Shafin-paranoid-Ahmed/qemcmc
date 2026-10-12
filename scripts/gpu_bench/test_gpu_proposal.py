"""Unit-level correctness checks for the isolated GPU proposal."""

from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("CUPY_CACHE_DIR", str(ROOT / ".cache" / "cupy"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from scipy.linalg import expm  # noqa: E402

from gpu_proposal import GPUExactQuantumProposal  # noqa: E402
from qemcmc import mixer_matrix  # noqa: E402


def main() -> None:
    rng = np.random.default_rng(17)
    n = 4
    couplings = rng.normal(0.0, 0.3, size=(n, n))
    couplings = np.triu(couplings, 1)
    couplings += couplings.T
    fields = rng.normal(0.0, 0.2, size=n)
    proposal = GPUExactQuantumProposal(couplings, fields)
    t, gamma, state = 7.25, 0.41, 5
    diagonal = (1.0 - gamma) * proposal.alpha * proposal.problem_energy_cpu
    hamiltonian = np.diag(diagonal) + gamma * mixer_matrix(n).toarray()
    basis = np.zeros(1 << n, dtype=np.complex128)
    basis[state] = 1.0
    reference = np.abs(expm(-1j * hamiltonian * t) @ basis) ** 2
    actual = proposal.distribution(state, t, gamma)
    tv = 0.5 * float(np.sum(np.abs(reference - actual)))
    assert tv <= 1e-10, f"dense four-spin TV mismatch: {tv:.3e}"
    assert abs(float(actual.sum()) - 1.0) <= 1e-12
    print(f"PASS dense 4-spin comparison: TV={tv:.3e}")


if __name__ == "__main__":
    main()
