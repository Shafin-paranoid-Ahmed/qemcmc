"""Run CPU unit tests explicitly, without importing the optional GPU backend."""
import unittest

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        "test_exact", "test_qemcmc", "test_stage1", "test_adaptive_controller",
    ])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
