"""Dates, times, ranges, and durations in the written formats that stress
TTS text normalization: numeric dates, ordinals, 12h/24h clock, time zones.
"""

from __future__ import annotations

import random

from . import framed_sentence, sample_unique

CATEGORY = "dates_times"

MONTHS = [
    ("January", 31), ("February", 28), ("March", 31), ("April", 30),
    ("May", 31), ("June", 30), ("July", 31), ("August", 31),
    ("September", 30), ("October", 31), ("November", 30), ("December", 31),
]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ZONES = ["Eastern", "Central", "Mountain", "Pacific", "ET", "CT", "PT", "EST", "PST", "CDT"]


def _ordinal(d: int) -> str:
    if 11 <= d % 100 <= 13:
        return f"{d}th"
    return f"{d}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th') }"


def _date(rng: random.Random) -> dict:
    mi = rng.randrange(12)
    month, max_day = MONTHS[mi]
    day = rng.randint(1, max_day)
    year = rng.choice([2025, 2026, 2027])
    style = rng.randrange(5)
    if style == 0:
        d, note = f"{month} {day}, {year}", "spoken with ordinal day and full year"
    elif style == 1:
        d, note = f"{mi + 1}/{day}/{year}", "numeric date; must be read as a date, not a fraction"
    elif style == 2:
        d, note = f"{year}-{mi + 1:02d}-{day:02d}", "ISO format; must be read as a date"
    elif style == 3:
        d, note = f"the {_ordinal(day)} of {month}", "ordinal-first form"
    else:
        d, note = f"{rng.choice(WEEKDAYS)}, {month} {_ordinal(day)}", "weekday plus ordinal date"
    frames = [
        "Your appointment is scheduled for {d}.",
        "The payment is due on {d}.",
        "We show the account was opened on {d}.",
        "That promotion ends on {d}, so there's still time.",
        "Delivery is currently estimated for {d}.",
        "The warranty expires on {d}.",
    ]
    return framed_sentence(
        rng, CATEGORY, "date", frames, values={"d": d}, notes=note
    )


def _time(rng: random.Random) -> dict:
    hour12 = rng.randint(1, 12)
    minute = rng.choice([0, 5, 10, 15, 20, 30, 40, 45, 50, 59])
    style = rng.randrange(4)
    if style == 0:
        t = f"{hour12}:{minute:02d} {rng.choice(['AM', 'PM', 'a.m.', 'p.m.'])}"
        note = "12-hour clock; ':00' spoken as o'clock or omitted"
    elif style == 1:
        # 13+ only: below 13:00 the written form is indistinguishable from
        # a 12-hour time, so it wouldn't exercise 24-hour reading.
        h24 = rng.randint(13, 23)
        t = f"{h24}:{minute:02d}"
        note = "24-hour clock; acceptable to read as 12-hour equivalent or as written"
    elif style == 2:
        t = f"{hour12}:{minute:02d} {rng.choice(['PM', 'AM'])} {rng.choice(ZONES)}"
        note = "time with zone; zone abbreviation read as letters or expanded"
    else:
        t = rng.choice(["noon", "midnight", f"{hour12} o'clock"])
        note = "word-form time"
    frames = [
        "The technician should be there by {t}.",
        "Our office closes at {t} today.",
        "The webinar starts promptly at {t}.",
        "Your flight now departs at {t}.",
        "I have you down for a callback at {t}.",
    ]
    return framed_sentence(
        rng, CATEGORY, "time", frames, values={"t": t}, notes=note
    )


def _range(rng: random.Random) -> dict:
    mi = rng.randrange(12)
    month, max_day = MONTHS[mi]
    d1 = rng.randint(1, max_day - 10)
    d2 = d1 + rng.randint(2, 9)
    style = rng.randrange(3)
    if style == 0:
        r = f"from {month} {d1} to {month} {d2}"
    elif style == 1:
        r = f"{month} {d1}–{d2}"
    else:
        h = rng.randint(8, 10)
        r = f"between {h}:00 AM and {h + rng.randint(2, 4)}:30 PM"
    frames = [
        "The office will be closed {r} for renovations.",
        "You can expect the technician {r}.",
        "The sale runs {r}, while supplies last.",
        "Installation appointments are available {r} next week.",
    ]
    return framed_sentence(
        rng, CATEGORY, "range", frames, values={"r": r},
        notes="both endpoints spoken; en dash read as 'to' or 'through'",
    )


def _duration(rng: random.Random) -> dict:
    style = rng.randrange(3)
    if style == 0:
        a = rng.randint(2, 5)
        d = f"{a} to {a + rng.randint(2, 5)} business days"
    elif style == 1:
        d = rng.choice(["24 to 48 hours", "48 hours", "72 hours", "7 to 10 business days"])
    else:
        d = rng.choice(["90 days", "30 days", "12 months", "6 weeks", "45 minutes"])
    frames = [
        "The refund typically takes {d} to appear on your statement.",
        "You should receive the replacement within {d}.",
        "The trial period lasts {d} from activation.",
        "Please allow {d} for the dispute to be reviewed.",
    ]
    return framed_sentence(
        rng, CATEGORY, "duration", frames, values={"d": d},
        notes="numbers read as cardinals",
    )


_MAKERS = [(_date, 40), (_time, 30), (_range, 15), (_duration, 15)]


def _make(rng: random.Random) -> dict:
    maker = rng.choices([m for m, _ in _MAKERS], weights=[w for _, w in _MAKERS])[0]
    return maker(rng)


def generate(rng: random.Random, n: int) -> list[dict]:
    return sample_unique(rng, _make, n)
