import unittest

import numpy as np

from qemcmc import ExactQuantumProposal, index_to_spins, planted_instance


class ExactProposalSymmetryTest(unittest.TestCase):
    def test_six_spin_proposal_is_symmetric(self):
        bias, coupling, _ = planted_instance(6, 7)
        proposal = ExactQuantumProposal(bias, coupling)
        matrix = np.column_stack([
            proposal.distribution(index_to_spins(index, 6), 7.25, 0.41)
            for index in range(1 << 6)
        ])
        np.testing.assert_allclose(matrix, matrix.T, atol=2e-12, rtol=2e-12)
        np.testing.assert_allclose(matrix.sum(axis=0), 1.0, atol=2e-12)


if __name__ == "__main__":
    unittest.main()
