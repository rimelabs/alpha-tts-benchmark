"""Seeded, deterministic sentence generators for the evaluation corpus.

Each generator module exposes:

    generate(rng: random.Random, n: int) -> list[dict]

returning exactly ``n`` unique sentences as dicts with keys including
``category``, ``subcategory``, ``text``, ``notes``, and ``template_id``. Sentence ids are
assigned later by ``corpus.build``. Generators must be pure functions of
the ``rng`` state so the same seed always yields the same corpus.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable


def sentence(
    category: str,
    subcategory: str,
    text: str,
    notes: str = "",
    spell_spans: list[str] | None = None,
    template: str | None = None,
) -> dict:
    """``spell_spans`` lists the exact substrings of ``text`` (e.g. an
    alphanumeric code) that should receive character-by-character reading
    treatment when rendering provider-specific input (see corpus.render).
    """
    template_id = (
        hashlib.sha256(template.encode("utf-8")).hexdigest()[:16]
        if template is not None
        else None
    )
    return {
        "category": category,
        "subcategory": subcategory,
        "text": text,
        "notes": notes,
        "spell_spans": spell_spans or [],
        "template_id": template_id,
        "tags": [],
    }


def framed_sentence(
    rng: random.Random,
    category: str,
    subcategory: str,
    frames: list[str],
    *,
    values: dict[str, object],
    notes: str = "",
    spell_spans: list[str] | None = None,
) -> dict:
    """Choose one frame and retain its stable identity with the rendered text."""
    frame = rng.choice(frames)
    return sentence(
        category,
        subcategory,
        frame.format(**values),
        notes,
        spell_spans=spell_spans,
        template=frame,
    )


def sample_unique(
    rng: random.Random,
    make: Callable[[random.Random], dict],
    n: int,
    max_attempts_per_item: int = 200,
) -> list[dict]:
    """Draw from ``make`` until ``n`` sentences with unique text are collected."""
    out: list[dict] = []
    seen: set[str] = set()
    attempts = 0
    while len(out) < n:
        attempts += 1
        if attempts > n * max_attempts_per_item:
            raise RuntimeError(
                f"could not generate {n} unique sentences "
                f"(got {len(out)} after {attempts} attempts)"
            )
        s = make(rng)
        if s["text"] in seen:
            continue
        seen.add(s["text"])
        out.append(s)
    return out
