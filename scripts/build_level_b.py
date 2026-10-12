"""Pre-registered Level-B construction (recorded 2026-07-13 before Stage 1).

Each seed has four template modes with pairwise Hamming distance >= 6.
Samples select modes with probabilities 40/30/20/10 percent, assign one
pseudo-class per mode, then independently flip bits with p=0.05 (easy) or
p=0.15 (hard). Each tier contains 2,000 train, 500 validation, and 500 test
examples. Seeds are 0, 1, and 2. The two fixed datasets are level-b-easy and
level-b-hard; this script does not tune their construction from results.
"""
from __future__ import annotations

import argparse

import numpy as np

from common import RESULTS, write_json, write_rows


def templates_for_seed(seed: int, bits: int = 16) -> np.ndarray:
    rng = np.random.default_rng(seed)
    templates = []
    while len(templates) < 4:
        candidate = rng.integers(0, 2, bits, dtype=np.int8)
        if all(np.count_nonzero(candidate != other) >= 6 for other in templates):
            templates.append(candidate)
    return np.stack(templates)


def build(seed: int, tier: str, flip_probability: float, bits: int, suffix: str) -> int:
    rng = np.random.default_rng(10_000 + seed)
    templates = templates_for_seed(seed, bits)
    rows = []
    for partition, count in (("train", 2000), ("val", 500), ("test", 500)):
        labels = rng.choice(4, size=count, p=[0.4, 0.3, 0.2, 0.1])
        codes = templates[labels].copy()
        codes ^= (rng.random(codes.shape) < flip_probability).astype(np.int8)
        for index, (label, code) in enumerate(zip(labels, codes)):
            row = {"sample_id": f"{partition}_{index}", "partition": partition, "label": int(label)}
            row.update({f"bit_{bit}": int(value) for bit, value in enumerate(code)})
            rows.append(row)
    tag = f"codes_planted_level-b-{tier}_{seed}{suffix}"
    write_rows(RESULTS / f"{tag}_codes.csv", rows)
    write_json(RESULTS / f"{tag}_metadata.json", {
        "seed": seed, "bits": bits, "modes": 4, "mode_weights": [0.4, 0.3, 0.2, 0.1],
        "flip_probability": flip_probability, "train": 2000, "val": 500, "test": 500,
        "minimum_template_hamming_distance": int(min(
            np.count_nonzero(templates[i] != templates[j])
            for i in range(4) for j in range(i)
        )),
        "templates": templates.tolist(),
    })
    return int(min(
        np.count_nonzero(templates[i] != templates[j])
        for i in range(4) for j in range(i)
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--bits", type=int, default=16, choices=range(6, 21))
    parser.add_argument("--tag", default=None)
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    achieved = []
    for seed in args.seeds:
        achieved.append(build(seed, "easy", 0.05, args.bits, suffix))
        achieved.append(build(seed, "hard", 0.15, args.bits, suffix))
    print(
        "Level-B easy/hard artifacts written for",
        args.seeds,
        f"at {args.bits} bits; achieved minimum Hamming distance={min(achieved)}",
    )


if __name__ == "__main__":
    main()
