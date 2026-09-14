# AlphaTTSBench

A human-listening framework for evaluating what TTS systems read incorrectly
and which delivery listeners prefer for a particular use case.

## TL;DR

**AlphaTTSBench separates reading failures, support-call preference, and narration
preference into three tasks.** The repository provides corpora, listener
instructions, synthesis and collection scripts, and analysis tools. Use these to
design an evaluation for your application, or reproduce our published run.

Our US-English evaluation used five configured systems and specification 1.0.0,
frozen September 12, 2026. The main study contains **31,100 judgments**; a separate
AlphaBench development pilot adds 1,350, bringing the package to **17 evaluations
and 32,450 judgments**. SupportBench favored the tested Rime configuration over
all four competitors. ContentBench favored Rime over Cartesia and OpenAI, and
Deepgram and ElevenLabs over Rime. AlphaBench produced an annotated reading-failure
inventory. These are separate findings about the tested configurations, with no
combined score or overall winner. See the [results, intervals, and limitations](results/README.md).

Start with [the three tasks](#what-each-benchmark-does),
[reproduce the published results](results/README.md#files-and-reproduction), or
[design your own evaluation](#design-your-own-evaluation).
The [framework narrative](docs/framework-narrative.md) explains the development
history and the reasoning behind the design.

## Why separate the questions?

Imagine a support response that reads a tracking number smoothly but leaves out
one digit. The delivery may sound convincing, yet the customer has received the
wrong information. Now consider two correctly read versions of a story: both
convey the words, but you may prefer one voice's pacing and expression.

Reading-error annotations and preference scores answer different questions.
Preference also needs a context. For a support call, warmth, texture, and a
human-like delivery can matter alongside clarity. Requiring the correctly read
clip to win automatically would prescribe how listeners trade those qualities
against mistakes. SupportBench asks for their overall preference; AlphaBench
examines reading failures directly. The preference tasks do not separately
measure warmth, engagement, or whether someone stays on a call.

## Framework, run, and evidence

The framework supplies the evaluation tasks and methods. A run fixes the voices,
material, listeners, and settings used to answer a specific question. The
resulting evidence belongs to that run.

| Layer | What it establishes | Where to look |
|---|---|---|
| Framework | Questions, listener tasks, treatment of evidence, and interpretation | [Framework guide](docs/framework-narrative.md#what-each-benchmark-does) and [task definitions](configs/listener_tasks.json) |
| Run specification | Corpora, models, voices, audio settings, rating allocation, and analysis | [Published protocol](PROTOCOL.md), [frozen run guide](docs/frozen-run.md), and [run design](configs/run_design.json) |
| Run evidence | Listener judgments, file identities, reports, and limitations | [Export manifest](exports/manifest.csv) and [results](results/README.md) |

The published protocol and implementation contain choices specific to our run,
including Rime as the comparison baseline. Adapting the framework means recording
your own choices and checking which parts of the implementation need to change.

## What each benchmark does

| Benchmark | Listener task | Output |
|---|---|---|
| AlphaBench | Hear one clip, compare it with the displayed script, and annotate reading errors | Qualitative failure inventory with listener notes and clip references |
| SupportBench | Hear two versions of a response and choose which fits a customer-support call | Mean paired preference score, uncertainty, and paired tests |
| ContentBench | Hear two versions of a passage and choose which is preferable as narration | Mean paired preference score, uncertainty, and paired tests |

### AlphaBench: inspect what was read incorrectly

AlphaBench focuses on required content, especially identifiers and spelled
sequences. For a code such as `XQ47B`, every character must be conveyed clearly
and in order. Listeners flag omissions, substitutions, repetitions, early stops,
and other reading failures, then mark the affected text and describe what they
heard. Pauses or visual separators do not count as errors when the required
content remains intact.

The output helps locate and investigate failures. Flag counts are listener
support for reviewing examples, not validated provider error rates or rankings.
See the [corpus](data/alphabench.jsonl), [listener instructions](docs/rater-instructions-fidelity.md),
[accepted-reading examples](docs/normalization-cases.md), and
[qualitative report](results/alphabench/alphabench_qualitative.md).

### SupportBench: compare delivery for a support call

A response might be: "A supervisor has to sign off on the card replacement, but
that usually takes minutes, not days." Listeners hear two recordings intended
to convey the same response and answer:

> Which recording would you prefer to hear during a customer-support call?

They make one overall judgment on a five-point scale, including a tie. Clarity,
naturalness, and suitability can influence preference. Mistakes can matter,
but there is no automatic correctness-wins rule. This evaluates the spoken
response; evaluating an agent's problem resolution or interruption handling
requires additional conversational tests.

See the [corpus](data/supportbench.jsonl), [preference instructions](docs/rater-instructions-cmos.md),
and [report](results/supportbench/supportbench_report.md).

### ContentBench: compare delivery for narration

A passage might begin: "A Venus flytrap can count. The trap only snaps shut when
an insect touches two trigger hairs within about twenty seconds." Listeners
compare two recordings and answer:

> Which recording would you prefer for listening to this passage?

The judgment reflects delivery as a whole, including how easy the passage is
to follow and how its pacing and expression fit. The supplied material includes
literature excerpts and authored narration. These short passages do not establish
listening comfort over a full audiobook.

See the [corpus](data/contentbench.jsonl), [exact task definitions](configs/listener_tasks.json),
and [report](results/contentbench/contentbench_report.md).

## How the framework developed

We first checked whether the collection workflow worked, then separated the
evaluation questions and corrected input and measurement problems. Pilot work
informed corpus coverage and rating allocation before the listener tasks and
published specification were fixed.

| When, 2026 | What changed and why |
|---|---|
| August 6 | Small demos and reading-error pilots checked whether synthesis, collection, and annotations worked end to end. |
| August 7–8 | Separator tests exposed input problems, including a spoken "dash" between code characters. Provider rendering was refined to express the intended spoken content. |
| August 8 | Reading failures, support preference, and narration preference became separate tasks. |
| August 27 | Sampling decisions were fixed after the 90-script AlphaBench pilot and initial preference stages. AlphaBench expanded to 83 source templates; preference variability informed continuation rating counts. |
| September 9 | Revised listener instructions fixed qualitative AlphaBench reporting and overall contextual preference without an automatic correctness-wins rule. |
| September 12 | Specification 1.0.0 was frozen, the latest result-producing runs were conducted, and the specification, listener exports, and reports were published. |
| September 13 | Licensing, citation metadata, and release documentation were added. |

The separate AlphaBench pilot used six scripts from each of 15 source templates,
called *frames*, to examine whether related variants behaved similarly. That
informed broader coverage within the 580-script main corpus. The pilot remains
a development diagnostic and is excluded from the main results.

On August 9, a check against an earlier recorded evaluation caught an inverted
Deepgram preference direction in a pilot report. The report was corrected. That
lesson became an implementation check: analysis now determines score direction
from each item's target metadata, with an
[automated test](tests/test_analysis.py) covering that recoding. The
[development account](docs/framework-narrative.md#how-we-developed-the-framework)
explains these decisions and the sampling target in more detail.

## Our published evaluation

The September 12 run used Rime Coda, OpenAI gpt-4o-mini-tts, ElevenLabs Flash v2.5,
Cartesia Sonic-3, and Deepgram Aura-2. Exact voices and controls are recorded in
[provider settings](configs/provider_configs.json). Preference comparisons pair
Rime with each competitor; this is not an all-pairs tournament.

| Component | Scripts | Judgments per item or clip | Total judgments |
|---|---:|---|---:|
| AlphaBench development pilot, five providers | 90 | Three per clip | 1,350 |
| AlphaBench main, five providers | 580 | Three per clip | 8,700 |
| SupportBench: OpenAI, Deepgram, Cartesia comparisons | 750 each | Seven on the first 120 items; three on the remaining 630 | 8,190 |
| SupportBench: ElevenLabs comparison | 750 | Seven per pair | 5,250 |
| ContentBench: four comparisons | 400 each | Seven on the first 120 items; five on the remaining 280 | 8,960 |
| **Full package** | | **17 evaluations, including the separate pilot** | **32,450** |

We allocated seven judgments per item to the ElevenLabs comparison to estimate
that comparison more precisely. The corpus, task, item weighting, and
interpretation rules remained the same.

Ratings are averaged within each script, then scripts receive equal weight.
An item with seven ratings therefore does not outweigh one with three. Related
scripts are grouped into *source families*, such as variants of one template or
excerpts from one work. Family bootstrap intervals and paired sign-flip tests
account for that shared material. Holm correction covers four comparisons
separately within each preference benchmark. ContentBench also reports an
author/genre sensitivity analysis. Dependence between different scripts rated
by the same listener remains outside these intervals.

Read the [published results](results/README.md) for effect sizes, intervals,
qualitative evidence, and interpretation limits. Findings apply to the included
recordings, configurations, material, and listeners. An inconclusive comparison
does not establish equivalence.

## Design your own evaluation

1. **Choose the question and material.** Start with a task and representative
   scripts for your application. Prioritize distinct scenarios; retain related
   variants when they test a deliberate difference. Preserve item IDs and source
   families using the [corpus builder](corpus/build.py) and [generators](corpus/generators).
   More varied scripts broaden coverage; more ratings clarify preferences on
   the recordings you already have.
2. **Pilot, then freeze your choices.** Check provider input, audio, listener
   instructions, and exports on development material. Record models, voices,
   corpus hashes, listeners, audio handling, rating allocation, exclusions, and
   analysis before collecting result evidence. If a first stage informs later
   sampling, specify what it can change and whether its ratings enter the result.
   The [variance planner](scripts/plan_variance_tranche.py) implements our planning approach.
3. **Generate and collect.** Inspect how the [renderer](corpus/render.py) turns
   canonical content into provider-specific input. Review the rendered listener
   task before starting paid collection. Preserve manifests, settings, and raw
   judgments alongside the audio.
4. **Verify and interpret.** Confirm score orientation from target metadata and
   test a known example before analysis. Review the analyzer's Rime-oriented
   labels, four-comparison assumptions, and fixed corpus checks when adapting
   the design. Report uncertainty, deviations, and limits with the findings.

Use a separately versioned configuration and integrity checks for your study.
The [full reuse guide](docs/framework-narrative.md#build-your-own-evaluation)
connects these steps to the development lessons. To reproduce our study, follow
the fixed choices in the [run specification](docs/frozen-run.md).

## Verify the published specification

**Specification 1.0.0 · frozen September 12, 2026**

- [Protocol](PROTOCOL.md): tasks, scoring, uncertainty, and interpretation.
- [Run specification](docs/frozen-run.md): exact execution and validation rules.
- [Run design](configs/run_design.json): corpora and rating allocations.
- [Provider settings](configs/provider_configs.json): models, voices, and API controls.
- [Listener tasks](configs/listener_tasks.json): platform instructions and questions.
- [Freeze manifest](configs/freeze_manifest.json): hashes of specification, code, tests, and data.

The original specification is preserved at commit
[`77bff1a`](https://github.com/rimelabs/alpha-tts-benchmark/commit/77bff1a2f2d50025a807b17ec70e62983dcc5895).
Later explanatory documentation is identified in the [changelog](CHANGELOG.md)
and manifest; the Git commit identifies the complete snapshot. Verify the
checked-out files with:

```bash
uv sync --frozen
uv run python scripts/check_frozen_run.py
uv run python -m unittest discover -s tests -v
```

## Repository layout

```text
PROTOCOL.md     published benchmark protocol
configs/        provider settings, tasks, allocation, and freeze manifest
corpus/         deterministic corpus generators and rendering
data/           benchmark corpora and stage selections
docs/           framework narrative, run specification, and listener guidance
exports/        published listener exports and their hash manifest
results/        reports, structured results, and reproduction instructions
scripts/        synthesis, submission, analysis, and design utilities
tests/          implementation checks
```

Listener exports and result reports are included. Audio references are retained
in the exports; audio files are not bundled in this repository. See the
[release and licensing guide](RELEASE.md) for citation and reuse terms.

## Synthesis and submission for the published run

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

The published audio policy applies linear gain toward -23 LUFS, constrained by
a -1 dBTP ceiling, at 24 kHz. Podonos normalization is disabled. Use these audio
settings for every provider and follow the complete
[run specification](docs/frozen-run.md). The ElevenLabs CLI provider name is
`eleven`. Keep separate output roots for Alpha pilot, Alpha main, Support, and
Content, and share each root across its providers.

Submit Alpha with `submit_fidelity_podonos.py`, Support with
`submit_supportbench_podonos.py`, and Content with
`submit_contentbench_podonos.py`. Set `--num-eval` from the run design and use
`--language en-us`. Submission creates drafts by default; `--auto-start` starts
collection. Configure US listener recruitment in the platform.

## Analyze the published run

For the included exports, use the [complete reproduction commands](results/README.md#files-and-reproduction).
The commands below illustrate the individual analyzers.

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
