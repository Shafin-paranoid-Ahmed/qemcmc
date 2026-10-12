"""CuPy exact-enumeration reference for the 20-bit Stage-1 GPU backend."""

from __future__ import annotations

from dataclasses import dataclass

import cupy as cp
import numpy as np


@dataclass
class GPUExactReference:
    """Exact joint p(z, y), sufficient statistics, and partition function."""

    states_cpu: np.ndarray

    def __post_init__(self) -> None:
        self.states_cpu = np.asarray(self.states_cpu, dtype=np.float64)
        self.states = cp.asarray(self.states_cpu, dtype=cp.float64)

    def _logits(self, model) -> cp.ndarray:
        bias = cp.asarray(model.b, dtype=cp.float64)
        coupling = cp.asarray(model.j, dtype=cp.float64)
        class_fields = cp.asarray(model.u, dtype=cp.float64)
        class_bias = cp.asarray(model.c, dtype=cp.float64)
        base = self.states @ bias + 0.5 * cp.einsum(
            "bi,ij,bj->b", self.states, coupling, self.states
        )
        return base[:, None] + self.states @ class_fields.T + class_bias

    @staticmethod
    def _probability(logits: cp.ndarray) -> tuple[cp.ndarray, float]:
        peak = cp.max(logits)
        weights = cp.exp(logits - peak)
        total = cp.sum(weights)
        log_partition = float((peak + cp.log(total)).item())
        return weights / total, log_partition

    def stats(self, model) -> tuple[dict[str, np.ndarray], np.ndarray, float]:
        probability, log_partition = self._probability(self._logits(model))
        marginal = cp.sum(probability, axis=1)
        mean = marginal @ self.states
        pair = self.states.T @ (marginal[:, None] * self.states)
        class_fields = probability.T @ self.states
        class_mass = cp.sum(probability, axis=0)
        pair_cpu = cp.asnumpy(pair)
        np.fill_diagonal(pair_cpu, 0.0)
        result = {
            "b": cp.asnumpy(mean),
            "j": pair_cpu,
            "u": cp.asnumpy(class_fields),
            "c": cp.asnumpy(class_mass),
        }
        probability_cpu = cp.asnumpy(probability)
        cp.cuda.get_current_stream().synchronize()
        return result, probability_cpu, log_partition

    def log_partition(self, model) -> float:
        _, log_partition = self._probability(self._logits(model))
        cp.cuda.get_current_stream().synchronize()
        return log_partition
