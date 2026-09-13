"""Very short agent utterances: one to four words. These are the trivial
turns every voice-agent must handle — backchannels, confirmations, brief
answers — and they stress prosody / naturalness with almost no text-
normalization load.
"""

from __future__ import annotations

import random

from . import sentence

CATEGORY = "short_responses"

UTTERANCES = [
    ("Okay.", "single-word acknowledgment"),
    ("Got it.", "two-word acknowledgment"),
    ("I understand.", "empathy acknowledgment"),
    ("Yes.", "affirmative"),
    ("No.", "negative"),
    ("Absolutely.", "emphatic affirmative"),
    ("Of course.", "affirmative"),
    ("Sure thing.", "casual affirmative"),
    ("Right.", "acknowledgment"),
    ("Understood.", "single-word acknowledgment"),
    ("Certainly.", "formal affirmative"),
    ("Not a problem.", "reassurance"),
    ("My apologies.", "brief apology"),
    ("One moment.", "hold request"),
    ("One moment, please.", "polite hold request"),
    ("Let me check.", "transition to lookup"),
    ("Let me look into that.", "transition to lookup"),
    ("I see.", "acknowledgment"),
    ("Thank you.", "thanks"),
    ("Thanks for waiting.", "post-hold thanks"),
    ("You're all set.", "closing confirmation"),
    ("Is there anything else?", "closing prompt"),
    ("Anything else I can help with?", "closing prompt"),
    ("Happy to help.", "closing pleasantry"),
    ("No problem at all.", "reassurance"),
    ("Great question.", "acknowledgment before answer"),
    ("Good news.", "positive transition"),
    ("I appreciate your patience.", "empathy"),
    ("That's correct.", "confirmation"),
    ("Exactly.", "emphatic confirmation"),
    ("Perfect.", "confirmation"),
    ("Will do.", "commitment"),
    ("Done.", "completion"),
    ("All set.", "completion"),
    ("Go ahead.", "prompt to continue"),
    ("Please hold.", "hold request"),
    ("I'm sorry to hear that.", "empathy"),
    ("No worries.", "casual reassurance"),
    ("Sure.", "casual affirmative"),
    ("Noted.", "single-word acknowledgment"),
]


def generate(rng: random.Random, n: int) -> list[dict]:
    if n > len(UTTERANCES):
        raise ValueError(f"requested {n} but only {len(UTTERANCES)} utterances available")
    picked = rng.sample(UTTERANCES, n)
    return [
        sentence(CATEGORY, "backchannel", text, notes, template=text)
        for text, notes in picked
    ]
