from __future__ import annotations

import unittest
from collections import defaultdict

from corpus.build import build


class CorpusFamilyTest(unittest.TestCase):
    def test_frozen_family_counts(self) -> None:
        alpha, support, content, _ = build()
        self.assertEqual(len({row["family_id"] for row in alpha}), 83)
        self.assertEqual(len({row["family_id"] for row in support}), 286)
        self.assertEqual(len({row["family_id"] for row in content}), 223)

    def test_generated_families_follow_source_templates(self) -> None:
        alpha, support, _, ambiguous = build()
        by_template: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for row in alpha + support + ambiguous:
            self.assertTrue(row["template_id"])
            self.assertNotEqual(
                row["family_id"],
                f"{row['category']}:{row['subcategory']}",
            )
            key = (row["category"], row["subcategory"], row["template_id"])
            by_template[key].add(row["family_id"])
        self.assertTrue(all(len(families) == 1 for families in by_template.values()))

    def test_alphabench_frames_are_balanced_within_subcategory(self) -> None:
        alpha, _, _, _ = build()
        sizes: dict[tuple[str, str], int] = defaultdict(int)
        for row in alpha:
            sizes[(row["subcategory"], row["family_id"])] += 1
        by_subcategory: dict[str, list[int]] = defaultdict(list)
        for (subcategory, _), size in sizes.items():
            by_subcategory[subcategory].append(size)
        for frame_sizes in by_subcategory.values():
            self.assertLessEqual(max(frame_sizes) - min(frame_sizes), 1)

    def test_content_families_follow_source_work_or_item(self) -> None:
        _, _, content, _ = build()
        literature = [row for row in content if row["subcategory"] == "literature"]
        narration = [row for row in content if row["subcategory"] == "narration"]
        self.assertEqual(len({row["family_id"] for row in literature}), 23)
        self.assertEqual(len({row["family_id"] for row in narration}), 200)


if __name__ == "__main__":
    unittest.main()
