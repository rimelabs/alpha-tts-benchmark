"""Currency amounts, percentages, and measurements — the numeric expressions
where normalization errors (wrong magnitude, dropped cents, misread decimals)
are most damaging in customer-support contexts.

Each value type carries its own semantically compatible frames so units
never land in nonsensical contexts (no temperatures as dosages).
"""

from __future__ import annotations

import random

from . import framed_sentence, sample_unique

CATEGORY = "amounts_units"

CURRENCY_FRAMES = [
    "Your current balance is {a}.",
    "The late fee of {a} has been waived as a courtesy.",
    "That plan runs {a} per month before taxes.",
    "I see a pending charge of {a} from yesterday.",
    "The deductible on this policy is {a}.",
    "You'll receive a credit of {a} on your next statement.",
    "The estimate for the repair came to {a}.",
]

PERCENT_FRAMES = [
    "That discount takes {p} off the total.",
    "Usage is up {p} compared to last month.",
    "The restocking fee is {p} of the purchase price.",
    "About {p} of orders ship the same day.",
]

RATE_FRAMES = [
    "The introductory rate is {p} for the first year.",
    "After the promotional period, the card reverts to {p}.",
    "We can refinance that at {p} if you qualify.",
]

# (value builder, frames appropriate to that unit)
MEASUREMENT_KINDS = [
    (
        lambda rng: f"{rng.randint(1, 20)}.{rng.randint(1, 9)} miles",
        [
            "The nearest branch is about {m} from your address.",
            "The service center is {m} away, right off the highway.",
        ],
        "decimal distance",
    ),
    (
        lambda rng: f"{rng.choice([250, 450, 500, 750, 1000])} mg",
        [
            "The prescribed dose is {m}, taken twice daily.",
            "Each tablet contains {m} of the active ingredient.",
        ],
        "unit abbreviation expanded to milligrams",
    ),
    (
        lambda rng: f"{rng.randint(55, 104)}°F",
        [
            "The thermostat was reporting {m} at the time of the alert.",
            "Tomorrow's high is expected to reach {m}.",
        ],
        "degree symbol spoken",
    ),
    (
        lambda rng: f"{rng.choice([5, 15, 50, 100, 500])} GB",
        [
            "Your plan includes {m} of data each month.",
            "You've used just over {m} of storage so far.",
        ],
        "unit read as gigabytes or letters",
    ),
    (
        lambda rng: f"{rng.randint(2, 48)}.{rng.randint(1, 9)} pounds",
        [
            "The package weighs just under {m}.",
            "With the packaging, it comes to about {m}.",
        ],
        "decimal weight",
    ),
]


def _currency(rng: random.Random) -> dict:
    style = rng.randrange(4)
    if style == 0:
        amt = f"${rng.randint(1, 99)}.{rng.randint(0, 99):02d}"
        note = "dollars and cents both spoken"
    elif style == 1:
        amt = f"${rng.randint(1, 9)},{rng.randint(0, 999):03d}.{rng.randint(0, 99):02d}"
        note = "thousands separator; full magnitude and cents spoken"
    elif style == 2:
        amt = f"${rng.choice([19, 29, 39, 49, 99, 149, 199])}.99"
        note = "price-point form"
    else:
        amt = f"${rng.randint(10, 950)}"
        note = "whole-dollar amount"
    return framed_sentence(
        rng, CATEGORY, "currency", CURRENCY_FRAMES, values={"a": amt}, notes=note
    )


def _percentage(rng: random.Random) -> dict:
    style = rng.randrange(3)
    if style == 0:
        p = f"{rng.randint(1, 29)}.{rng.choice([25, 5, 75, 9, 99])}%"
        note = "decimal percentage; decimal point and all digits spoken"
        frames = PERCENT_FRAMES
    elif style == 1:
        p = f"{rng.choice([5, 10, 15, 20, 25, 30, 40, 50])}%"
        note = "whole percentage"
        frames = PERCENT_FRAMES
    else:
        p = f"{rng.randint(2, 8)}.{rng.randint(0, 9)}% APR"
        note = "rate with APR; abbreviation read as letters"
        frames = RATE_FRAMES
    return framed_sentence(
        rng, CATEGORY, "percentage", frames, values={"p": p}, notes=note
    )


def _measurement(rng: random.Random) -> dict:
    make_value, frames, note = MEASUREMENT_KINDS[rng.randrange(len(MEASUREMENT_KINDS))]
    m = make_value(rng)
    return framed_sentence(
        rng, CATEGORY, "measurement", frames, values={"m": m}, notes=note
    )


def _account_figure(rng: random.Random) -> dict:
    style = rng.randrange(2)
    if style == 0:
        f_ = f"{rng.randint(1, 12)} of {rng.randint(13, 24)}"
        note = "'of' construction with two cardinals"
        frames = [
            "That's payment {f} on the current schedule.",
            "You've completed installment {f} on this payment plan.",
        ]
    else:
        f_ = f"{rng.randint(101, 999)} kWh"
        note = "kilowatt-hours; unit expanded or read as letters"
        frames = [
            "Last month the meter recorded {f}.",
            "Your household averaged {f} over the billing period.",
        ]
    return framed_sentence(
        rng, CATEGORY, "account_figure", frames, values={"f": f_}, notes=note
    )


_MAKERS = [(_currency, 45), (_percentage, 25), (_measurement, 20), (_account_figure, 10)]


def _make(rng: random.Random) -> dict:
    maker = rng.choices([m for m, _ in _MAKERS], weights=[w for _, w in _MAKERS])[0]
    return maker(rng)


def generate(rng: random.Random, n: int) -> list[dict]:
    return sample_unique(rng, _make, n)
