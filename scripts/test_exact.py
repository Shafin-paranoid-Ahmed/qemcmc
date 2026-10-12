import itertools
import unittest

import numpy as np

from exact import all_spins, boltzmann, energies, exact_log_likelihood, exact_negative_phase


class ExactFourBitTest(unittest.TestCase):
    def test_matches_hand_loop(self):
        bias = np.array([0.2, -0.1, 0.35, 0.05])
        coupling = np.zeros((4, 4))
        coupling[0, 1] = coupling[1, 0] = 0.4
        coupling[2, 3] = coupling[3, 2] = -0.25
        states = all_spins(4)
        energy = energies(states, bias, coupling)
        hand = []
        for state in itertools.product((-1.0, 1.0), repeat=4):
            state = np.array(state)
            hand.append(-state @ bias - sum(coupling[i, j] * state[i] * state[j] for i in range(4) for j in range(i + 1, 4)))
        # all_spins uses little-endian enumeration; compare the unordered table.
        np.testing.assert_allclose(np.sort(energy), np.sort(hand), atol=1e-12)
        probability, log_partition = boltzmann(energy)
        mean, pair = exact_negative_phase(bias, coupling)
        np.testing.assert_allclose(mean, probability @ states, atol=1e-12)
        np.testing.assert_allclose(pair[0, 1], np.sum(probability * states[:, 0] * states[:, 1]), atol=1e-12)
        self.assertAlmostEqual(probability.sum(), 1.0)
        self.assertAlmostEqual(log_partition, np.log(np.exp(-energy).sum()))
        self.assertTrue(np.isfinite(exact_log_likelihood(states[:3], bias, coupling)))


if __name__ == "__main__":
    unittest.main()
