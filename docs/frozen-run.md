# Benchmark run specification — 1.0.0

Specification freeze: September 12, 2026.

This document fixes the corpus selections, provider settings, listener tasks,
rating allocation, and analysis for the benchmark. Collection records and
result artifacts identify the data associated with an evaluation.

## Rating allocation

| Benchmark / stage | Comparisons or providers | Scripts | Ratings per pair or clip | Total ratings |
|---|---|---:|---:|---:|
| Alpha pilot | All five providers | 90 | 3 | 1,350 |
| Alpha main | All five providers | 580 | 3 | 8,700 |
| Support tranche | Rime vs OpenAI, Deepgram, Cartesia | 120 each | 7 | 2,520 |
| Support continuation | Same three comparisons | 630 each | 3 | 5,670 |
| Support full | Rime vs ElevenLabs | 750 | 7 | 5,250 |
| Content tranche | All four comparisons against Rime | 120 each | 7 | 3,360 |
| Content continuation | Same four comparisons | 280 each | 5 | 5,600 |
| **Total** | **17 evaluations** | | | **32,450** |

[run_design.json](../configs/run_design.json) names every evaluation and its
exact corpus file. Preference tranche and continuation selections are disjoint
and exhaust the full corpus. Use those selections without resampling or
filtering. The ambiguity set and other small pilot corpora are outside this
allocation. Alpha pilot and main use separate texts, identifiers, and audio;
never pool their results.

The rating counts are fixed. Pilot and tranche diagnostics do not change the
main task, prompts, voices, allocation, or analysis.

## Audio

Use [provider_configs.json](../configs/provider_configs.json) and the checked-in
rendering implementation. The configuration fixes requested model identifiers,
voice IDs, ElevenLabs controls, Cartesia API version, and 24 kHz output. Service
model identifiers do not pin internal provider weights.

Use these synthesis options for every provider:

```text
--audio-mode level-matched --sample-rate 24000 --target-lufs -23 --true-peak-db -1
```

Processing applies linear gain toward -23 LUFS, constrained by a -1 dBTP
true-peak ceiling, and produces mono 16-bit WAV. Measurement safety margins are
part of the implementation. Peak-constrained clips may remain below the
loudness target; processing does not apply dynamic compression to force equal
loudness. Podonos normalization is disabled.

Retain the first technically valid response under the synthesis script's
transport and invalid-audio retry rules. Do not regenerate valid clips based
on pronunciation or preference. Resolve technical failures with the same
settings. Resume only verified audio matching the requested configuration.

Generate the full Support and Content corpus for each provider, then select
manifest rows for the allocated stages. Reuse the Rime clip for each item
across its four comparisons. Keep Alpha pilot, Alpha main, Support, and Content
in separate output roots, each shared across its five providers.

## Listeners and tasks

Recruit US listeners and use `en-us`. Use exactly
[listener_tasks.json](../configs/listener_tasks.json). Each item/clip receives
its allocated number of distinct listeners; a listener may rate multiple
items. Canonical target A/B metadata determines score direction. It does not
establish a presentation-randomization policy.

## Execution

1. Install dependencies with `uv sync --frozen` and verify the specification
   with `uv run python scripts/check_frozen_run.py`.
2. Synthesize each corpus for all five providers with the fixed audio options
   and provider defaults. The ElevenLabs CLI provider name is `eleven`.
3. Select manifests using each job's exact corpus IDs. Preserve canonical text,
   model tags, and audio references. Alpha submission receives all five
   provider manifests; each preference job receives Rime and one competitor.
4. Submit using the benchmark's submission script, the allocated `--num-eval`,
   and `--language en-us`. Use an evaluation name and upload state for each job.
   Configure US listener recruitment before starting collection.

The general-purpose scripts also expose settings for other experiments. Those
options do not alter this specification.

## Data validation

A complete package contains all 17 evaluations, every allocated item/provider
pair, matching canonical text, and exactly the required number of distinct
valid listeners per item/clip. Compare coverage with `run_design.json`; totals
alone are insufficient.

Resolve missing ratings without selecting responses by score. Document any
excess or invalid responses and their treatment. Preserve the complete raw
exports and identify deviations instead of silently dropping prompts or votes.

Keep audio manifests, provider settings, processing metadata, and collection
records with the evaluation artifacts. Exported model tags and audio paths
alone do not verify the underlying configuration or audio processing.

## Analysis

Load each evaluation once. Analyze all seven Support summary files together and
all eight Content summary files together. Individual-response exports support
listener and count checks; auxiliary copies are not additional evaluations.
Analyze only Alpha main in the main qualitative report.

Use `analyze_comparison.py` with the full benchmark corpus,
`--n-boot 10000 --seed 20260825`. Average ratings within each item and weight
items equally across stages. The additional ElevenLabs Support ratings affect
within-item precision, not item weight.

Retain the family bootstrap, family sign-flip tests, separate four-comparison
Holm corrections, and Content author/genre sensitivity in
[PROTOCOL.md](../PROTOCOL.md). Shared-listener dependence across items remains
outside these intervals.

Use `analyze_alphabench_qualitative.py` for Alpha main. Its output is a failure
inventory with listener support and annotations. Review clips before treating
unclear labels or task/input artifacts as provider failures. AlphaBench does
not produce provider error rates or rankings.

## Freeze identity

[freeze_manifest.json](../configs/freeze_manifest.json) records SHA-256 hashes
for the specification, configuration, corpora, implementation, and tests. The
manifest excludes itself; the Git commit identifies the complete snapshot.
Verify the hashes before analysis. Changes to pinned files create a different
specification snapshot.
