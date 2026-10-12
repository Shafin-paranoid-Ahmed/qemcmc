from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from exact import all_spins
from finalize_stage1 import validate_canonical_budget
import stage1_train
from stage1_train import aggregate_iat, states_to_exact_indices


class Stage1MetricTests(unittest.TestCase):
    def test_exact_enumeration_indices_round_trip(self):
        states = all_spins(4)
        np.testing.assert_array_equal(states_to_exact_indices(states), np.arange(16))

    def test_iat_is_aggregated_within_chains(self):
        traces = np.array([[1.0, -1.0], [-1.0, 1.0], [1.0, -1.0], [-1.0, 1.0]])
        self.assertEqual(aggregate_iat(traces), 1.0)

    def test_g3_v2_gpu_finalizer_requires_registered_budget(self):
        validate_canonical_budget("g3-v2-gpu", (100, 1, 32, "g3-v2-gpu", "gpu", 20))
        with self.assertRaises(RuntimeError):
            validate_canonical_budget("g3-v2-gpu", (99, 1, 32, "g3-v2-gpu", "gpu", 20))
        with self.assertRaises(RuntimeError):
            validate_canonical_budget("g3-v2-gpu", (100, 1, 32, "g3-v2-gpu", "cpu", 20))


class ScalingLadderTests(unittest.TestCase):
    def test_level_c_reads_distinct_tagged_code_files_at_ladder_widths(self):
        code_tags = {
            22: "stage1-22bit-ladder22-v1-gpu",
            24: "stage1-24bit-ladder24-v1-gpu",
        }
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary:
            results = Path(temporary)
            for bits, code_tag in code_tags.items():
                path = results / f"codes_frozenresnet_level-c_0_{code_tag}_codes.csv"
                fields = ["image_id", "partition", "label", *[f"bit_{i}" for i in range(bits)]]
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerow({
                        "image_id": f"tiny-{bits}",
                        "partition": "train",
                        "label": 2,
                        **{f"bit_{i}": i % 2 for i in range(bits)},
                    })

            with mock.patch.object(stage1_train, "RESULTS", results):
                for bits in code_tags:
                    with self.subTest(bits=bits):
                        codes, labels, partitions = stage1_train.read_dataset("c", 0, bits)
                        self.assertEqual(codes.shape, (1, bits))
                        np.testing.assert_array_equal(labels, np.array([2]))
                        np.testing.assert_array_equal(partitions, np.array(["train"]))

    def test_resume_budget_guard_rejects_bits_mismatch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary:
            results = Path(temporary)
            prefix = "stage1_qemcmc_level-c_0_ladder22-v1-gpu"
            state_path = results / f"{prefix}_state.json"
            existing_budget = {
                "level": "c", "sampler": "qemcmc", "seed": 0,
                "updates": 3, "chains": 1, "proposal_steps": 32,
                "tag": "ladder22-v1-gpu", "backend": "gpu", "bits": 20,
                "sampler_variant": "qemcmc", "reward_signal": "none",
                "persistence": False,
            }
            state_path.write_text(json.dumps({"budget": existing_budget}), encoding="utf-8")
            argv = [
                "stage1_train.py", "--level", "c", "--sampler", "qemcmc",
                "--seed", "0", "--updates", "3", "--chains", "1",
                "--proposal-steps", "32", "--backend", "gpu", "--bits", "22",
                "--tag", "ladder22-v1-gpu",
            ]
            with mock.patch.object(stage1_train, "RESULTS", results), mock.patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(RuntimeError, "resume budget mismatch"):
                    stage1_train.main()


if __name__ == "__main__":
    unittest.main()
