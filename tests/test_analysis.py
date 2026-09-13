from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from analyze_comparison import (
    analyze as analyze_comparison,
    combine_repeated_item_rows,
    load_corpus_metadata,
    markdown_report as comparison_markdown_report,
    parse_export,
)
from analyze_fidelity import (
    ALPHABENCH_SUBCATEGORY_COUNTS,
    ALPHABENCH_SUBCATEGORY_WEIGHTS,
    analyze,
    markdown_report as fidelity_markdown_report,
    parse_payload,
)
from analyze_alphabench_qualitative import (
    analyze_qualitative,
    markdown_report as qualitative_markdown_report,
    parse_source as parse_qualitative_source,
)
from stats_utils import stratified_equal_family_mean
from submit_fidelity_podonos import (
    ALPHABENCH_TASK_VERSION,
    FIDELITY_TEMPLATE,
)


class AlphaModelExportTest(unittest.TestCase):
    def test_grouped_votes_and_duplicate_annotation_section_are_read_once(self) -> None:
        annotation = {"content": "ABC", "reason": "[OMISSION] B was missing"}
        clip = {
            "path": "model/item-1.wav",
            "model_tag": "model",
            "script": "ABC",
            "Reading error": 2,
            "No reading error": 1,
            "annotations": [annotation, {"content": "ABC", "reason": None}],
        }
        payload = [
            {"model": "model", "responses": [{"responses": [clip]}]},
            {"type": "annotation", "responses": [clip]},
        ]
        rows = parse_qualitative_source(
            payload,
            source="model.json",
            corpus_families={"item-1": "family"},
            corpus_subcategories={"item-1": "confirmation_code"},
            corpus_diagnostics={},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["error_votes"], 2)
        self.assertEqual(rows[0]["pass_votes"], 1)
        self.assertEqual(rows[0]["notes"], ["[OMISSION] B was missing"])
        self.assertEqual(len(clip["annotations"]), 2)

    def test_conflicting_duplicate_notes_are_rejected(self) -> None:
        clip = {
            "path": "model/item-1.wav",
            "model_tag": "model",
            "Reading error": 1,
            "No reading error": 2,
            "annotations": [{"reason": "[OMISSION] missing B"}],
        }
        payload = [
            {"model": "model", "responses": [{"responses": [clip]}]},
            {"type": "annotation", "responses": [{
                **clip, "annotations": [{"reason": "[INSERTION] extra B"}],
            }]},
        ]
        with self.assertRaisesRegex(ValueError, "conflicting AlphaBench annotations"):
            parse_qualitative_source(
                payload,
                source="model.json",
                corpus_families={},
                corpus_subcategories={},
                corpus_diagnostics={},
            )


class ComparisonAnalysisTest(unittest.TestCase):
    def test_score_is_recoded_from_target_identity(self) -> None:
        payload = [{
            "responses": [{
                "targets": [
                    {
                        "type": "A",
                        "path": "competitor/item-1.wav",
                        "model_tag": "competitor_voice",
                        "tags": ["utt_item-1", "family_family-1"],
                    },
                    {
                        "type": "B",
                        "path": "rime/item-1.wav",
                        "model_tag": "rime_coda_voice",
                        "tags": ["utt_item-1", "family_family-1"],
                    },
                ],
                "frequency": [{"score": -2, "count": 2}, {"score": 0, "count": 1}],
            }],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rows = parse_export(
                path,
                rime_prefix="rime_",
                corpus_families={},
            )
        self.assertEqual(rows[0]["rime_target"], "B")
        self.assertAlmostEqual(rows[0]["rime_minus_competitor"], 4 / 3)

    def test_registered_corpus_family_overrides_no_export_fallback(self) -> None:
        payload = [{
            "responses": [{
                "targets": [
                    {
                        "type": "A",
                        "path": "rime/item-1.wav",
                        "model_tag": "rime_voice",
                        "tags": ["utt_item-1", "family_old-family"],
                    },
                    {
                        "type": "B",
                        "path": "competitor/item-1.wav",
                        "model_tag": "competitor_voice",
                        "tags": ["utt_item-1", "family_old-family"],
                    },
                ],
                "frequency": [{"score": 1, "count": 3}],
            }],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "corpus"):
                parse_export(
                    path,
                    rime_prefix="rime_",
                    corpus_families={"item-1": "new-family"},
                    require_corpus_match=True,
                )

    def test_repeated_item_jobs_pool_moments(self) -> None:
        rows = [
            {
                "competitor": "competitor",
                "item_id": "item-1",
                "family_id": "family-1",
                "judgments": 2,
                "rime_minus_competitor": 1.0,
                "within_variance": 2.0,
                "source": "tranche",
            },
            {
                "competitor": "competitor",
                "item_id": "item-1",
                "family_id": "family-1",
                "judgments": 1,
                "rime_minus_competitor": -2.0,
                "within_variance": 0.0,
                "source": "topup",
            },
        ]
        combined = combine_repeated_item_rows(rows)
        self.assertEqual(combined[0]["judgments"], 3)
        self.assertAlmostEqual(combined[0]["rime_minus_competitor"], 0.0)
        self.assertAlmostEqual(combined[0]["within_variance"], 4.0)

    def test_report_includes_kish_g_and_win_tie_loss_proportions(self) -> None:
        rows = [
            {
                "competitor": "competitor",
                "item_id": f"item-{index}",
                "family_id": family,
                "judgments": 3,
                "rime_minus_competitor": value,
                "within_variance": 0.0,
                "source": "test",
            }
            for index, (family, value) in enumerate([
                ("family-1", 1.0),
                ("family-1", 0.0),
                ("family-2", -1.0),
            ])
        ]
        result = analyze_comparison(rows, n_boot=100, seed=4)
        comparison = result["competitor"]
        self.assertAlmostEqual(comparison["kish_effective_families"], 1.8)
        self.assertAlmostEqual(comparison["win_item_rate"], 1 / 3)
        self.assertAlmostEqual(comparison["tie_item_rate"], 1 / 3)
        self.assertAlmostEqual(comparison["loss_item_rate"], 1 / 3)
        report = comparison_markdown_report("SupportBench", result)
        self.assertIn("Kish G", report)
        self.assertIn("33.3%/33.3%/33.3%", report)
        self.assertNotIn("Coarser dependence sensitivity", report)
        self.assertIn("claim status", report)

    def test_content_author_sensitivity_uses_frozen_notes(self) -> None:
        corpus = [
            {
                "id": "book-1",
                "family_id": "content-source:book-one-author-name",
                "category": "content_reading",
                "subcategory": "literature",
                "notes": "Source: Book One, Author Name",
            },
            {
                "id": "book-2",
                "family_id": "content-source:book-two-author-name",
                "category": "content_reading",
                "subcategory": "literature",
                "notes": "Source: Book Two, Author Name",
            },
            {
                "id": "narration-1",
                "family_id": "generated-template:narration:one",
                "category": "content_reading",
                "subcategory": "narration",
                "notes": "authored narration",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "content.jsonl"
            path.write_text(
                "\n".join(json.dumps(row) for row in corpus) + "\n",
                encoding="utf-8",
            )
            families, coarse = load_corpus_metadata(path)
        self.assertNotEqual(families["book-1"], families["book-2"])
        self.assertEqual(coarse["book-1"], "content-author:author-name")
        self.assertEqual(coarse["book-1"], coarse["book-2"])
        self.assertEqual(coarse["narration-1"], "content-genre:narration")

        rows = [
            {
                "competitor": "competitor",
                "item_id": row["id"],
                "family_id": families[row["id"]],
                "coarse_cluster_id": coarse[row["id"]],
                "judgments": 3,
                "rime_minus_competitor": value,
                "within_variance": 0.0,
                "source": "test",
            }
            for row, value in zip(corpus, [1.0, 0.5, -0.5], strict=True)
        ]
        result = analyze_comparison(rows, n_boot=100, seed=4)
        self.assertEqual(
            result["competitor"]["sensitivity_coarse_dependency"]["clusters"],
            2,
        )
        report = comparison_markdown_report("ContentBench", result)
        self.assertIn("Coarser dependence sensitivity", report)


class FidelityAnalysisTest(unittest.TestCase):
    def test_registered_alpha_weights_match_corpus_and_protocol(self) -> None:
        corpus_counts = Counter(
            json.loads(line)["subcategory"]
            for line in (REPO_ROOT / "data" / "alphabench.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
        self.assertEqual(dict(corpus_counts), ALPHABENCH_SUBCATEGORY_COUNTS)
        self.assertEqual(sum(ALPHABENCH_SUBCATEGORY_COUNTS.values()), 580)
        self.assertAlmostEqual(sum(ALPHABENCH_SUBCATEGORY_WEIGHTS.values()), 1.0)

        protocol = (REPO_ROOT / "PROTOCOL.md").read_text(encoding="utf-8")
        for subcategory, count in ALPHABENCH_SUBCATEGORY_COUNTS.items():
            self.assertIn(
                f"| `{subcategory}` | {count} | `{count} / 580` |",
                protocol,
            )

    def test_task_judges_the_complete_script(self) -> None:
        question = FIDELITY_TEMPLATE["questions"][0]
        self.assertEqual(question["question"], "Does this recording contain a reading error compared with the displayed script?")
        self.assertEqual(
            [option["label_text"] for option in question["options"]],
            ["No reading error", "Reading error"],
        )
        instructions = " ".join(
            instruction["description"]
            for instruction in FIDELITY_TEMPLATE["instructions"]
        )
        self.assertIn("hyphens are visual separators", instructions)
        self.assertIn(
            "[EARLY_STOP]",
            FIDELITY_TEMPLATE["annotations"][0]["description"],
        )
        self.assertEqual(
            ALPHABENCH_TASK_VERSION,
            "1.0.0",
        )

    def test_majority_of_three_and_paired_direction(self) -> None:
        payload = [{
            "responses": [
                {
                    "path": "rime/item-1.wav",
                    "model_tag": "rime_coda_voice",
                    "tags": ["utt_item-1", "family_family-1"],
                    "script": "One.",
                    "Reading error": 0,
                    "No reading error": 3,
                    "annotations": [],
                },
                {
                    "path": "competitor/item-1.wav",
                    "model_tag": "competitor_voice",
                    "tags": ["utt_item-1", "family_family-1"],
                    "script": "One.",
                    "Reading error": 2,
                    "No reading error": 1,
                    "annotations": [],
                },
            ],
        }]
        rows = parse_payload(
            payload,
            source="test",
            corpus_families={},
            corpus_diagnostics={
                "item-1": {
                    "target_entities": 1,
                    "script_length_chars": 4,
                }
            },
        )
        result = analyze(
            rows,
            baseline="rime_coda_voice",
            n_boot=100,
            seed=3,
            primary_interval_method="stratified family percentile bootstrap",
        )
        comparison = result["comparisons"]["competitor_voice"]
        self.assertEqual(
            comparison["competitor_minus_rime_error_rate"],
            1.0,
        )
        self.assertAlmostEqual(
            comparison["sensitivity_weighted_mean_vote_error_effect"],
            2 / 3,
        )
        self.assertAlmostEqual(
            result["providers"]["competitor_voice"]
            ["majority_error_clips_per_target_entity_diagnostic"],
            1.0,
        )
        self.assertEqual(
            result["corpus_diagnostics"]["script_length_chars_mean"],
            4.0,
        )
        report = fidelity_markdown_report(result)
        self.assertIn("mean-of-votes sensitivity", report)
        self.assertIn("Script-length balance diagnostic", report)
        self.assertIn("majority-error clips / target entity", report)

    def test_alpha_weighting_is_equal_frame_within_subcategory(self) -> None:
        value = stratified_equal_family_mean(
            [0.0, 0.0, 1.0, 1.0],
            ["large", "large", "small", "other"],
            ["codes", "codes", "codes", "names"],
            stratum_weights={"codes": 0.75, "names": 0.25},
        )
        self.assertAlmostEqual(value, 0.625)

    def test_qualitative_report_has_labels_but_no_provider_claims(self) -> None:
        rows = [
            {
                "model_tag": "provider_voice",
                "item_id": "item-1",
                "family_id": "family-1",
                "subcategory": "name_spelling",
                "script": "Yes, that's spelled P-H-I-L-L-I-P.",
                "target_entities": 1,
                "script_length_chars": 39,
                "error_votes": 2,
                "pass_votes": 1,
                "majority_error": True,
                "notes": [
                    "[EARLY_STOP] Expected final P; audio ended after I."
                ],
                "source": "test",
            },
            {
                "model_tag": "provider_voice",
                "item_id": "item-2",
                "family_id": "family-2",
                "subcategory": "name_spelling",
                "script": "Yes, that's spelled K-E-N-J-I.",
                "target_entities": 1,
                "script_length_chars": 32,
                "error_votes": 1,
                "pass_votes": 2,
                "majority_error": False,
                "notes": ["The dash was not pronounced."],
                "source": "test",
            },
        ]
        result = analyze_qualitative(rows)
        provider = result["providers"]["provider_voice"]
        self.assertFalse(result["inferential_provider_claims_allowed"])
        self.assertEqual(
            provider["failure_label_clip_counts"]["EARLY_STOP"],
            1,
        )
        self.assertEqual(
            provider["review_flag_clip_counts"]
            ["VISUAL_SEPARATOR_FALSE_POSITIVE"],
            1,
        )
        self.assertNotIn("comparisons", result)
        self.assertEqual(
            result["failure_interpretation"]["EARLY_STOP"]["disposition"],
            "functional failure",
        )
        self.assertIn("pacing", result["not_functional_failures"])
        report = qualitative_markdown_report(result)
        self.assertIn("qualitative failure report", report)
        self.assertIn("How functional impact is judged", report)
        self.assertNotIn("Holm", report)
        self.assertNotIn("95%", report)


if __name__ == "__main__":
    unittest.main()
