# Listener preference results

For the evaluated US-English scripts, voices, and listeners, SupportBench supports a mean paired preference for Rime over each of the four configured competitors. ContentBench supports a mean paired preference for Rime over Cartesia and OpenAI, and for Deepgram and ElevenLabs over Rime. These are separate benchmark results, not an overall provider ranking.

## Primary results

Scores run from -2 to +2. Positive differences favor Rime; negative differences favor the competitor. Each row compares Rime Coda with the clementine voice against the configuration named below. Exact voice IDs and API controls are in the [frozen provider settings](../configs/provider_configs.json).

On the five-point SupportBench scale, the mean paired Rime-minus-competitor differences were:

| Configured competitor | Scripts | Valid judgments | Mean difference | 95% interval | Holm-adjusted p |
|---|---:|---:|---:|---|---:|
| Cartesia Sonic-3, configured default voice | 750 | 2,730 | +0.2001 | [+0.1113, +0.2879] | 0.000020 |
| Deepgram Aura-2, thalia | 750 | 2,730 | +0.3681 | [+0.2852, +0.4490] | 0.000020 |
| ElevenLabs Flash v2.5, configured voice | 750 | 5,250 | +0.1217 | [+0.0513, +0.1973] | 0.000180 |
| OpenAI gpt-4o-mini-tts, coral | 750 | 2,730 | +0.9004 | [+0.8320, +0.9686] | 0.000020 |

On the five-point ContentBench scale, the mean paired Rime-minus-competitor differences were:

| Configured competitor | Scripts | Valid judgments | Mean difference | 95% interval | Holm-adjusted p |
|---|---:|---:|---:|---|---:|
| Cartesia Sonic-3, configured default voice | 400 | 2,240 | +0.2011 | [+0.1178, +0.2795] | 0.000020 |
| Deepgram Aura-2, thalia | 400 | 2,240 | -0.1535 | [-0.2290, -0.0763] | 0.000020 |
| ElevenLabs Flash v2.5, configured voice | 400 | 2,240 | -0.1641 | [-0.2566, -0.0715] | 0.000215 |
| OpenAI gpt-4o-mini-tts, coral | 400 | 2,240 | +0.3105 | [+0.2147, +0.4135] | 0.000020 |

All eight primary intervals exclude zero, and all eight Holm-adjusted tests support their respective directions. Holm correction applies separately to the four comparisons in each benchmark. Values in these tables are rounded; the JSON results retain full precision.

## Dependence and interpretation

Repeated judgments are averaged within each script, then scripts receive equal weight. The primary 95% intervals use a family bootstrap, and paired tests use family-level sign flips. SupportBench has 286 families with a Kish effective family count of 166.32. ContentBench has 223 families with a Kish effective family count of 80.73.

The ContentBench author/genre sensitivity has 24 clusters with a Kish effective count of 3.83. All four sensitivity intervals and Holm-adjusted tests support the same directions as the primary analysis. For OpenAI, the sensitivity interval is [+0.0058, +0.4413] with Holm-adjusted p = 0.019325. Its lower bound is close to zero, so the primary interval alone should not be used to describe certainty about the magnitude. The full sensitivity table is in the [ContentBench report](contentbench/contentbench_report.md).

These tasks measure one overall contextual preference judgment. They do not separately establish naturalness, prosody, acoustic fidelity, or engagement, or identify why a configuration received its scores. Results apply to the included scripts, configurations, and listeners. The intervals account for source-family dependence but do not model dependence between different items rated by the same listener. No perceptual size threshold or equivalence claim is used.

The generated reports also contain descriptive item win/tie/loss counts. Those are exploratory summaries of item means, not independent listener votes or provider rankings. AlphaBench is a separate qualitative task and does not enter these comparisons.

## Files and reproduction

- [SupportBench report](supportbench/supportbench_report.md) and [full-precision results](supportbench/supportbench_results.json).
- [ContentBench report](contentbench/contentbench_report.md) and [full-precision results](contentbench/contentbench_results.json).

Specification: [`77bff1a2f2d50025a807b17ec70e62983dcc5895`](https://github.com/rimelabs/alpha-tts-benchmark/commit/77bff1a2f2d50025a807b17ec70e62983dcc5895), protocol 1.0.0. Export snapshot: [`3b6526025fb5d7616f3bbd5ae13b506e1d7b73dc`](https://github.com/rimelabs/alpha-tts-benchmark/commit/3b6526025fb5d7616f3bbd5ae13b506e1d7b73dc). Input hashes are in [exports/manifest.csv](../exports/manifest.csv). The generated Markdown and JSON files are unchanged analyzer outputs.

Run from the repository root:

```bash
uv sync --frozen
uv run python scripts/check_frozen_run.py
uv run python - <<'PY'
import csv
import hashlib
import subprocess
import sys
from pathlib import Path

rows = list(csv.DictReader(Path('exports/manifest.csv').open()))
for row in rows:
    content = (Path('exports') / row['file']).read_bytes()
    assert hashlib.sha256(content).hexdigest() == row['sha256']
    assert len(content) == int(row['bytes'])

for benchmark, label, expected in [
    ('supportbench', 'SupportBench', 7),
    ('contentbench', 'ContentBench', 8),
]:
    inputs = [
        str(Path('exports') / row['file'])
        for row in rows
        if row['file'].startswith(benchmark + '/')
        and 'individual-responses' not in row['file']
    ]
    assert len(inputs) == expected
    subprocess.run([
        sys.executable, 'scripts/analyze_comparison.py',
        '--stats-json', *inputs,
        '--benchmark', label,
        '--corpus', f'data/{benchmark}.jsonl',
        '--n-boot', '10000', '--seed', '20260825',
        '--outdir', f'results/{benchmark}',
    ], check=True)
PY
```

Load each summary once. Individual-response files verify coverage and distinct-listener counts; they are not additional analysis inputs. Follow the [frozen protocol](../PROTOCOL.md) for interpretation.
