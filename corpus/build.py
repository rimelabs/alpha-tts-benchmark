"""Build the evaluation corpus manifests.

Usage (from the repo root):

    uv run python -m corpus.build

Writes three corpora with no overlap:
- ``data/alphabench.jsonl`` (580 alphanumeric sentences) — fidelity eval
- ``data/supportbench.jsonl`` (750 CX sentences) — support quality eval
- ``data/contentbench.jsonl`` (400 general content sentences) — content quality eval

Plus a held-out ambiguity bench. Fully deterministic: re-running produces
byte-identical output.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

from .generators import (
    addresses_contact,
    alphanumerics,
    amounts_units,
    content_reading,
    dates_times,
    phone_numbers,
    short_responses,
    support_dialogue,
)

SEED = 20260806

# --- Alphabench (fidelity) -------------------------------------------------
# 580 sentences across the specified AlphaBench subcategories.
# 40 are long codes (20–25 chars), 40 are confusable-stress codes, 80 are
# spelled first/last names; the rest are the standard subcategories.
ALPHABENCH_TOTAL = 580
ALPHABENCH_LONG = 40
ALPHABENCH_CONFUSABLE = 40
ALPHABENCH_SPELLED = 80
ALPHABENCH_STANDARD_COUNTS = {
    "confirmation_code": 98,
    "flight_number": 66,
    "license_plate": 40,
    "order_number": 96,
    "policy_case_id": 73,
    "tracking_number": 47,
}

# --- SupportBench (support quality/naturalness) ----------------------------
SUPPORT_SPEC = [
    (phone_numbers, 100),
    (dates_times, 120),
    (amounts_units, 80),
    (addresses_contact, 60),
    (short_responses, 40),
    (support_dialogue, 350),
]
SUPPORT_TOTAL = sum(n for _, n in SUPPORT_SPEC)  # 750

# --- ContentBench (general content quality) --------------------------------
# 400 narration passages across the specified content genres.
CONTENT_TOTAL = 400

# --- Ambiguity bench (held out) --------------------------------------------
AMBIGUOUS_TOTAL = 40

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _assign_family_id(row: dict) -> None:
    """Record the independent family used by the clustered analysis.

    Generated items share a family only when they use the same source
    template. Literature excerpts share a source-work family. Authored
    one-off support lines and narration passages are independent items.
    """
    if row["category"] == "content_reading" and row["subcategory"] == "literature":
        source = row["notes"].removeprefix("Source: ").strip()
        row["family_id"] = f"content-source:{_slug(source)}"
    elif row["category"] == "content_reading":
        row["family_id"] = f"content-narration:{row['id']}"
    else:
        template_id = row.get("template_id")
        if not template_id:
            raise ValueError(
                f"generated item lacks template provenance: {row.get('id')}"
            )
        row["family_id"] = (
            f"generated-template:{row['category']}:{row['subcategory']}:"
            f"{template_id}"
        )

# Acoustically confusable letter pairs: sounds alike when spelled aloud.
_CONFUSABLE = [
    "PT", "TP", "DB", "BD",  # plosive voicing
    "MN", "NM",              # nasals
    "FV", "VF",              # fricatives
    "SZ", "ZS",              # sibilants
    "YI", "IY",              # vowel-like
    "GK", "KG",              # velar plosives
    "BV", "VB",              # voiced labial
]
CONFUSABLE_PAIRS = re.compile("|".join(_CONFUSABLE))
REPEATED_RUN = re.compile(r"(.)\1{2,}")

# --- SupportBench subcategory → group tag ----------------------------------
SUPPORT_GROUP = {
    "standalone": "phone", "local": "phone", "toll_free": "phone",
    "international": "phone", "extension": "phone",
    "date": "date_time", "time": "date_time", "range": "date_time",
    "duration": "date_time",
    "currency": "money", "percentage": "money", "account_figure": "money",
    "measurement": "measurement",
    "street_address": "address", "url": "address", "spelled_name": "address",
    "backchannel": "short_utterance",
    "retail": "dialogue", "telecom": "dialogue", "banking": "dialogue",
    "travel": "dialogue", "healthcare": "dialogue",
}


def _tag_alphabench(row: dict) -> None:
    tags = [row["subcategory"]]
    for span in row["spell_spans"]:
        # Pre-spelled names carry hyphen joiners (C-A-L-L-A-H-A-N); tag on
        # the spoken content, not the joiners.
        core = span.replace("-", "")
        if len(core) >= 16:
            tags.append("long")
        if len(core) <= 7:
            tags.append("short")
        if REPEATED_RUN.search(core):
            tags.append("repeated")
        if CONFUSABLE_PAIRS.search(core):
            tags.append("confusable")
    row["tags"] = sorted(set(tags))


def _tag_support(row: dict) -> None:
    tags = [row["subcategory"]]
    group = SUPPORT_GROUP.get(row["subcategory"])
    if group:
        tags.append(group)
    row["tags"] = sorted(set(tags))


def _tag_content(row: dict) -> None:
    row["tags"] = [row["subcategory"]]


def build() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    # -- Alphabench ----------------------------------------------------------
    n_standard = sum(ALPHABENCH_STANDARD_COUNTS.values())
    assert n_standard == (
        ALPHABENCH_TOTAL
        - ALPHABENCH_LONG
        - ALPHABENCH_CONFUSABLE
        - ALPHABENCH_SPELLED
    )
    alpha_standard = []
    for subcategory, count in ALPHABENCH_STANDARD_COUNTS.items():
        alpha_standard.extend(alphanumerics.generate_subcategory(
            random.Random(f"{SEED}-{alphanumerics.CATEGORY}-{subcategory}"),
            subcategory,
            count,
        ))

    seen = {r["text"] for r in alpha_standard}

    alpha_long_unique = alphanumerics.generate_subcategory(
        random.Random(f"{SEED}-long_code"),
        "long_code",
        ALPHABENCH_LONG,
    )
    alpha_conf_unique = alphanumerics.generate_subcategory(
        random.Random(f"{SEED}-confusable"),
        "confusable",
        ALPHABENCH_CONFUSABLE,
    )
    for row in alpha_long_unique + alpha_conf_unique:
        if row["text"] in seen:
            raise AssertionError(f"AlphaBench text collision: {row['text']}")
        seen.add(row["text"])

    # Spelled names follow the code subcategories in the item ID sequence.
    spelled_rng = random.Random(f"{SEED}-name_spelling")
    alpha_spelled = alphanumerics.generate_spelled(spelled_rng, ALPHABENCH_SPELLED)
    for r in alpha_spelled:
        assert r["text"] not in seen, f"spelled-name text collision: {r['text']}"
        seen.add(r["text"])

    alphabench = alpha_standard + alpha_long_unique + alpha_conf_unique + alpha_spelled
    for i, row in enumerate(alphabench, start=1):
        row["id"] = f"alphanumerics-{i:04d}"

    # -- SupportBench --------------------------------------------------------
    support: list[dict] = []
    for module, n in SUPPORT_SPEC:
        rng = random.Random(f"{SEED}-{module.CATEGORY}")
        rows = module.generate(rng, n)
        prefix = rows[0]["category"]
        for i, row in enumerate(rows, start=1):
            row["id"] = f"{prefix}-{i:04d}"
        support.extend(rows)

    # -- ContentBench --------------------------------------------------------
    content_rng = random.Random(f"{SEED}-{content_reading.CATEGORY}")
    content = content_reading.generate(content_rng, CONTENT_TOTAL)
    for i, row in enumerate(content, start=1):
        row["id"] = f"content_reading-{i:04d}"

    # -- Tagging -------------------------------------------------------------
    for row in alphabench + support + content:
        _assign_family_id(row)
    for row in alphabench:
        _tag_alphabench(row)
    for row in support:
        _tag_support(row)
    for row in content:
        _tag_content(row)

    # -- Ambiguity bench -----------------------------------------------------
    ambiguous = alphanumerics.generate_ambiguous(
        random.Random(f"{SEED}-ambiguous"), AMBIGUOUS_TOTAL,
    )
    for i, row in enumerate(ambiguous, start=1):
        row["id"] = f"ambiguous-{i:04d}"
        _assign_family_id(row)

    _check(alphabench, support, content, ambiguous)
    return alphabench, support, content, ambiguous


def _check(
    alphabench: list[dict],
    support: list[dict],
    content: list[dict],
    ambiguous: list[dict],
) -> None:
    assert len(alphabench) == ALPHABENCH_TOTAL, (
        f"alphabench: expected {ALPHABENCH_TOTAL}, got {len(alphabench)}"
    )
    assert len(support) == SUPPORT_TOTAL, (
        f"supportbench: expected {SUPPORT_TOTAL}, got {len(support)}"
    )
    assert len(content) == CONTENT_TOTAL, (
        f"contentbench: expected {CONTENT_TOTAL}, got {len(content)}"
    )
    assert len(ambiguous) == AMBIGUOUS_TOTAL

    alpha_ids = {r["id"] for r in alphabench}
    support_ids = {r["id"] for r in support}
    content_ids = {r["id"] for r in content}
    assert not alpha_ids & support_ids, "overlap between alphabench and supportbench"
    assert not alpha_ids & content_ids, "overlap between alphabench and contentbench"
    assert not support_ids & content_ids, "overlap between supportbench and contentbench"

    for r in alphabench + support + content + ambiguous:
        assert "{" not in r["text"] and "}" not in r["text"], (
            f"unfilled template slot: {r['id']}"
        )
        assert r["text"].strip() == r["text"] and r["text"], (
            f"whitespace issue: {r['id']}"
        )
        for span in r["spell_spans"]:
            assert span in r["text"], (
                f"spell span {span!r} not in text: {r['id']}"
            )
        assert r["subcategory"] != "promo_code" or r["id"].startswith("ambiguous-"), (
            f"word-like code leaked into main corpus: {r['id']}"
        )
        assert r.get("family_id"), f"missing family_id: {r['id']}"
        if r["category"] != "content_reading":
            assert r.get("template_id"), f"missing template_id: {r['id']}"

    assert all(r["category"] == "alphanumerics" for r in alphabench)
    assert all(r["category"] != "alphanumerics" for r in support)
    assert all(r["category"] == "content_reading" for r in content)

    alpha_texts = [r["text"] for r in alphabench]
    assert len(set(alpha_texts)) == len(alpha_texts), "duplicate text in alphabench"
    support_texts = [r["text"] for r in support]
    assert len(set(support_texts)) == len(support_texts), "duplicate text in supportbench"
    content_texts = [r["text"] for r in content]
    assert len(set(content_texts)) == len(content_texts), "duplicate text in contentbench"

    long_count = sum(1 for r in alphabench if r["subcategory"] == "long_code")
    assert long_count == ALPHABENCH_LONG, (
        f"expected {ALPHABENCH_LONG} long codes, got {long_count}"
    )
    conf_count = sum(1 for r in alphabench if r["subcategory"] == "confusable")
    assert conf_count == ALPHABENCH_CONFUSABLE, (
        f"expected {ALPHABENCH_CONFUSABLE} confusable codes, got {conf_count}"
    )
    spelled_count = sum(1 for r in alphabench if r["subcategory"] == "name_spelling")
    assert spelled_count == ALPHABENCH_SPELLED, (
        f"expected {ALPHABENCH_SPELLED} spelled names, got {spelled_count}"
    )
    standard_counts = {
        subcategory: sum(
            1 for row in alphabench if row["subcategory"] == subcategory
        )
        for subcategory in ALPHABENCH_STANDARD_COUNTS
    }
    assert standard_counts == ALPHABENCH_STANDARD_COUNTS, (
        f"registered AlphaBench mix changed: {standard_counts}"
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    keys = [
        "id",
        "family_id",
        "template_id",
        "category",
        "subcategory",
        "text",
        "notes",
        "spell_spans",
        "tags",
    ]
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({k: row[k] for k in keys}, ensure_ascii=False) + "\n")


def main() -> None:
    alphabench, support, content, ambiguous = build()
    DATA_DIR.mkdir(exist_ok=True)
    write_jsonl(DATA_DIR / "alphabench.jsonl", alphabench)
    write_jsonl(DATA_DIR / "supportbench.jsonl", support)
    write_jsonl(DATA_DIR / "contentbench.jsonl", content)
    write_jsonl(DATA_DIR / "ambiguous_bench.jsonl", ambiguous)

    by_sub: dict[str, int] = {}
    for r in alphabench:
        by_sub[r["subcategory"]] = by_sub.get(r["subcategory"], 0) + 1
    print(
        f"alphabench: {len(alphabench)} sentences, "
        f"{len({row['family_id'] for row in alphabench})} families -> "
        f"{DATA_DIR / 'alphabench.jsonl'}"
    )
    for sub, count in by_sub.items():
        print(f"  {sub}: {count}")

    by_cat: dict[str, int] = {}
    for r in support:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    print(
        f"supportbench: {len(support)} sentences, "
        f"{len({row['family_id'] for row in support})} families -> "
        f"{DATA_DIR / 'supportbench.jsonl'}"
    )
    for cat, count in by_cat.items():
        print(f"  {cat}: {count}")

    by_sub_c: dict[str, int] = {}
    for r in content:
        by_sub_c[r["subcategory"]] = by_sub_c.get(r["subcategory"], 0) + 1
    print(
        f"contentbench: {len(content)} sentences, "
        f"{len({row['family_id'] for row in content})} families -> "
        f"{DATA_DIR / 'contentbench.jsonl'}"
    )
    for sub, count in by_sub_c.items():
        print(f"  {sub}: {count}")

    print(f"ambiguity bench: {len(ambiguous)} sentences -> {DATA_DIR / 'ambiguous_bench.jsonl'}")


if __name__ == "__main__":
    main()
