from __future__ import annotations

import unittest

import numpy as np

from adaptive_controller import ARM_NAMES, AdaptiveController
from stage1_train import sampler_configuration


class AdaptiveControllerTests(unittest.TestCase):
    def test_first_five_rounds_force_each_registered_arm_once(self):
        controller = AdaptiveController()

        selected = []
        for reward in (-5.0, -4.0, -3.0, -2.0, -1.0):
            arm = controller.select_arm()
            selected.append(arm.name)
            controller.observe(arm.index, reward)

        self.assertEqual(selected, list(ARM_NAMES))

    def test_reward_standardization_uses_running_mean_and_population_std(self):
        controller = AdaptiveController()

        first = controller.observe(0, 10.0)
        second = controller.observe(1, 14.0)

        self.assertEqual(first, 0.0)
        self.assertEqual(second, 1.0)

    def test_previous_arm_counts_are_discounted_by_point_nine(self):
        controller = AdaptiveController()

        controller.observe(0, 10.0)
        controller.observe(1, 14.0)

        np.testing.assert_allclose(controller.discounted_counts, [0.9, 1.0, 0.0, 0.0, 0.0])

    def test_state_round_trip_preserves_the_next_decision(self):
        controller = AdaptiveController()
        for reward in (-5.0, -4.0, -3.0, -2.0, -1.0):
            arm = controller.select_arm()
            controller.observe(arm.index, reward)

        restored = AdaptiveController.from_state(controller.to_state())

        self.assertEqual(restored.select_arm(), controller.select_arm())
        np.testing.assert_allclose(restored.value_estimates, controller.value_estimates)


class ControllerConcentrationTests(unittest.TestCase):
    """Amended G5 mechanism check (2026-07-14): under a planted 1-sigma arm
    separation the controller must concentrate on the planted arm, with and
    without the reward drift observed in live runs."""

    def _pulls(self, planted: int, drift: float, seed: int, rounds: int = 100) -> np.ndarray:
        rng = np.random.default_rng(seed)
        controller = AdaptiveController()
        pulls = np.zeros(len(ARM_NAMES))
        for round_index in range(rounds):
            arm = controller.select_arm()
            pulls[arm.index] += 1
            reward = -17.0 - drift * round_index / rounds * 6.0 + rng.normal(0.0, 3.5)
            if arm.index == planted:
                reward += 3.5
            controller.observe(arm.index, reward)
        return pulls

    def test_concentrates_on_planted_arm_in_stationary_environment(self):
        pulls = sum(self._pulls(planted=3, drift=0.0, seed=seed) for seed in range(10))
        self.assertEqual(int(np.argmax(pulls)), 3)
        self.assertGreater(pulls[3], 2.0 * np.delete(pulls, 3).mean())

    def test_concentrates_on_planted_arm_under_reward_drift(self):
        pulls = sum(self._pulls(planted=3, drift=1.0, seed=seed) for seed in range(10))
        self.assertEqual(int(np.argmax(pulls)), 3)
        self.assertGreater(pulls[3], 2.0 * np.delete(pulls, 3).mean())


class Stage2SamplerConfigurationTests(unittest.TestCase):
    def test_registered_stage2_variants_fix_reward_and_persistence(self):
        expected = {
            "adaptive-qemcmc": ("exact", False, True),
            "adaptive-qemcmc-p": ("exact", True, True),
            "qemcmc-p": ("none", True, False),
            "adaptive-qemcmc-proxy": ("proxy", False, True),
            "adaptive-qemcmc-p-proxy": ("proxy", True, True),
        }

        for sampler, (reward, persistent, adaptive) in expected.items():
            with self.subTest(sampler=sampler):
                configuration = sampler_configuration(sampler)
                self.assertEqual(configuration.reward_signal, reward)
                self.assertEqual(configuration.persistence, persistent)
                self.assertEqual(configuration.adaptive, adaptive)


if __name__ == "__main__":
    unittest.main()
