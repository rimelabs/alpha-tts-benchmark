# Alpha TTS Benchmark

A human-judged evaluation suite for US-English text-to-speech systems.

| Benchmark | Question | Output |
|---|---|---|
| AlphaBench | What reading failures occur on exact identifiers? | Qualitative failure taxonomy and supporting clips |
| SupportBench | Which recording would a listener prefer in a customer-support conversation? | Mean paired preference score |
| ContentBench | Which recording would a listener prefer for narration? | Mean paired preference score |

The suite covers five configured systems: Rime, OpenAI, ElevenLabs, Cartesia,
and Deepgram. AlphaBench contains 580 scripts, SupportBench 750, and
ContentBench 400. A separate Alpha pilot contains 90 scripts.

## Specification freeze

**Version 1.0.0 · September 12, 2026**

This freeze identifies the benchmark specification and analysis implementation.
Its date records when these repository contents were fixed.

- [Protocol](PROTOCOL.md): tasks, scoring, uncertainty, and interpretation.
- [Run specification](docs/frozen-run.md): 17 evaluations and 32,450 judgments.
- [Run design](configs/run_design.json): exact corpora and rating allocations.
- [Provider settings](configs/provider_configs.json): models, voices, and API controls.
- [Listener tasks](configs/listener_tasks.json): exact platform instructions and questions.
- [Freeze manifest](configs/freeze_manifest.json): SHA-256 hashes of specification, code, tests, and data.

The Git commit identifies the complete snapshot. Verify it locally with:

```bash
uv sync --frozen
uv run python scripts/check_frozen_run.py
uv run python -m unittest discover -s tests -v
```

## Method

Human listeners provide every primary judgment. Each provider receives the same
canonical spoken content, with provider-specific rendering where required.
Audio processing targets -23 LUFS with a -1 dBTP ceiling at 24 kHz; Podonos
normalization is disabled.

AlphaBench records reading failures, listener annotations, and supporting clips.
It does not estimate provider error rates or produce provider rankings.

SupportBench and ContentBench compare Rime with each competitor on a five-point
scale. Analysis averages ratings within each script, then weights scripts
equally. Source families define the bootstrap and paired sign-flip tests.
Holm correction covers four comparisons separately within each benchmark.
ContentBench also reports an author/genre sensitivity analysis. Shared-listener
dependence across scripts is outside these confidence intervals.

Results describe the evaluated configurations and scripts. An inconclusive
comparison does not establish equivalence. The protocol does not support a
combined score or overall winner across the three benchmarks.

## Repository layout

```text
PROTOCOL.md     benchmark protocol
configs/        provider settings, tasks, allocation, and freeze manifest
corpus/         deterministic corpus generators and rendering
data/          benchmark corpora and stage selections
docs/          run specification and reading guidance
scripts/       synthesis, submission, analysis, and design utilities
tests/         implementation checks
```

Audio, listener exports, and result reports are supplied separately. The
repository contains the specification and tools needed to produce and analyze
them.

## Synthesis and submission

Set the API keys for the providers being used: `RIME_API_KEY`, `OPENAI_API_KEY`,
`ELEVENLABS_API_KEY`, `CARTESIA_API_KEY`, and `DEEPGRAM_API_KEY`.
`PODONOS_API_KEY` is required for evaluation submission.

Example synthesis command:

```bash
uv run python scripts/synth_demo.py \
  --corpus data/supportbench.jsonl \
  --providers rime \
  --outdir out/support \
  --audio-mode level-matched \
  --sample-rate 24000 \
  --target-lufs -23 \
  --true-peak-db -1
```

Use the same settings for every provider and follow the complete
[run specification](docs/frozen-run.md). The ElevenLabs CLI provider name is
`eleven`. Keep separate output roots for Alpha pilot, Alpha main, Support, and
Content, and share each root across its providers.

Submit Alpha with `submit_fidelity_podonos.py`, Support with
`submit_supportbench_podonos.py`, and Content with
`submit_contentbench_podonos.py`. Set `--num-eval` from the run design and use
`--language en-us`. Submission creates drafts by default; `--auto-start` starts
collection. Configure US listener recruitment in the platform.

## Analysis

Load each evaluation once. Use all seven Support summary exports together and
all eight Content summary exports together. Keep individual-response files and
auxiliary copies out of those inputs. Individual responses support coverage and
distinct-listener checks.

```bash
uv run python scripts/analyze_comparison.py \
  --stats-json <all-summary-files-for-one-benchmark> \
  --benchmark SupportBench \
  --corpus data/supportbench.jsonl \
  --n-boot 10000 \
  --seed 20260825 \
  --outdir results/supportbench
```

For Content, use `--benchmark ContentBench`, `data/contentbench.jsonl`, and a
separate output directory. Replace the angle-bracket placeholder with explicit
summary file paths.

Analyze Alpha main separately:

```bash
uv run python scripts/analyze_alphabench_qualitative.py \
  --stats-json <alpha-main-model-summary> \
  --corpus data/alphabench.jsonl \
  --outdir results/alphabench
```

Review the generated Alpha inventory against its annotations and clips. Keep
task artifacts and ambiguous evidence separate from demonstrated reading
failures. The Alpha pilot remains a separate diagnostic.
