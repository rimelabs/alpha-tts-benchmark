"""Street addresses, emails, URLs, and spelled-out names — contact details a
support agent reads back to a caller. All domains use example.com/.org/.net
and addresses are synthetic.
"""

from __future__ import annotations

import random

from . import framed_sentence, sample_unique

CATEGORY = "addresses_contact"

STREET_NAMES = [
    "Maple", "Oak", "Cedar", "Willow", "Lakeview", "Sunset", "Harrison",
    "Jefferson", "Meadowbrook", "Fairview", "Cypress", "Juniper", "Bristol",
]
STREET_TYPES = ["Street", "Avenue", "Boulevard", "Drive", "Lane", "Court", "Road"]
CITIES = [
    ("Austin", "TX", "78701"), ("Denver", "CO", "80203"), ("Portland", "OR", "97205"),
    ("Nashville", "TN", "37203"), ("Phoenix", "AZ", "85004"), ("Columbus", "OH", "43215"),
    ("Raleigh", "NC", "27601"), ("Sacramento", "CA", "95814"), ("Tampa", "FL", "33602"),
    ("Minneapolis", "MN", "55401"),
]
FIRST_NAMES = [
    "Priya", "Marcus", "Elena", "Dashawn", "Keiko", "Tomás", "Ingrid", "Rohan",
    "Aoife", "Nikolai", "Yusuf", "Simone", "Bram", "Leilani", "Otis", "Wren",
]
LAST_NAMES = [
    "Okafor", "Lindqvist", "Marchetti", "Villanueva", "Szymanski", "Beaumont",
    "Kowalczyk", "Nakagawa", "Petrov", "Delacroix", "Whitfield", "Iversen",
]
URL_PATHS = ["returns", "help", "account", "billing", "track", "support/chat", "reset", "warranty"]


def _address(rng: random.Random) -> dict:
    num = rng.choice([rng.randint(10, 999), rng.randint(1000, 9899)])
    street = f"{rng.choice(STREET_NAMES)} {rng.choice(STREET_TYPES)}"
    city, state, zip5 = rng.choice(CITIES)
    style = rng.randrange(3)
    if style == 0:
        a = f"{num} {street}, {city}, {state} {zip5}"
        note = "full address; state abbreviation as letters or expanded; ZIP digits individually"
    elif style == 1:
        unit = rng.choice(["Apt", "Suite", "Unit"])
        a = f"{num} {street}, {unit} {rng.choice(['2B', '410', '17', 'C'])}, {city}, {state} {zip5}"
        note = "address with unit; unit designator and value both spoken"
    else:
        a = f"{num} {street} in {city}"
        note = "short address form"
    frames = [
        "I have the shipping address as {a} — is that correct?",
        "The replacement card was mailed to {a}.",
        "Our nearest service center is located at {a}.",
        "Please send the signed form to {a}.",
    ]
    return framed_sentence(
        rng, CATEGORY, "street_address", frames, values={"a": a}, notes=note
    )


def _url(rng: random.Random) -> dict:
    style = rng.randrange(3)
    if style == 0:
        u = f"www.example.com/{rng.choice(URL_PATHS)}"
        note = "'www' as letters, dots and slash spoken"
    elif style == 1:
        u = f"example.com/{rng.choice(URL_PATHS)}"
        note = "bare domain with path; slash spoken"
    else:
        u = f"example.{rng.choice(['com', 'org'])}"
        note = "bare domain"
    frames = [
        "You can start the return yourself at {u}.",
        "Head over to {u} and sign in with your account.",
        "All of the outage updates are posted at {u}.",
        "The self-service portal is {u}, available any time.",
    ]
    return framed_sentence(
        rng, CATEGORY, "url", frames, values={"u": u}, notes=note
    )


def _spelled_name(rng: random.Random) -> dict:
    name = rng.choice(LAST_NAMES if rng.random() < 0.7 else FIRST_NAMES)
    spelled = "-".join(name.upper())
    frames = [
        "The last name is {n} — that's {s}.",
        "Let me spell that for you: {s}.",
        "I have the name {n}, spelled {s}.",
        "It's under {n}: {s}.",
    ]
    return framed_sentence(
        rng, CATEGORY, "spelled_name", frames,
        values={"n": name, "s": spelled},
        notes=(
            "hyphenated capitals read as letter names, each exactly once, in order; "
            "rendered per provider: spell()/<spell> for Rime/Cartesia, literal "
            "hyphens for Deepgram/OpenAI/ElevenLabs"
        ),
        spell_spans=[spelled],
    )


_MAKERS = [(_address, 40), (_url, 30), (_spelled_name, 30)]


def _make(rng: random.Random) -> dict:
    maker = rng.choices([m for m, _ in _MAKERS], weights=[w for _, w in _MAKERS])[0]
    return maker(rng)


def generate(rng: random.Random, n: int) -> list[dict]:
    return sample_unique(rng, _make, n)
