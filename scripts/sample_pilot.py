"""Sample 5% of each corpus (stratified by subcategory) for a pilot run.

Usage:

    uv run python scripts/sample_pilot.py

Writes data/pilot_alphabench.jsonl, data/pilot_supportbench.jsonl,
and data/pilot_contentbench.jsonl. Deterministic (seeded).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 20260808
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FRACTION = 0.05  # of each subcategory, rounded, at least 1


def sample(rows: list[dict], fraction: float, seed: str) -> list[dict]:
    by_sub: dict[str, list[dict]] = {}
    for r in rows:
        by_sub.setdefault(r["subcategory"], []).append(r)
    out = []
    for sub in sorted(by_sub):
        rng = random.Random(f"{seed}-{sub}")
        pool = by_sub[sub]
        k = max(1, round(fraction * len(pool)))
        out.extend(rng.sample(pool, k))
    out.sort(key=lambda r: r["id"])
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def print_summary(name: str, rows: list[dict]) -> None:
    by_sub: dict[str, int] = {}
    for r in rows:
        by_sub[r["subcategory"]] = by_sub.get(r["subcategory"], 0) + 1
    print(f"{name}: {len(rows)} sentences")
    for sub, n in sorted(by_sub.items()):
        print(f"  {sub}: {n}")


def main() -> None:
    alpha = [json.loads(l) for l in (DATA_DIR / "alphabench.jsonl").open()]
    support = [json.loads(l) for l in (DATA_DIR / "supportbench.jsonl").open()]
    content = [json.loads(l) for l in (DATA_DIR / "contentbench.jsonl").open()]

    pilot_alpha = sample(alpha, FRACTION, f"{SEED}-alpha")
    pilot_support = sample(support, FRACTION, f"{SEED}-support")
    pilot_content = sample(content, FRACTION, f"{SEED}-content")

    write_jsonl(DATA_DIR / "pilot_alphabench.jsonl", pilot_alpha)
    write_jsonl(DATA_DIR / "pilot_supportbench.jsonl", pilot_support)
    write_jsonl(DATA_DIR / "pilot_contentbench.jsonl", pilot_content)

    print_summary("pilot_alphabench", pilot_alpha)
    print_summary("pilot_supportbench", pilot_support)
    print_summary("pilot_contentbench", pilot_content)


if __name__ == "__main__":
    main()
