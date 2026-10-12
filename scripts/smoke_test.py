"""Small synthetic sampler and local metrics-bridge check; writes no results."""
import numpy as np
from common import ROOT, SPLITS, load_split
from metrics import classification_metrics as direct_metrics
from qemcmc import ExactQuantumProposal, index_to_spins, planted_instance
from stage1_train import classification_metrics


def main():
    assert SPLITS == ROOT / "splits"
    for seed in range(3):
        split = load_split(seed)
        train, val, test = (set(split[part]) for part in ("train", "val", "test"))
        assert train and val and test
        assert not (train & val or train & test or val & test)
    probabilities = np.array([[.8, .1, .1], [.2, .6, .2], [.1, .4, .5], [.1, .7, .2]])
    labels = np.array([0, 1, 2, 2])
    assert classification_metrics(probabilities, labels) == direct_metrics(probabilities, labels)
    bias, coupling, _ = planted_instance(4, 0)
    distribution = ExactQuantumProposal(bias, coupling).distribution(index_to_spins(0, 4), 7.25, .41)
    assert np.isfinite(distribution).all() and np.all(distribution >= 0)
    np.testing.assert_allclose(distribution.sum(), 1, atol=1e-12)
    print("PASS frozen splits, local metrics subprocess parity, and 4-spin quantum proposal")


if __name__ == "__main__":
    main()
