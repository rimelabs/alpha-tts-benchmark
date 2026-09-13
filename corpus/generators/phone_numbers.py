"""Phone numbers in the formats a customer-support agent actually says them.

All numbers use the reserved fictional 555-01XX exchange range so nothing in
the corpus is a real dialable number.
"""

from __future__ import annotations

import random

from . import framed_sentence, sample_unique

CATEGORY = "phone_numbers"

AREA_CODES = [
    "212", "310", "415", "512", "617", "702", "737", "808", "917", "206",
    "303", "404", "480", "503", "615", "720", "813", "832", "907", "952",
]

TOLL_FREE = ["800", "833", "844", "855", "866", "877", "888"]

FRAMES = [
    "You can reach our billing department at {num}.",
    "Please call us back at {num} if the issue comes up again.",
    "The number on file for your account is {num}.",
    "For faster service, dial {num} and select option two.",
    "Our support line, {num}, is open around the clock.",
    "I'm going to transfer you, but just in case, the direct line is {num}.",
    "If we get disconnected, call me back directly at {num}.",
    "The pharmacy can be reached at {num} during business hours.",
    "To confirm your appointment, call {num} before Friday.",
    "That fax should go to {num}, attention claims department.",
    "The dealership's service desk is {num}.",
    "You'll want to contact the manufacturer at {num} for warranty claims.",
]

EXT_FRAMES = [
    "Call the main office at {num}, extension {ext}.",
    "My direct extension is {ext}, and the front desk number is {num}.",
    "Dial {num} and ask for extension {ext}.",
]


def _line(rng: random.Random) -> str:
    return f"01{rng.randint(0, 99):02d}"


def _local(rng: random.Random) -> tuple[str, str]:
    ac, line = rng.choice(AREA_CODES), _line(rng)
    if rng.randrange(2) == 0:
        return f"({ac}) 555-{line}", "parenthesized area code"
    return f"{ac}-555-{line}", "hyphenated"


def _toll_free(rng: random.Random) -> tuple[str, str]:
    tf, line = rng.choice(TOLL_FREE), _line(rng)
    style = rng.randrange(3)
    if style == 0:
        return f"1-{tf}-555-{line}", "toll-free with leading 1"
    if style == 1:
        return f"1 ({tf}) 555-{line}", "toll-free, parenthesized"
    return f"{tf}-555-{line}", "toll-free, no leading 1"


def _international(rng: random.Random) -> tuple[str, str]:
    ac, line = rng.choice(AREA_CODES), _line(rng)
    style = rng.randrange(2)
    if style == 0:
        return f"+1 {ac} 555 {line}", "E.164-style with spaces"
    return f"+1-{ac}-555-{line}", "E.164-style hyphenated"


def _make(rng: random.Random) -> dict:
    kind = rng.choices(
        ["local", "toll_free", "international", "extension"],
        weights=[40, 30, 15, 15],
    )[0]
    if kind == "extension":
        num, fmt = _local(rng)
        ext = str(rng.randint(100, 9899))
        notes = f"{fmt}; extension digits read individually or as pairs"
        return framed_sentence(
            rng, CATEGORY, "extension", EXT_FRAMES,
            values={"num": num, "ext": ext}, notes=notes,
        )
    if kind == "local":
        num, fmt = _local(rng)
    elif kind == "toll_free":
        num, fmt = _toll_free(rng)
    else:
        num, fmt = _international(rng)
    notes = (
        f"{fmt}; every digit must be read exactly once, in order; "
        "grouped readings (e.g. 'eight hundred') and individual digits both pass"
    )
    return framed_sentence(
        rng, CATEGORY, kind, FRAMES, values={"num": num}, notes=notes
    )


def generate(rng: random.Random, n: int) -> list[dict]:
    return sample_unique(rng, _make, n)
