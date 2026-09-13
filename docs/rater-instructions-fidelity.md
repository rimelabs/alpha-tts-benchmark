# Rater instructions: AlphaBench whole-script reading accuracy

Listener-task version: 1.0.0.

Question:

> Does this recording contain a reading error compared with the displayed script?

Description:

> Select Reading error if any required word, letter, number, name, or other entity is missing, added, wrong, repeated, out of order, cut off, or unclear. Select No reading error if all required content is conveyed correctly and unambiguously.

## Your task

You will see a sentence of **text** and hear one **audio clip** of a synthetic voice reading it. Decide whether the audio contains **exactly** the text — nothing added, nothing missing, nothing repeated.

You are checking **content**, not style or voice quality. A robotic-sounding clip that says exactly the right words is a **Pass**. A beautiful-sounding clip that repeats one digit is a **Fail**.

## How to work

1. Read the full text first.
2. Play the clip. Follow along word by word, character by character for codes and numbers.
3. Replay difficult words, letters, numbers, names, or entities before answering.
4. Answer No reading error or Reading error. If you mark Reading error, highlight or describe the affected script region.

In a spelling such as `P-H-I-L-L-I-P`, the hyphens are visual separators between letters. The voice should say the letters. It should not say the word "dash." Not speaking these visual separators is a pass.

## What counts as a FAIL

| Error type | Example (text → what was heard) |
|---|---|
| **Repetition** | `555-0132` → "five five five, zero one three **three** two" (extra digit) |
| **Omission** | `X7Q-4RZ` → "X seven, four R Z" (Q dropped) |
| **Insertion / hallucination** | "Your balance is $40." → "Your balance is $40 **today**." |
| **Substitution** | `WBGK2KPBV4TZ` → "W B G K 2 K P B **4** T Z" (V became 4) |
| **Reordering** | `AK52` → "A K 2 5" |
| **Wrong symbol reading** | `3/14/2026` read as "three fourteenths…"; `$1,247` read as "one hundred twenty-four thousand seven" |
| **Early stop / truncation** | Audio ends before the sentence or spelled identifier does |
| **Slurred or ambiguous** | Required content cannot be identified confidently by the listener |
| **Pronunciation / other reading error** | A word, name, letter, number, or entity is pronounced as a different item |

## What is NOT a fail

The same text can be read correctly in more than one style. In general, all of these **Pass**:

- `1-800` read as "one eight hundred" **or** "one, eight, zero, zero"
- Digits grouped ("fifty-five") or individual ("five five") — as long as every digit is accounted for exactly once, in order
- `ext.` read as "extension"; `#` read as "number" or omitted; `@` as "at"; `.` in emails/URLs as "dot"
- `PM` as "p m" or "in the afternoon" context-appropriate clock readings; `16:30` as "four thirty PM" or "sixteen thirty"
- State abbreviations expanded (`TX` → "Texas") or read as letters
- Alphanumeric codes (confirmation numbers, plates, tracking numbers): expect character-by-character reading; grouped digits ("forty-seven" for `47`) still pass as long as every character is accounted for exactly once, in order
- Codes contain no hyphens, spaces, or symbols — every character in a code should be spoken, each exactly once, in order
- Hyphens between single letters in a spelled name are visual separators and should not be spoken as "dash"
- Accent, pacing, pitch, or "unnatural" prosody — **never** a fidelity failure

**Rule of thumb:** if a careful listener transcribing the audio would write down exactly the text shown (allowing standard readings of numbers and symbols), it passes.

## Edge cases

- Accent variation is a pass. A pronunciation that changes the word or name, or makes it impossible to identify confidently, is a reading error.
- A digit that is slurred or ambiguous: replay it; if the required content remains unclear, label the error `[SLURRED_OR_AMBIGUOUS]`.
- Long pause mid-sentence with no content change: **Pass**.
- The clip contains the full text and then extra noise/breath (no words): **Pass**.

## How to label an error

Start every error note with one or more of these labels, then write the expected and heard content:

- `[OMISSION]`
- `[SUBSTITUTION]`
- `[INSERTION]`
- `[REPETITION]`
- `[REORDERING]`
- `[EARLY_STOP]`
- `[SLURRED_OR_AMBIGUOUS]`
- `[OTHER]`

Example: `[EARLY_STOP] Expected P-H-I-L-L-I-P; audio ended after the second I.`

## Environment

Use headphones in a quiet room. The exact platform instructions are in [listener_tasks.json](../configs/listener_tasks.json).
