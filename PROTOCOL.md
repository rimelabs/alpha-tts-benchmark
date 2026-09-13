# TTS benchmark protocol

Status: frozen benchmark specification

Protocol and audio version: 1.0.0

Listener-task version: 1.0.0

AlphaBench analysis is qualitative.

Scope: US-English

Freeze date: 2026-09-12

This file describes the corpora, listener tasks, scoring, and interpretation
for AlphaBench, SupportBench, and ContentBench.

AlphaBench reports functional failure types and supporting clips.
SupportBench and ContentBench report paired listener preference.

## Research questions

| Benchmark | Question | Primary result |
|---|---|---|
| AlphaBench | What functional reading failures occur on exact identifiers? | Qualitative failure taxonomy and supporting clips |
| SupportBench | Which rendering would a listener prefer in a customer-support conversation? | Mean paired Rime-minus-competitor score |
| ContentBench | Which rendering would a listener prefer for narrated articles, stories, and videos? | Mean paired Rime-minus-competitor score |

These are two different instruments. AlphaBench documents reading failure mechanisms. SupportBench and ContentBench measure contextual overall preference. Do not combine them into one score or claim that the preference task separately proves naturalness, prosody, acoustic fidelity, or engagement.

## Target of inference

Results describe the US-English scripts, provider configurations, audio, and listeners included in the evaluation.

The results do not establish multilingual performance, all voices from a provider, later model versions, production latency, speech-to-speech performance, or every listener population.

## Corpus and comparisons

- AlphaBench has 580 scripts and five providers: Rime, OpenAI, ElevenLabs, Cartesia, and Deepgram.
- SupportBench has 750 scripts and four Rime-versus-competitor comparisons.
- ContentBench has 400 scripts and four Rime-versus-competitor comparisons.
- The held-out ambiguity corpus is excluded.
- The same canonical script appears on both sides of each A/B comparison.
- Each corpus item has a stable item ID and family ID. Generated items also record a stable template ID.
- Provider-specific markup and spelling instructions express the same canonical spoken content.

The corpus build is deterministic.

### Family definitions

A family records shared source material that may make item outcomes dependent. It is not a reporting category.

| Benchmark | Items per comparison | Families | Definition | Family size |
|---|---:|---:|---|---:|
| AlphaBench | 580 | 83 | Generation frame | 5-11 |
| SupportBench | 750 | 286 | Generation frame; authored one-off lines are single-item families | 1-13 |
| ContentBench | 400 | 223 | Source work for literature; one family per narration passage | 1-10 |

The generator hashes the unfilled source frame into `template_id`. Rendered variants share a family within their corpus construction group. SupportBench phone frames can occur in separate subcategory-specific families: its 267 template IDs map to 286 families. The recorded family IDs define the primary clustering; subcategories also support stratified reporting.

## Provider configurations

The machine-readable source is [configs/provider_configs.json](configs/provider_configs.json). The included settings use these models and voices across the three benchmarks:

| Provider | Model and voice |
|---|---|
| Rime | Coda, clementine |
| ElevenLabs | Flash v2.5, voice ID vCHG6sKIqAbXWNNm5vpY, stability 0.5, similarity boost 0.75, text normalization on |
| Deepgram | Aura-2, thalia, en-US |
| Cartesia | Sonic-3, voice ID e07c00bc-4134-4eae-9ea4-1a55fb45746b, API version 2026-03-01 |
| OpenAI | gpt-4o-mini-tts, coral |

The synthesis defaults request 24 kHz mono audio. Use the settings and fixed allocation in [docs/frozen-run.md](docs/frozen-run.md) and [configs/run_design.json](configs/run_design.json). General-purpose command-line overrides do not change that run definition.

## AlphaBench

### Rater task

The rater sees the complete canonical script and hears one clip.

Question:

> Does this recording contain a reading error compared with the displayed script?

Description:

> Select Reading error if any required word, letter, number, name, or other entity is missing, added, wrong, repeated, out of order, cut off, or unclear. Select No reading error if all required content is conveyed correctly and unambiguously.

Options:

- No reading error.
- Reading error.

In a spelling such as `P-H-I-L-L-I-P`, the hyphens are visual separators. The voice should say the letters, not the word "dash." A pause, grouped digits, or an unspoken visual separator is not an error when every required character is clear exactly once and in order.

When the rater selects Reading error, Podonos asks for a highlighted text region and a note beginning with one or more structured labels:

- `[OMISSION]`
- `[SUBSTITUTION]`
- `[INSERTION]`
- `[REPETITION]`
- `[REORDERING]`
- `[EARLY_STOP]`
- `[SLURRED_OR_AMBIGUOUS]`
- `[OTHER]`

The note states the expected content and what the listener heard. Accent, pace, pitch, voice quality, pauses, and grouping are not errors when the full content remains unambiguous.

### AlphaBench qualitative evidence rule

The report records the number of judgments and reading-error flags for each clip, including majority and unanimous support. Those counts show listener support for reviewing an example. They are not independent observations, error-rate estimates, or tests.

The corpus retains nine subcategories and 83 source frames to cover different identifier forms and failure mechanisms. The separate statistical diagnostic averages scripts within frames, weights frames equally within each subcategory, and uses these corpus shares:

| Subcategory | Scripts | Corpus share |
|---|---:|---:|
| `confirmation_code` | 98 | `98 / 580` |
| `confusable` | 40 | `40 / 580` |
| `flight_number` | 66 | `66 / 580` |
| `license_plate` | 40 | `40 / 580` |
| `long_code` | 40 | `40 / 580` |
| `name_spelling` | 80 | `80 / 580` |
| `order_number` | 96 | `96 / 580` |
| `policy_case_id` | 73 | `73 / 580` |
| `tracking_number` | 47 | `47 / 580` |
| **Total** | **580** | **`580 / 580`** |

Report recurring error types, representative clips, exact expected and heard sequences, subcategory, and listener support. Keep task or input artifacts separate from provider failures. A visual-separator misunderstanding, provider-specific conditioning mistake, corrupt file, or platform transform is not a model failure.

AlphaBench does not produce a primary provider error rate, paired effect, confidence interval, p-value, multiplicity-adjusted test, rank, or winner. Descriptive clip and vote counts may help readers locate evidence, but they cannot support prevalence language or a comparative provider claim.

Statistical diagnostics do not support a primary AlphaBench provider claim.

## SupportBench and ContentBench

### Rater tasks

Both tasks use a five-point comparison scale with a real tie. Podonos may store either model as canonical target A. Rime recodes every item from the target metadata to this analysis convention:

| Score | Meaning |
|---|---|
| +2 | Rime much better |
| +1 | Rime better |
| 0 | About the same |
| -1 | Competitor better |
| -2 | Competitor much better |

SupportBench question:

> Which recording would you prefer to hear during a customer-support call?

Description:

> Both recordings are intended to convey the same text. Imagine receiving this spoken response during a customer-support call. Consider the delivery as a whole: how easy it is to understand, how natural the speech sounds, and how well it fits the situation. Make one overall preference judgment.

ContentBench question:

> Which recording would you prefer for listening to this passage?

Description:

> Both recordings are intended to convey the same text. Imagine listening to this passage as narration. Consider the delivery as a whole: how easy it is to follow, how natural the speech sounds, and how well the pacing and expression fit the passage. Make one overall preference judgment.

The listener instructions ask raters to use headphones, listen to both clips completely, keep volume fixed, and avoid forced preferences. The preference tasks ask for one overall contextual judgment without an explicit reading-error penalty or a rule that the correctly read clip must win. They do not instruct listeners to ignore mistakes.

The exact questions, descriptions, cards, response options, and anchor labels are in [configs/listener_tasks.json](configs/listener_tasks.json) and implemented by the submission scripts.

### Preference estimand

For each item and competitor:

1. Recode every valid response to the Rime-positive scale using the canonical target metadata.
2. Average repeated judgments within the item.
3. Take the mean across items.

Repeated judgments reduce uncertainty within an item. They do not create additional independent scripts.

## Statistical analysis

### Independent unit and confidence intervals

AlphaBench has no inferential estimate or hypothesis test. Its report contains judgment counts, majority-review flags, structured failure labels, annotations, and clip references as qualitative evidence.

SupportBench and ContentBench preserve each Rime-versus-competitor pair within item. The analysis defaults to 10,000 bootstrap replicates with a fixed seed.

SupportBench and ContentBench first average repeated judgments within item. Their construction families may share a source template, so the primary interval resamples family IDs and then items within each selected family. Their paired test is the family-level sign-flip test.

ContentBench also reports a coarser-dependence sensitivity. For a literature item whose `notes` field has the form `Source: title, author`, replace the source-work family with the normalized author cluster `content-author:<author-slug>`. Group other ContentBench items by their genre or subcategory as `content-genre:<subcategory>`. Items outside ContentBench retain their source family. Recompute the family-percentile interval and family sign-flip test with these clusters, then apply Holm correction across the same four competitors. This sensitivity can qualify a primary claim but cannot license one. The source-family analysis remains primary.

For SupportBench and ContentBench, report the 2.5th and 97.5th family-bootstrap percentiles as the ordinary 95% interval.

The analysis reports the number of families and Kish effective family count. These intervals account for source-family dependence; they do not model dependence between different items rated by the same listener. A sensitivity analysis can qualify a primary claim. It can never license a claim that the primary family-clustered analysis does not support.

### Multiple comparisons

Apply Holm's correction separately to the four planned Rime-versus-competitor tests in SupportBench and the four in ContentBench. Report raw effect estimates and ordinary intervals alongside Holm-adjusted p-values. AlphaBench has no p-values or multiplicity correction.

Elo and Bradley-Terry rankings remain exploratory. They cannot replace the pairwise comparisons.

### Claim rule

For SupportBench and ContentBench, a directional claim requires the paired analysis and its Holm-adjusted test to support that direction. An interval crossing zero is inconclusive. It is not proof of equivalence.

AlphaBench permits no provider-level directional, prevalence, parity, equivalence, rank, or winner claim. Its output is a failure taxonomy with supporting clips and listener notes.

Magnitude language must use the 95% interval bound nearest zero, never the point estimate alone. Version 1 defers equivalence testing and prohibits parity, equivalence, no-difference, and indistinguishable claims. A null or inconclusive result remains inconclusive.

Do not give a causal or mechanistic explanation for a benchmark result unless separate evidence directly tests that explanation. The benchmark measures outcomes under the evaluated configurations; it does not identify why a provider performed as observed.

Do not use 0.07 as a perceptual threshold. Do not label a difference small, large, meaningful, or imperceptible without a separately justified threshold.

Report a result in this form:

> On the five-point SupportBench scale, Rime's mean paired advantage over X was Y, with a 95% interval of [L, U], across N scripts and M valid judgments.

## Multiplicity families

Holm correction is applied separately to:

- four SupportBench comparisons against Rime
- four ContentBench comparisons against Rime

Per-category analyses, error labels, win/tie/loss counts, Elo, Bradley-Terry scores, galleries, and adjudicated results are exploratory or diagnostic.

The two four-comparison families do not support a combined claim such as "leads across our benchmarks." AlphaBench cannot enter a combined directional claim because it has no provider-level inferential result.
