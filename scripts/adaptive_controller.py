"""Frozen Stage-2 discounted-UCB controller for adaptive QeMCMC."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


CONTROLLER_VERSION = "stage2-v1-gpu"
DISCOUNT = 0.9
EXPLORATION = 1.0

ARM_NAMES = (
    "qemcmc-t-low-gamma-low",
    "qemcmc-t-low-gamma-high",
    "qemcmc-t-high-gamma-low",
    "qemcmc-t-high-gamma-high",
    "classical-local",
)
ARM_VALUE_COLUMNS = tuple(
    "controller_value_arm_{}_{}".format(index, name.replace("-", "_"))
    for index, name in enumerate(ARM_NAMES)
)


@dataclass(frozen=True)
class ControllerArm:
    index: int
    name: str
    time_range: tuple[float, float] | None
    gamma_range: tuple[float, float] | None

    @property
    def classical(self) -> bool:
        return self.time_range is None

    def draw_parameters(self, rng: np.random.Generator) -> tuple[float, float]:
        if self.classical:
            raise RuntimeError("the classical arm has no quantum parameters")
        # upper - U[0, width) realizes the preregistered (lower, upper] cells.
        evolution_time = self.time_range[1] - rng.uniform(
            0.0, self.time_range[1] - self.time_range[0]
        )
        gamma = self.gamma_range[1] - rng.uniform(
            0.0, self.gamma_range[1] - self.gamma_range[0]
        )
        return float(evolution_time), float(gamma)


ARMS = (
    ControllerArm(0, ARM_NAMES[0], (2.0, 11.0), (0.25, 0.425)),
    ControllerArm(1, ARM_NAMES[1], (2.0, 11.0), (0.425, 0.6)),
    ControllerArm(2, ARM_NAMES[2], (11.0, 20.0), (0.25, 0.425)),
    ControllerArm(3, ARM_NAMES[3], (11.0, 20.0), (0.425, 0.6)),
    ControllerArm(4, ARM_NAMES[4], None, None),
)


class AdaptiveController:
    """Discounted UCB with frozen Stage-2 hyperparameters and online z-scores."""

    def __init__(self) -> None:
        self.rounds = 0
        self.discounted_counts = np.zeros(len(ARMS), dtype=float)
        self.discounted_rewards = np.zeros(len(ARMS), dtype=float)
        self.reward_count = 0
        self.reward_mean = 0.0
        self.reward_m2 = 0.0

    @property
    def value_estimates(self) -> np.ndarray:
        return np.divide(
            self.discounted_rewards,
            self.discounted_counts,
            out=np.zeros_like(self.discounted_rewards),
            where=self.discounted_counts > 0,
        )

    def select_arm(self) -> ControllerArm:
        if self.rounds < len(ARMS):
            return ARMS[self.rounds]
        total = float(self.discounted_counts.sum())
        bonus = EXPLORATION * np.sqrt(
            np.log(max(total, 1.0)) / np.maximum(self.discounted_counts, 1e-15)
        )
        return ARMS[int(np.argmax(self.value_estimates + bonus))]

    def observe(self, arm_index: int, raw_reward: float) -> float:
        if not 0 <= arm_index < len(ARMS):
            raise ValueError(f"unknown controller arm index: {arm_index}")
        if not np.isfinite(raw_reward):
            raise ValueError("controller reward must be finite")

        self.reward_count += 1
        delta = raw_reward - self.reward_mean
        self.reward_mean += delta / self.reward_count
        self.reward_m2 += delta * (raw_reward - self.reward_mean)
        reward_std = np.sqrt(self.reward_m2 / self.reward_count)
        standardized = 0.0 if reward_std == 0.0 else (raw_reward - self.reward_mean) / reward_std

        self.discounted_counts *= DISCOUNT
        self.discounted_rewards *= DISCOUNT
        self.discounted_counts[arm_index] += 1.0
        self.discounted_rewards[arm_index] += standardized
        self.rounds += 1
        return float(standardized)

    def to_state(self) -> dict:
        return {
            "version": CONTROLLER_VERSION,
            "rounds": self.rounds,
            "discounted_counts": self.discounted_counts.tolist(),
            "discounted_rewards": self.discounted_rewards.tolist(),
            "reward_count": self.reward_count,
            "reward_mean": self.reward_mean,
            "reward_m2": self.reward_m2,
        }

    @classmethod
    def from_state(cls, state: dict) -> "AdaptiveController":
        if state.get("version") != CONTROLLER_VERSION:
            raise RuntimeError(
                f"controller state version mismatch: {state.get('version')} != {CONTROLLER_VERSION}"
            )
        controller = cls()
        controller.rounds = int(state["rounds"])
        controller.discounted_counts = np.asarray(state["discounted_counts"], dtype=float)
        controller.discounted_rewards = np.asarray(state["discounted_rewards"], dtype=float)
        if (
            controller.discounted_counts.shape != (len(ARMS),)
            or controller.discounted_rewards.shape != (len(ARMS),)
        ):
            raise RuntimeError("controller state has the wrong arm count")
        controller.reward_count = int(state["reward_count"])
        controller.reward_mean = float(state["reward_mean"])
        controller.reward_m2 = float(state["reward_m2"])
        return controller
