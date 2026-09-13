from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from claim_rules import assess_directional_claim


class ClaimRulesTest(unittest.TestCase):
    def test_direction_requires_interval_and_holm_support(self) -> None:
        supported = assess_directional_claim(0.2, [0.05, 0.35], 0.04)
        self.assertEqual(supported["status"], "rime_direction_supported")
        self.assertEqual(supported["magnitude_bound_nearest_zero"], 0.05)
        self.assertFalse(supported["equivalence_or_parity_claim_allowed"])

        inconclusive = assess_directional_claim(0.2, [-0.01, 0.4], 0.01)
        self.assertEqual(inconclusive["status"], "inconclusive")
        self.assertFalse(inconclusive["directional_claim_allowed"])
        self.assertEqual(inconclusive["magnitude_bound_nearest_zero"], 0.0)


if __name__ == "__main__":
    unittest.main()
