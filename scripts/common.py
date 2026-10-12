from __future__ import annotations

import csv
import os
import json
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT
DATA_ROOT = Path(os.environ.get("QEMCMC_DATA_ROOT", str(ROOT / "data"))).expanduser().resolve()
RESULTS = PILOT / "results"
SPLITS = ROOT / "splits"


def seed_all(seed: int) -> np.random.Generator:
    random.seed(seed)
    np.random.seed(seed)
    return np.random.default_rng(seed)


def load_split(seed: int) -> dict:
    return json.loads((SPLITS / f"split_seed{seed}.json").read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_rows(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("refusing to write an empty CSV")
    fields = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_codes(seed: int, tag: str | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    suffix = f"_{tag}" if tag else ""
    path = RESULTS / f"codes_frozenresnet_level-c_{seed}{suffix}_codes.csv"
    data = np.genfromtxt(path, delimiter=",", names=True, dtype=None, encoding="utf-8")
    bit_names = [name for name in data.dtype.names if name.startswith("bit_")]
    x = np.column_stack([data[name] for name in bit_names]).astype(np.int8)
    return x, data["label"].astype(int), data["partition"]
