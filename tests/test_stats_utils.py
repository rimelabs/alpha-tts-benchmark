from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from stats_utils import (
    bootstrap_mean,
    clustered_bootstrap_mean,
    clustered_sign_flip_p,
    holm_adjust,
)


class StatsUtilsTest(unittest.TestCase):
    def test_item_bootstrap_is_deterministic(self) -> None:
        first = bootstrap_mean([0.0, 1.0, 1.0], n_boot=100, seed=4)
        second = bootstrap_mean([0.0, 1.0, 1.0], n_boot=100, seed=4)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first[0], 2 / 3)

    def test_holm_adjustment_is_monotonic_in_rank_order(self) -> None:
        adjusted = holm_adjust({"a": 0.01, "b": 0.03, "c": 0.04, "d": 0.5})
        self.assertAlmostEqual(adjusted["a"], 0.04)
        self.assertAlmostEqual(adjusted["b"], 0.09)
        self.assertAlmostEqual(adjusted["c"], 0.09)
        self.assertAlmostEqual(adjusted["d"], 0.5)

    def test_clustered_bootstrap_is_deterministic(self) -> None:
        values = [1.0, 1.0, -1.0, -1.0]
        families = ["a", "a", "b", "b"]
        first = clustered_bootstrap_mean(
            values,
            families,
            n_boot=200,
            seed=7,
        )
        second = clustered_bootstrap_mean(
            values,
            families,
            n_boot=200,
            seed=7,
        )
        self.assertEqual(first, second)
        self.assertEqual(first[0], 0.0)

    def test_cluster_sign_flip_uses_family_as_unit(self) -> None:
        values = [1.0, 1.0, 1.0, 1.0]
        families = ["a", "a", "b", "b"]
        self.assertEqual(
            clustered_sign_flip_p(values, families),
            0.5,
        )


if __name__ == "__main__":
    unittest.main()
