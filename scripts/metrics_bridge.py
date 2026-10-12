"""Run the unchanged Full-QCNN metrics implementation from the CPU stack."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "metrics.py"
spec = importlib.util.spec_from_file_location("frozen_qcnn_metrics", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

payload = json.load(sys.stdin)
metrics = module.classification_metrics(
    np.asarray(payload["probabilities"], dtype=float),
    np.asarray(payload["labels"], dtype=int),
)
print(json.dumps(metrics))
