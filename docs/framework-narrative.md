# AlphaTTSBench

## TL;DR

**AlphaTTSBench is a human-listening framework for evaluating whether TTS systems
read required content correctly and how listeners prefer their delivery in
different contexts.** It contains three complementary tests: **AlphaBench**
documents reading failures, **SupportBench** measures customer-support
preference, and **ContentBench** measures narration preference. Each produces
its own evidence; there is no combined quality score or overall winner.

The repository provides the corpora, listener questions, provider-input handling,
synthesis and collection scripts, and analysis needed to build an evaluation.
A run fixes the particular models, voices, material, listeners, and rating
allocation. Those choices belong to that run, rather than defining what every
user of the framework must test.

Our published evaluation uses five configured systems and specification **1.0.0,
frozen September 12, 2026**. Its package contains **17 evaluations and 32,450
judgments**, including a separate AlphaBench development pilot. On the tested
US-English material, SupportBench favored Rime over the four configured
competitors. ContentBench favored Rime over Cartesia and OpenAI, and Deepgram
and ElevenLabs over Rime. AlphaBench's review inventory contains 84 Deepgram clips
flagged by a majority of listeners, compared with 6–16 for each other configuration;
omissions and early stops feature prominently in its annotations. These are
listener flags for review, not validated provider error rates. The [reports](../results/README.md)
include uncertainty and limits; the findings describe the evaluated configurations,
not every voice offered by those providers.

Use the [published run and reproduction guide](../results/README.md) as a worked example,
or adapt the framework to your own voices and material with a separately recorded
configuration and freeze.

## Why evaluate TTS this way?

Imagine a support response that reads a tracking number smoothly but leaves out
one digit. The delivery may sound convincing, yet the customer has received the
wrong information. Now consider two correctly read versions of a story: both
convey the words, but you may prefer one voice's pacing and expression.

These are different evaluation questions. A preference score alone does not tell
us which content was misread. A reading-error annotation does not tell us which
recording someone would choose to listen to. Even preference needs a context:
what works for a short support response may not work as well for narration.

For support calls, there is another part of the experience we wanted to
understand: the warmth, texture, intimacy, and human-like pleasantness that make
a voice comfortable to listen to. If we tell evaluators that the correctly read
recording must always win, we prescribe how they should trade those qualities
against reading accuracy. Their answers may then reveal less about the delivery
they would otherwise choose for that conversation.

Keeping the questions separate proved useful in developing the framework.
AlphaBench asks directly about reading failures. SupportBench lets listeners judge the
delivery as a whole, including any mistakes they notice, without imposing a
correctness-first decision. Warmth and the desire to keep listening motivate the
question; the task does not separately measure those qualities or whether a
customer stays on a call.

AlphaTTSBench gives each question its own task so the evidence can inform a
specific decision: investigate a reading failure, compare delivery for an
application, or identify what needs further testing.

## Start with the framework, then define a run

Think of the framework as the method you use to ask the question. The run is the
specific experiment you conduct with it.


| Layer             | What it establishes                                                                         | Where to look                                                                                                                                                                                        |
| ----------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Framework         | Evaluation questions, listener tasks, treatment of evidence, and interpretation             | [Protocol](../PROTOCOL.md) and [task definitions](../configs/listener_tasks.json)      |
| Run specification | Corpora, models, voices, audio settings, listeners, rating allocation, and analysis version | [Frozen run guide](../docs/frozen-run.md) and [run design](../configs/run_design.json) |
| Run evidence      | Collected judgments, file identities, analysis outputs, and limitations                     | [Export manifest](../exports/manifest.csv) and [results](../results/README.md)         |


For example, you could use the SupportBench approach to compare two voices for
your own support application. You would still need to choose representative
responses, specify which voices and settings to test, decide how many listeners
to recruit, and fix the analysis before inspecting the results. Those decisions
create your evaluation; they do not inherit the conclusions of ours.

The checked-in implementation includes assumptions specific to the published
run. Reuse its methods and code with those assumptions in view, particularly
when changing the baseline, number of comparisons, or corpus structure.

## What each benchmark does



### AlphaBench: inspect what was read incorrectly

AlphaBench focuses on required content, especially identifiers and spelled
sequences where a single missing character matters. A listener sees the complete
script, hears one recording, flags a reading error, and annotates the affected
text with what they heard.

The supplied material includes confirmation codes, order and tracking numbers,
flight numbers, license plates, policy identifiers, long codes, confusable
sequences, and name spellings. For a code such as `XQ47B`, the question is whether
the required sequence is conveyed correctly and unambiguously. Pauses or visual
separators should not create an error when the content is intact.

The result is a **qualitative failure inventory**: omissions, substitutions,
repetitions, insertions, reordering, early stops, and ambiguous readings, linked
to listener evidence. Flag counts help locate examples for review. They do not
estimate a provider's error rate or establish an accuracy ranking.

To understand or adapt the task, read the [AlphaBench corpus](../data/alphabench.jsonl),
[listener instructions](../docs/rater-instructions-fidelity.md), and [accepted-reading examples](../docs/normalization-cases.md).
The [qualitative report](../results/alphabench/alphabench_qualitative.md) shows how the collected evidence is
organized, including cases that need task or input review.

### SupportBench: compare delivery in a support-call context

SupportBench gives listeners two recordings intended to convey the same response
and asks:

> Which recording would you prefer to hear during a customer-support call?

The supplied corpus combines conversational responses with information customers
need to understand: support dialogue, short acknowledgments, phone numbers,
dates and times, amounts and units, and addresses/contact information.
For example, `support_dialogue-0001` reads:

> A supervisor has to sign off on the card replacement, but that usually takes minutes, not days.

Listeners make one overall judgment on a five-point scale, including a tie.
Clarity, naturalness, and suitability can all influence their preference.
Reading mistakes can matter too, but the instructions do not prescribe an
automatic winner whenever one recording contains an error.

This answers a question about the spoken response. To evaluate whether an agent
resolves a support request, makes the right tool calls, or handles interruptions,
you would need additional conversational tests.

Start with the [SupportBench corpus](../data/supportbench.jsonl) and [preference instructions](../docs/rater-instructions-cmos.md).

### ContentBench: compare delivery for narration

ContentBench uses the same paired-listening structure for literature excerpts
and authored narration passages. Its question is:

> Which recording would you prefer for listening to this passage?

For example, `content_reading-0201` begins:

> A Venus flytrap can count. The trap only snaps shut when an insect touches two trigger hairs within about twenty seconds, and it starts digesting only after several more touches.

Listeners consider how easy the passage is to follow and how its pacing,
expression, and naturalness work together. This remains one overall preference
judgment; it does not produce separate scores for each quality.

The supplied material lets you examine narration preference alongside support
preference while keeping the results separate. These are short passages, so the
results do not establish listening comfort over a full audiobook or comprehension
after sustained listening.

See the [ContentBench corpus](../data/contentbench.jsonl). The [task definitions](../configs/listener_tasks.json) contain the
exact questions, descriptions, and instruction cards for all three benchmarks.

## Why group scripts into families?

A *frame* is a source template used to generate scripts. A *family* is the
grouping used to account for shared source material in the analysis. For generated
scripts, that grouping follows their recorded construction family; for narration,
it can group excerpts from one source work. A family is not simply a topic such
as travel or banking.

Suppose three scripts begin “Your confirmation code is…” and differ only in
the code. They are three recordings, but they may share the same reading or
preference pattern because they came from a shared frame.

Why not keep just one script from each family? For broad coverage under a fixed
budget, that can be a sensible choice. But some variants test a deliberate
difference. For example, an ordinary mixed code such as `AB123`, a repeated
sequence such as `BBB333`, and a confusable sequence such as `O0I1` probe
different reading challenges even inside the same sentence. These examples
illustrate the design choice, rather than define the existing corpus families.

The principle for designing another evaluation is to **prioritize distinct
scenarios and reading challenges, retaining related variants when they test an
explicit difference**. Broad preference comparisons benefit from varied material;
failure investigations can benefit from repeated, targeted variations.

Grouping lets the analysis account for shared behavior when estimating
uncertainty. It does not make redundant scripts more informative. More listeners
help resolve disagreement about the recordings you have; more varied scripts
broaden what you have tested. Make that sampling decision before the run, rather
than removing variants after seeing which systems they favor.

## How we developed the framework

Development followed four moves: establish that the collection workflow worked;
separate the questions and correct input or measurement problems; plan the
material and rating allocation; then fix the listener tasks and reporting scope.
In the [layers above](#start-with-the-framework-then-define-a-run), this meant
refining the framework before fixing the choices for a particular run.


| When           | Stage or question                                                                                                                  | What we did and changed                                                                                                                                                                                                                                                                                                                                   |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| August 6, 2026 | Could the pipeline produce usable audio, judgments, and annotations?                                                               | Ran small preference demos and reading-error pilots to establish the collection workflow and identify ambiguities.                                                                                                                                                                                                                                        |
| August 7–8     | Input notation could create apparent reading failures: Deepgram spoke “dash” between characters in the mixed code `M-N-L-9-I-C-Z`. | Tested alternative spelling controls and used comma-separated characters for mixed codes, distinguishing the intended content from the notation passed to the provider.                                                                                                                                                                                   |
| August 8       | Reading accuracy and contextual preference needed distinct tasks.                                                                  | Established the three-benchmark split and ran initial pilots with 29 AlphaBench clips per provider, 39 SupportBench pairs, and 20 ContentBench pairs per competitor.                                                                                                                                                                                      |
| August 27      | How much distinct material and listener feedback did the study need?                                                               | Froze the sampling decisions after a 90-script AlphaBench pilot across 15 frames and preference tranches, a first stage of 120 scripts per comparison rated seven times. Expanded AlphaBench to 83 frames and selected three SupportBench and five ContentBench continuation ratings to meet the target for detecting a 0.15-point preference difference. |
| September 9    | The listener instructions and permitted claims needed to match the stated questions.                                               | Fixed the revised tasks: qualitative AlphaBench evidence and overall contextual preference for SupportBench and ContentBench, without an automatic correctness-wins rule.                                                                                                                                                                                 |
| September 12   | Specification freeze and latest evaluation runs                                                                                    | Froze specification 1.0.0, identifying the corpus, configurations, listener tasks, rating allocation, and analysis. Conducted the latest result-producing runs.                                                                                                                                                                                           |
| September 12   | Publication                                                                                                                        | Published the specification, listener exports, and result reports, with file hashes and reproduction instructions.                                                                                                                                                                                                                                        |
| September 13   | Release documentation                                                                                                              | Added licensing, citation metadata, and release notes to support reuse and attribution.                                                                                                                                                                                                                                                                   |


There was also a measurement correction. An early pilot report inverted the
Deepgram preference direction. The August 9 update records that the team checked
the sign against a previously documented evaluation and corrected the report.
The current analysis determines direction from each item's target metadata,
rather than assuming a fixed A/B position. An [automated test](../tests/test_analysis.py)
checks that a score favoring target B becomes positive when B is Rime. That makes
orientation an explicit, testable part of the implementation.

The separate AlphaBench pilot deliberately used six scripts from each of 15
frames to examine whether variants behaved similarly. With only one script per
frame, we could not estimate that within-frame dependence. Its findings informed
expansion to 83 frames within the same 580-script budget. This supported broader
coverage, without establishing that 83 frames was uniquely optimal or that every
retained variant added equal value.

The preference tranches addressed rating allocation. The planning target was an
80% chance of detecting a 0.15-point difference on the five-point scale under the
model, with an adjustment for four comparisons. Three continuation ratings met
the target for every SupportBench comparison; ContentBench needed five. This
allocated additional feedback where the estimated variability required it.

The September task freeze put the [separation explained earlier](#why-evaluate-tts-this-way)
into the actual listener instructions and reporting rules.

## Our published evaluation

The latest result-producing runs took place on September 12, 2026. We published
specification 1.0.0, the exports, and the reports that day, followed by release,
licensing, and citation documentation on September 13. These are the run and
evidence layers of the framework, with their own recorded configurations and
artifacts.

This evaluation applies the framework to US-English material using Rime Coda, ElevenLabs Flash v2.5, Deepgram Aura-2, Cartesia Sonic-3, and OpenAI
gpt-4o-mini-tts. The [provider configuration](../configs/provider_configs.json) records the exact voices
and API controls. The preference design compares Rime with each competitor;
it is not an all-pairs tournament.


| Component                                                | Material                                                    | Ratings                                                     | Total judgments |
| -------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------- | --------------- |
| AlphaBench development pilot                             | 90 scripts, five providers                                  | Three per clip; excluded from main results                  | 1,350           |
| AlphaBench main                                          | 580 scripts, 83 source families, five providers             | Three per clip                                              | 8,700           |
| SupportBench: OpenAI, Deepgram, and Cartesia comparisons | 750 scripts and 286 families per comparison                 | Seven on 120 tranche items; three on 630 continuation items | 8,190           |
| SupportBench: ElevenLabs comparison                      | 750 scripts, 286 families                                   | Seven per pair                                              | 5,250           |
| ContentBench: four comparisons                           | 400 passages and 223 families per comparison                | Seven on 120 tranche items; five on 280 continuation items  | 8,960           |
| **Total**                                                | **17 evaluations, including the separate AlphaBench pilot** |                                                             | **32,450**      |


We allocated seven judgments per item to the ElevenLabs comparison to estimate
that comparison more precisely. The corpus, task, item weighting, and
interpretation rules remained the same.

For preference scoring, we first average the ratings within each script, then
weight scripts equally. This keeps an item with seven ratings from counting more
than one with three. A *source family* groups related material, such as variants
of a template or excerpts from the same work. The analysis accounts for that
structure through family bootstrap intervals and paired sign-flip tests, with
Holm correction across the four comparisons in each preference benchmark.

The [published reports](../results/README.md) show different patterns across contexts:
SupportBench favored the tested Rime configuration in all four comparisons; ContentBench
favored Rime over Cartesia and OpenAI and favored Deepgram and ElevenLabs over
Rime. The reports include confidence intervals, adjusted tests, and sensitivity
results. These observations do not isolate why preferences differ across tasks.
AlphaBench's separate [review inventory](../results/alphabench/alphabench_qualitative.md) contains 84 majority-flagged
Deepgram clips and 6–16 for each of the other configurations, out of 580 clips
each. Its Deepgram annotations include omissions and early stops. These counts
identify evidence to inspect; they are not independently adjudicated error rates
or a provider ranking.

The primary preference intervals account for shared source material, but not
dependence across scripts rated by the same listener. Results apply to the
included recordings, configurations, material, and listeners. They should guide
further evaluation on your use case rather than substitute for it.

The [run guide](../docs/frozen-run.md) explains execution, [run_design.json](../configs/run_design.json) specifies the
allocation, and the [freeze manifest](../configs/freeze_manifest.json) records file hashes. The
[export manifest](../exports/manifest.csv) identifies the released data. These records let you
connect a reported finding to the study that produced it.

## Build your own evaluation

You can begin with the supplied corpora and tasks, then adapt the parts that
need to match your application. Use the [three layers](#start-with-the-framework-then-define-a-run)
as a guide: choose the framework questions, freeze your run choices, and preserve
the evidence. The development experience suggests four checks along that path.

### 1. Choose the question and material

Decide what the evaluation should help you choose or understand. For example,
if you are comparing two voices for support responses, select the response types
that matter to that application and state how much weight each receives.

Our family analysis showed why script count alone is not enough: many variants
can repeat the same challenge. Choose varied scenarios and keep related examples
when they probe a deliberate difference. The [corpus builder](../corpus/build.py) and [generators](../corpus/generators) show how the supplied material is constructed. Preserve stable item IDs, intended readings, and source families when adapting it. Use the [input renderer](../corpus/render.py) to understand how canonical content becomes provider-specific input. Different models or languages may need additional integration and validation.

### 2. Pilot, then freeze your study

The input corrections and task review taught us to check what listeners actually
receive before fixing the instrument. Start with development material to check
the complete path: synthesis input, audio, listener task, annotations, and exports. If pilot variability will inform
the rating count, define that planning procedure before inspecting preference
directions. The [variance planner](../scripts/plan_variance_tranche.py) provides an implementation whose
defaults reflect the published design.

Record your chosen models and voices, corpus hashes, exact listener instructions,
audio handling, listener recruitment, rating allocation, exclusions, and analysis.
Freeze the specification and code before collecting the result evidence. If you
use staged collection, specify in advance which decisions the first stage may
inform and whether those judgments enter the final result.

### 3. Generate audio and collect judgments

The separator tests showed why the canonical script and the provider input both
need inspection. The [synthesis script](../scripts/synth_demo.py) contains the supported provider
integrations. Here is an example using the supplied SupportBench corpus, the configured Rime
defaults, and the published audio settings:

```bash
uv sync --frozen
uv run python scripts/synth_demo.py \
  --corpus data/supportbench.jsonl \
  --providers rime \
  --outdir out/support \
  --audio-mode level-matched \
  --sample-rate 24000 \
  --target-lufs -23 \
  --true-peak-db -1
```

Set the relevant provider API key first. Inspect `--help` for model and voice
overrides, and check that the actual command matches your recorded configuration.
The published audio policy applies linear gain toward -23 LUFS subject to a
-1 dBTP ceiling, with additional Podonos normalization disabled. Preserve the
manifests, hashes, settings, and generation-attempt records.

Use the [AlphaBench](../scripts/submit_fidelity_podonos.py), [SupportBench](../scripts/submit_supportbench_podonos.py), or [ContentBench](../scripts/submit_contentbench_podonos.py)
submission script with the generated manifests, a unique evaluation name,
language, and rating count. These scripts create drafts by default. Review the
rendered listener task and allocation before starting paid collection.

### 4. Inspect the evidence and report what it supports

Confirm score orientation before analysis. Our early sign error is the reason
this deserves an explicit check: verify from target metadata which system each
end of the scale favors, and test a known example before interpreting the means.

The [AlphaBench analyzer](../scripts/analyze_alphabench_qualitative.py) assembles qualitative reading-error evidence.
The [preference analyzer](../scripts/analyze_comparison.py) produces paired results and
uncertainty. Retain raw exports, and keep summary files separate from
individual-response files so the same judgments are not counted twice.

For a different comparison design, review the code before using its output.
The released implementation includes Rime-oriented labels, four-competitor
assumptions, and fixed corpus checks. Changing the baseline, number of systems,
or sampling structure can require adapting the analysis as well as configuration.

If your goal is reproduction, follow the [results guide](../results/README.md) and run
`scripts/check_frozen_run.py` against the published specification. If your goal
is a new evaluation, retain the original release and give your study its own
version and integrity checks. Share its tasks, configuration, coverage,
deviations, and evidence alongside the findings so others can understand what
you tested and build on it.
