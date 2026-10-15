# TTSBench

**Human-listener benchmarks for text-to-speech, organized around the job a voice
has to do.**

TTSBench asks listeners three separate questions. Did the voice read the
required content correctly? Which recording would they rather hear on a
customer-support call? Which would they rather hear for narration? This
repository holds everything behind the published run: corpora, listener tasks,
provider settings, synthesis and collection scripts, analysis code,
judgment-level listener exports, and reports. You can check every number below
or run the same study on your own voices.

TTSBench was first released as AlphaTTSBench with specification 1.0.0 in
September 2026. Only the name has changed.

[Results page](https://www.rime.ai/research/tts-benchmarks) · [Launch post](https://www.rime.ai/resources/a-better-set-of-benchmarks-for-text-to-speech) · [Full results](results/README.md) · [Framework narrative](docs/framework-narrative.md)

## At a glance

- **Three tests:** AlphaBench (reading accuracy on codes, IDs, numbers, and
  spellings), SupportBench (support-call preference), and ContentBench
  (narration preference). Each keeps its own result. There is no combined score.
- **Five configured systems:** Rime Coda with clementine, Cartesia Sonic-3,
  Deepgram Aura-2 with thalia, ElevenLabs Flash v2.5, and OpenAI gpt-4o-mini-tts
  with coral. Exact voices and controls are in [provider
  settings](configs/provider_configs.json).
- **Material:** 1,730 US-English scripts: 580 for AlphaBench, 750 for
  SupportBench, and 400 for ContentBench.
- **Listeners and judgments:** US listeners recruited through Podonos made
  31,100 judgments in the main study. A separate 1,350-judgment AlphaBench pilot
  brings the package to 17 evaluations and 32,450 judgments.
- **Specification:** 1.0.0, frozen September 12, 2026.
  `scripts/check_frozen_run.py` verifies the frozen files against their hashes.

## Key findings

Each preference comparison pairs Rime Coda with one competitor on the same
scripts. Scores are Rime minus competitor on a scale from -2 to +2, averaged per
script, so positive values favor Rime.

| Rime Coda vs | SupportBench (support calls) | ContentBench (narration) |
|---|---|---|
| OpenAI gpt-4o-mini-tts | **+0.90** [+0.83, +0.97] | **+0.31** [+0.21, +0.41] |
| Deepgram Aura-2 | **+0.37** [+0.29, +0.45] | **-0.15** [-0.23, -0.08] |
| Cartesia Sonic-3 | **+0.20** [+0.11, +0.29] | **+0.20** [+0.12, +0.28] |
| ElevenLabs Flash v2.5 | **+0.12** [+0.05, +0.20] | **-0.16** [-0.26, -0.07] |

Brackets are 95% family-bootstrap intervals. All eight directions meet the
benchmark's bar: the interval excludes zero and the Holm-adjusted p-value is
0.05 or lower. Full-precision values are in the [results](results/README.md).

- **Support calls:** listeners preferred Rime over all four configured
  competitors.
- **Narration:** listeners preferred Rime over OpenAI and Cartesia, and
  preferred Deepgram and ElevenLabs over Rime.
- **Reading accuracy:** AlphaBench produced an inventory of clips that listeners
  flagged for review.

| System | Clips flagged by at least one listener | By a majority (2 of 3) | By all three |
|---|---:|---:|---:|
| Deepgram Aura-2 | 133 | 84 | 42 |
| OpenAI gpt-4o-mini-tts | 54 | 16 | 3 |
| Rime Coda | 45 | 10 | 3 |
| Cartesia Sonic-3 | 64 | 9 | 3 |
| ElevenLabs Flash v2.5 | 39 | 6 | 0 |

Each system read the same 580 scripts. Omissions (40 clips) and early stops (30
clips) were the most common labels on flagged Deepgram clips. In one, the
spelling W-H-I-T-T-A-K-E-R drew unanimous early-stop and omission flags. Rime
has failures in the inventory too: a reading of the confirmation code CCC666CQIT
drew unanimous omission flags. These counts point reviewers at clips worth
hearing. They are not adjudicated error rates, and they are not a ranking. See
the [qualitative report](results/alphabench/alphabench_qualitative.md).

## What makes TTSBench different

1. **Accuracy and preference are separate tests.** A voice can deliver a line
   warmly and still drop a character. AlphaBench asks only whether the required
   content arrived intact. SupportBench asks which recording a listener would
   rather hear, without telling them that the correct one must win, so the
   trade-off stays visible instead of being decided for them.
2. **There is no combined score or overall winner.** The published run shows
   why. The same system can lead on support calls and trail on narration.
3. **The losses are published.** Rime built this benchmark, and Rime Coda is one
   of the systems it tests. The narration results that go against Rime sit next
   to the support results.
4. **The statistics account for related scripts.** Scripts built from one
   template are grouped into families, and intervals resample whole families.
   Each script gets one vote however many ratings it received. Holm correction
   covers the four comparisons in each preference benchmark.
5. **Everything needed to check or rerun it is here.** Corpora, listener
   questions, provider settings, rating allocations, judgment-level listener
   exports, analysis code, and reports are in this repository, with a hash
   manifest for the frozen files.

## Takeaways for builders

- **Choose a voice for the job.** A preference result on support calls says
  little about narration, and the reverse.
- **Test reading accuracy on its own.** Codes, spellings, and numbers fail in
  ways an overall preference score can hide.
- **Read the size and the interval, not only the direction.** +0.12 on a
  five-point scale is a reliable lean, not a landslide.
- **Run it on your own material.** Your voices, scripts, and listeners can give
  a different answer. The framework is built to be adapted.

## Learn how TTSBench works

This part is for anyone new to listening tests or planning their own. It covers
the reasoning behind each test, how the statistics work, how the published run
was built, and how to adapt it. Read it in order or jump to a section:

1. [Why separate the questions?](#why-separate-the-questions)
2. [Framework, run, and evidence](#framework-run-and-evidence)
3. [What each benchmark does](#what-each-benchmark-does)
4. [How the statistics work](#how-the-statistics-work)
5. [Our published evaluation](#our-published-evaluation)
6. [How the framework developed](#how-the-framework-developed)
7. [Design your own evaluation](#design-your-own-evaluation)
8. [Verify, reproduce, and analyze the published
   run](#verify-the-published-specification)

## Why separate the questions?

Imagine a support response that reads a tracking number smoothly but leaves out
one digit. The delivery may sound convincing, yet the customer has received the
wrong information. Now consider two correctly read versions of a story: both
convey the words, but you may prefer one voice's pacing and expression.

Reading-error annotations and preference scores answer different questions.
Preference also needs a context. For a support call, warmth, texture, and a
human-like delivery can matter alongside clarity. Requiring the correctly read
clip to win automatically would prescribe how listeners trade those qualities
against mistakes. SupportBench asks for their overall preference, and AlphaBench
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
including Rime as the comparison baseline. Adapting the framework means
recording your own choices and checking which parts of the implementation need
to change.

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
See the [corpus](data/alphabench.jsonl), [listener
instructions](docs/rater-instructions-fidelity.md), [accepted-reading
examples](docs/normalization-cases.md), and [qualitative
report](results/alphabench/alphabench_qualitative.md).

### SupportBench: compare delivery for a support call

A response might be: "A supervisor has to sign off on the card replacement, but
that usually takes minutes, not days." Listeners hear two recordings intended to
convey the same response and answer:

> Which recording would you prefer to hear during a customer-support call?

They make one overall judgment on a five-point scale, including a tie. Clarity,
naturalness, and suitability can influence preference. Mistakes can matter, but
there is no automatic correctness-wins rule. This evaluates the spoken response.
Evaluating an agent's problem resolution or interruption handling requires
additional conversational tests.

See the [corpus](data/supportbench.jsonl), [preference
instructions](docs/rater-instructions-cmos.md), and
[report](results/supportbench/supportbench_report.md).

### ContentBench: compare delivery for narration

A passage might begin: "A Venus flytrap can count. The trap only snaps shut when
an insect touches two trigger hairs within about twenty seconds." Listeners
compare two recordings and answer:

> Which recording would you prefer for listening to this passage?

The judgment reflects delivery as a whole, including how easy the passage is to
follow and how its pacing and expression fit. The supplied material includes
literature excerpts and authored narration. These short passages do not
establish listening comfort over a full audiobook.

See the [corpus](data/contentbench.jsonl), [exact task
definitions](configs/listener_tasks.json), and
[report](results/contentbench/contentbench_report.md).

## How the statistics work

A preference number is only useful if you know how much to believe it. Five
ideas carry most of the weight.

**One vote per script.** Some scripts received seven ratings and others three or
five. Ratings are averaged within each script first, then every script carries
equal weight. A heavily rated script cannot outvote a lightly rated one.

**Script families.** Suppose three scripts all begin "Your confirmation code
is..." and differ only in the code. That is three recordings, but they may share
one weakness, since a voice that rushes that sentence probably rushes all three.
Treating them as independent would overstate the evidence. Every script belongs
to a source family: variants of one template, or excerpts from one work.
SupportBench has 286 families and ContentBench has 223. Uncertainty is estimated
by resampling whole families.

**Intervals, tests, and four comparisons at once.** For each comparison, the 95%
interval comes from a family bootstrap with 10,000 replicates, and the paired
test is a family-level sign-flip test. Each preference benchmark makes four
comparisons, and Holm correction adjusts those four tests together. Without it,
every extra comparison would raise the chance of a false "win." A direction
counts as supported only when the interval excludes zero and the Holm-adjusted
p-value is 0.05 or lower.

**Planned rating counts.** Each preference comparison began with a first stage
of 120 scripts rated seven times. That stage's variability set how many more
ratings the remaining scripts needed. The target was an 80% chance of detecting
a 0.15-point difference on the five-point scale under the model, adjusted for
four comparisons. Three more ratings per script met the target for SupportBench,
and ContentBench needed five. The [variance
planner](scripts/plan_variance_tranche.py) implements this approach.

**A coarser check.** ContentBench was also analyzed with broader groups:
literature by author and other passages by genre. All four directions stay
supported. The check also shows where to be careful. For OpenAI, the interval
under the coarser grouping is [+0.0058, +0.4413], with a Holm-adjusted p-value
of 0.019. The direction holds, but the size of that gap is uncertain.

What the intervals do not cover: dependence between different scripts rated by
the same listener. No perceptual size threshold or equivalence claim is used,
and an inconclusive comparison would not establish equivalence. The
[results](results/README.md#dependence-and-interpretation) give the full
interpretation rules.

## Our published evaluation

The September 12 run used Rime Coda, OpenAI gpt-4o-mini-tts, ElevenLabs Flash
v2.5, Cartesia Sonic-3, and Deepgram Aura-2. Exact voices and controls are
recorded in [provider settings](configs/provider_configs.json). Preference
comparisons pair Rime with each competitor. This is not an all-pairs tournament.

| Component | Scripts | Judgments per item or clip | Total judgments |
|---|---:|---|---:|
| AlphaBench development pilot, five providers | 90 | Three per clip | 1,350 |
| AlphaBench main, five providers | 580 | Three per clip | 8,700 |
| SupportBench: OpenAI, Deepgram, Cartesia comparisons | 750 each | Seven on the first 120 items, three on the remaining 630 | 8,190 |
| SupportBench: ElevenLabs comparison | 750 | Seven per pair | 5,250 |
| ContentBench: four comparisons | 400 each | Seven on the first 120 items, five on the remaining 280 | 8,960 |
| **Full package** | | **17 evaluations, including the separate pilot** | **32,450** |

We allocated seven judgments per item to the ElevenLabs comparison to estimate
that comparison more precisely. The corpus, task, item weighting, and
interpretation rules remained the same.

Audio for every provider was level-matched toward -23 LUFS under a -1 dBTP
ceiling at 24 kHz, with Podonos normalization disabled. Findings apply to the
included recordings, configurations, material, and listeners. Read the
[published results](results/README.md) for effect sizes, intervals, qualitative
evidence, and interpretation limits.

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
| August 27 | Sampling decisions were fixed after the 90-script AlphaBench pilot and initial preference stages. AlphaBench expanded to 83 source templates, and preference variability informed continuation rating counts. |
| September 9 | Revised listener instructions fixed qualitative AlphaBench reporting and overall contextual preference without an automatic correctness-wins rule. |
| September 12 | Specification 1.0.0 was frozen, the latest result-producing runs were conducted, and the specification, listener exports, and reports were published. |
| September 13 | Licensing, citation metadata, and release documentation were added. |

Three lessons from that work carry over to any listening study:

- **Provider input can create the error.** An early separator test produced a
  spoken "dash" between the characters of a code. That was the notation leaking
  into the audio, not a reading failure. Mixed codes now go to providers as
  comma-separated characters, which keeps the intended content distinct from the
  notation.
- **A sign can flip silently.** On August 9, a check against an earlier recorded
  evaluation caught an inverted Deepgram preference direction in a pilot report.
  The analysis now determines score direction from each item's target metadata,
  with an [automated test](tests/test_analysis.py) covering that recoding.
- **More variants are not more coverage.** The AlphaBench pilot used six scripts
  from each of 15 source templates, called *frames*, to examine whether related
  variants behaved similarly. That informed spreading the 580-script main corpus
  across 83 frames. The pilot remains a development diagnostic and is excluded
  from the main results.

The [development
account](docs/framework-narrative.md#how-we-developed-the-framework) explains
these decisions and the sampling target in more detail.

## Design your own evaluation

1. **Choose the question and material.** Start with a task and representative
   scripts for your application. Prioritize distinct scenarios, and retain related
   variants when they test a deliberate difference. Preserve item IDs and source
   families using the [corpus builder](corpus/build.py) and
[generators](corpus/generators).
   More varied scripts broaden coverage. More ratings clarify preferences on
   the recordings you already have.
2. **Pilot, then freeze your choices.** Check provider input, audio, listener
   instructions, and exports on development material. Record models, voices,
   corpus hashes, listeners, audio handling, rating allocation, exclusions, and
   analysis before collecting result evidence. If a first stage informs later
   sampling, specify what it can change and whether its ratings enter the
result.
   The [variance planner](scripts/plan_variance_tranche.py) implements our
planning approach.
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
- [Provider settings](configs/provider_configs.json): models, voices, and API
  controls.
- [Listener tasks](configs/listener_tasks.json): platform instructions and
  questions.
- [Freeze manifest](configs/freeze_manifest.json): hashes of specification,
  code, tests, and data.

The original specification is preserved at commit
[`77bff1a`](https://github.com/rimelabs/alpha-tts-benchmark/commit/77bff1a2f2d50025a807b17ec70e62983dcc5895).
Later explanatory documentation is identified in the [changelog](CHANGELOG.md)
and manifest. The Git commit identifies the complete snapshot. Verify the
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
in the exports. Audio files are not bundled in this repository. See the
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
`--language en-us`. Submission creates drafts by default, and `--auto-start` starts
collection. Configure US listener recruitment in the platform.

## Analyze the published run

For the included exports, use the [complete reproduction
commands](results/README.md#files-and-reproduction).
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

## Citation and license

Cite this work with [CITATION.cff](CITATION.cff). Original software is licensed
under the MIT License. Rime-authored corpus text, benchmark definitions,
numerical results, and the dataset compilation are licensed under CC BY 4.0.
Listener-authored notes, provider audio, and third-party material are excluded
from both grants. [LICENSING.md](LICENSING.md) gives the exact scope, and the
[release guide](RELEASE.md) covers reuse.
