from __future__ import annotations

import json
import unittest
from pathlib import Path

from corpus.render import render_span, render_text


REPO_ROOT = Path(__file__).resolve().parent.parent


class ElevenLabsRenderingTest(unittest.TestCase):
    def test_mixed_identifier_uses_written_digits_and_no_separator_hyphens(
        self,
    ) -> None:
        rendered = render_text(
            "Order AK52562274 shipped out yesterday afternoon.",
            ["AK52562274"],
            style="elevenlabs",
        )
        self.assertEqual(
            rendered,
            "Order A, K, five, two, five, six, two, two, seven, four "
            "shipped out yesterday afternoon.",
        )
        self.assertNotIn("A-K", rendered)

    def test_real_identifier_hyphen_is_the_only_spoken_dash(self) -> None:
        self.assertEqual(
            render_span("L2X-8XH", style="elevenlabs"),
            "L, two, X, dash, eight, X, H",
        )

    def test_name_spelling_hyphens_are_visual_separators(self) -> None:
        self.assertEqual(
            render_span("P-H-I-L-L-I-P", style="elevenlabs"),
            "P, H, I, L, L, I, P",
        )

    def test_every_registered_alpha_span_avoids_literal_hyphens(self) -> None:
        rows = [
            json.loads(line)
            for line in (REPO_ROOT / "data" / "alphabench.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        for row in rows:
            for span in row["spell_spans"]:
                self.assertNotIn("-", render_span(span, style="elevenlabs"))


if __name__ == "__main__":
    unittest.main()
