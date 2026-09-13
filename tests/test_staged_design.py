from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sample_staged_design import select_preference_tranche
from analyze_alpha_icc_pilot import one_way_icc
from plan_variance_tranche import plan


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


class StagedDesignTest(unittest.TestCase):
    def test_alpha_pilot_has_registered_frame_structure(self) -> None:
        sample = read_jsonl(REPO_ROOT / "data" / "pilot_alphabench_icc.jsonl")
        families = Counter(row["family_id"] for row in sample)
        self.assertEqual(len(sample), 90)
        self.assertEqual(len(families), 15)
        self.assertEqual(set(families.values()), {6})
        self.assertEqual(
            {row["subcategory"] for row in sample},
            {
                "confirmation_code",
                "confusable",
                "flight_number",
                "license_plate",
                "long_code",
                "name_spelling",
                "order_number",
                "policy_case_id",
                "tracking_number",
            },
        )

    def test_preference_tranches_have_120_items_and_repeated_families(self) -> None:
        for benchmark in ("supportbench", "contentbench"):
            rows = read_jsonl(REPO_ROOT / "data" / f"{benchmark}.jsonl")
            sample = select_preference_tranche(rows, benchmark=benchmark)
            families = Counter(row["family_id"] for row in sample)
            self.assertEqual(len(sample), 120)
            self.assertGreater(sum(count > 1 for count in families.values()), 0)

    def test_icc_detects_frame_separation(self) -> None:
        rho = one_way_icc(
            [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            ["a", "a", "a", "b", "b", "b"],
        )
        self.assertAlmostEqual(rho, 1.0)

    def test_tranche_plan_uses_full_family_sizes(self) -> None:
        corpus = [
            {"id": f"item-{index}", "family_id": f"family-{index // 2}"}
            for index in range(200)
        ]
        rows = []
        for comparison in range(4):
            for index in range(120):
                rows.append({
                    "competitor": f"competitor-{comparison}",
                    "item_id": f"item-{index}",
                    "family_id": f"family-{index // 2}",
                    "judgments": 7,
                    "rime_minus_competitor": float((index + comparison) % 3 - 1),
                    "within_variance": 0.5,
                })
        result = plan(
            rows,
            corpus=corpus,
            comparisons=4,
            power=0.8,
            alpha=0.05,
            target_mde=1.0,
            candidate_votes=[3, 5, 7],
            tranche_items=120,
            initial_votes=7,
            blinding_seed=20260826,
        )
        self.assertEqual(result["full_design"]["families"], 100)
        self.assertEqual(result["selected_votes_per_remaining_item"], 3)


if __name__ == "__main__":
    unittest.main()
