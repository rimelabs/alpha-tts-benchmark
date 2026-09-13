"""Validate the AlphaBench development sample and create preference tranches.

The AlphaBench pilot selects 15 source frames across every subcategory and
the observed frame-size range, then samples six scripts per frame. The
SupportBench and ContentBench tranches each contain 120 scripts sampled
within their subcategory mix. All selections are deterministic.
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
SEED = 20260826
ALPHA_FRAMES = 15
ALPHA_ITEMS_PER_FRAME = 6
PREFERENCE_TRANCHE_ITEMS = 120


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def select_alpha_icc_pilot(
    rows: list[dict[str, Any]],
    *,
    seed: int = SEED,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["subcategory"], row["family_id"])].append(row)
    eligible = [
        {
            "subcategory": subcategory,
            "family_id": family_id,
            "rows": sorted(items, key=lambda row: row["id"]),
            "size": len(items),
        }
        for (subcategory, family_id), items in grouped.items()
        if len(items) >= ALPHA_ITEMS_PER_FRAME
    ]
    by_subcategory: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for family in eligible:
        by_subcategory[family["subcategory"]].append(family)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for subcategory in sorted(by_subcategory):
        candidates = sorted(
            by_subcategory[subcategory],
            key=lambda family: (family["size"], family["family_id"]),
        )
        median = candidates[len(candidates) // 2]
        selected.append(median)
        selected_ids.add(median["family_id"])

    remaining = [
        family for family in eligible if family["family_id"] not in selected_ids
    ]
    low = sorted(remaining, key=lambda family: (family["size"], family["family_id"]))
    high = list(reversed(low))
    for candidates in (high, low, high, low, high, low):
        choice = next(
            family
            for family in candidates
            if family["family_id"] not in selected_ids
        )
        selected.append(choice)
        selected_ids.add(choice["family_id"])
    if len(selected) != ALPHA_FRAMES:
        raise ValueError(f"expected {ALPHA_FRAMES} frames, found {len(selected)}")

    sampled: list[dict[str, Any]] = []
    for family in sorted(selected, key=lambda value: value["family_id"]):
        rng = random.Random(f"{seed}-alpha-{family['family_id']}")
        sampled.extend(rng.sample(family["rows"], ALPHA_ITEMS_PER_FRAME))
    sampled.sort(key=lambda row: row["id"])
    return sampled


def _largest_remainder_quotas(
    counts: Counter[str],
    total: int,
) -> dict[str, int]:
    population = sum(counts.values())
    exact = {
        name: total * count / population for name, count in counts.items()
    }
    quotas = {name: math.floor(value) for name, value in exact.items()}
    for name in sorted(
        counts,
        key=lambda value: (exact[value] - quotas[value], value),
        reverse=True,
    )[: total - sum(quotas.values())]:
        quotas[name] += 1
    return quotas


def select_preference_tranche(
    rows: list[dict[str, Any]],
    *,
    benchmark: str,
    seed: int = SEED,
    total: int = PREFERENCE_TRANCHE_ITEMS,
) -> list[dict[str, Any]]:
    counts = Counter(row["subcategory"] for row in rows)
    quotas = _largest_remainder_quotas(counts, total)
    sampled: list[dict[str, Any]] = []
    for subcategory in sorted(quotas):
        pool = [row for row in rows if row["subcategory"] == subcategory]
        rng = random.Random(f"{seed}-{benchmark}-{subcategory}")
        sampled.extend(rng.sample(pool, quotas[subcategory]))
    sampled.sort(key=lambda row: row["id"])
    if len(sampled) != total:
        raise ValueError(f"expected {total} {benchmark} items, found {len(sampled)}")
    return sampled


def summary(name: str, rows: list[dict[str, Any]]) -> str:
    subcategories = Counter(row["subcategory"] for row in rows)
    families = Counter(row["family_id"] for row in rows)
    repeated = sum(count > 1 for count in families.values())
    details = ", ".join(
        f"{subcategory}={count}"
        for subcategory, count in sorted(subcategories.items())
    )
    return (
        f"{name}: {len(rows)} items, {len(families)} families, "
        f"{repeated} repeated families; {details}"
    )


def main() -> None:
    support = read_jsonl(DATA_DIR / "supportbench.jsonl")
    content = read_jsonl(DATA_DIR / "contentbench.jsonl")

    alpha_pilot = read_jsonl(DATA_DIR / "pilot_alphabench_icc.jsonl")
    alpha_families = Counter(row["family_id"] for row in alpha_pilot)
    if (
        len(alpha_pilot) != 90
        or len(alpha_families) != 15
        or set(alpha_families.values()) != {6}
    ):
        raise ValueError("the AlphaBench development sample is invalid")
    support_tranche = select_preference_tranche(
        support,
        benchmark="supportbench",
    )
    content_tranche = select_preference_tranche(
        content,
        benchmark="contentbench",
    )

    write_jsonl(DATA_DIR / "tranche_supportbench.jsonl", support_tranche)
    write_jsonl(DATA_DIR / "tranche_contentbench.jsonl", content_tranche)
    support_tranche_ids = {row["id"] for row in support_tranche}
    content_tranche_ids = {row["id"] for row in content_tranche}
    write_jsonl(
        DATA_DIR / "continuation_supportbench.jsonl",
        [row for row in support if row["id"] not in support_tranche_ids],
    )
    write_jsonl(
        DATA_DIR / "continuation_contentbench.jsonl",
        [row for row in content if row["id"] not in content_tranche_ids],
    )

    print(summary("AlphaBench ICC pilot", alpha_pilot))
    print(summary("SupportBench variance tranche", support_tranche))
    print(summary("ContentBench variance tranche", content_tranche))


if __name__ == "__main__":
    main()
