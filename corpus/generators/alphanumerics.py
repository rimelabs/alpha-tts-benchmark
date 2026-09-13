"""Alphanumeric sequences: confirmation codes, order and tracking numbers,
flight numbers, license plates, policy and case identifiers.

Every code is a single fused token — no hyphens, no spaces, no
'#', no separators of any kind (e.g. XED91580BC, BBB333ASDF). Separator
verbalization varies across providers (dash spoken vs. silent, '#' as
hash/hashtag/number), which contaminates fidelity measurement with
normalization ambiguity; fused tokens make every reading judgment
unambiguous. Confusable characters (O/0, I/1, B/8) and deliberate
character runs (BBB, 333) are included on purpose — they are the actual
failure surface.

Every code is recorded in ``spell_spans`` so provider-specific input can
be rendered with the preferred reading control (see ``corpus.render``).

Codes containing readable English words (promo codes like SAVE20) remain
excluded from the main corpus; ``generate_ambiguous`` feeds the separate
ambiguity bench.
"""

from __future__ import annotations

import random

from . import framed_sentence, sample_unique

CATEGORY = "alphanumerics"

# Includes visually/acoustically confusable characters on purpose.
LETTERS = "ABCDEFGHJKLMNPQRSTVWXYZIO"
DIGITS = "0123456789"

AIRLINES = [("UA", "United"), ("DL", "Delta"), ("AA", "American"), ("AS", "Alaska"), ("B6", "JetBlue"), ("WN", "Southwest")]

PROMO_WORDS = ["SAVE", "SPRING", "WELCOME", "LOYAL", "SHIP", "FLASH", "VIP", "RENEW"]

SPELL_NOTE = "code read character by character, each exactly once, in order; digits individually"


def _chars(rng: random.Random, pool: str, k: int) -> str:
    return "".join(rng.choice(pool) for _ in range(k))


def _confirmation(rng: random.Random) -> dict:
    style = rng.randrange(4)
    if style == 0:
        code = f"{_chars(rng, LETTERS, 3)}{_chars(rng, DIGITS, 4)}"
    elif style == 1:
        code = _chars(rng, LETTERS + DIGITS, 6)
    elif style == 2:
        code = f"{_chars(rng, LETTERS, 3)}{_chars(rng, DIGITS, 5)}{_chars(rng, LETTERS, 2)}"
    else:
        # Deliberate runs (BBB333ASDF): repetition is a core stress case.
        code = f"{rng.choice(LETTERS) * 3}{rng.choice(DIGITS) * 3}{_chars(rng, LETTERS, 4)}"
    frames = [
        "Your confirmation code is {c}; you'll need it at check-in.",
        "I've booked that for you — the confirmation number is {c}.",
        "Please write down this reference: {c}.",
        "The cancellation code {c} was sent to your email as well.",
        "At the airport kiosk, enter {c} when it asks for the booking code.",
        "{c} is the only confirmation code associated with this reservation.",
        "Before we disconnect, please read back confirmation code {c}.",
        "The agent corrected the confirmation code to {c}, not the earlier one.",
        "For passenger two, the confirmation code in the itinerary is {c}.",
    ]
    return framed_sentence(
        rng, CATEGORY, "confirmation_code", frames, values={"c": code},
        notes=SPELL_NOTE, spell_spans=[code],
    )


def _order(rng: random.Random) -> dict:
    num = f"{_chars(rng, LETTERS, 2)}{rng.randint(10000000, 99999999)}"
    frames = [
        "I'm looking at order {c} right now.",
        "Order {c} shipped out yesterday afternoon.",
        "Can you confirm that order {c} is the one you'd like to return?",
        "The refund for order {c} was processed this morning.",
        "The warehouse label lists {c} as the order identifier.",
        "For the damaged item, use order number {c} on the claim form.",
        "I found two purchases, but {c} is the order still awaiting delivery.",
        "Before I cancel anything, please read order {c} back to me.",
        "Was {c} the order placed through the mobile app?",
    ]
    return framed_sentence(
        rng, CATEGORY, "order_number", frames, values={"c": num},
        notes=SPELL_NOTE, spell_spans=[num],
    )


def _tracking(rng: random.Random) -> dict:
    style = rng.randrange(2)
    if style == 0:
        code = f"1Z{_chars(rng, LETTERS + DIGITS, 6)}{rng.randint(10000000, 99999999)}"
    else:
        code = f"{_chars(rng, LETTERS, 2)}{rng.randint(100000000, 999999999)}US"
    frames = [
        "Your tracking number is {c}.",
        "According to the carrier, {c} was delivered at 2:14 PM.",
        "Go ahead and paste {c} into the tracking page.",
        "The shipping label shows tracking identifier {c} beneath the barcode.",
        "For the second parcel, use {c} rather than the number in the first email.",
        "Can you read tracking number {c} back one character at a time?",
        "Once {c} appears in the carrier app, alerts will begin automatically.",
        "Tracking number {c} has not received its first scan yet.",
    ]
    return framed_sentence(
        rng, CATEGORY, "tracking_number", frames, values={"c": code},
        notes=f"long sequence; watch for skipped or duplicated characters; {SPELL_NOTE}",
        spell_spans=[code],
    )


def _flight(rng: random.Random) -> dict:
    code, name = rng.choice(AIRLINES)
    fused = f"{code}{rng.randint(4, 2899)}"
    frames = [
        "You're confirmed on {n} flight {f}, departing at 7:35 AM.",
        "Unfortunately {n} flight {f} has been delayed by about ninety minutes.",
        "I can rebook you on {n} flight {f} at no additional charge.",
        "The departure board now lists {n} flight {f} at gate C12.",
        "Is {n} flight {f} the connection you are trying to change?",
        "For the return trip, your itinerary shows {n} flight {f}.",
        "The text alert refers to {n} flight {f}, not the earlier departure.",
        "Please tell the gate agent that you are ticketed on {n} flight {f}.",
    ]
    return framed_sentence(
        rng, CATEGORY, "flight_number", frames,
        values={"n": name, "f": fused},
        notes="carrier code read as letters; flight digits read individually or grouped",
        spell_spans=[fused],
    )


def _plate(rng: random.Random) -> dict:
    plate = f"{rng.randint(1, 9)}{_chars(rng, LETTERS, 3)}{rng.randint(100, 999)}"
    frames = [
        "The vehicle is registered under plate {p}.",
        "Can you verify the license plate? I have {p} on file.",
        "The tow lot released the car with plate number {p} this morning.",
        "The parking citation records the plate as {p}.",
        "At the gate, enter license plate {p} on the visitor form.",
        "Is {p} the plate attached to the replacement vehicle?",
        "The officer corrected the plate to {p}, not the number in the first report.",
        "Please read back plate {p} before I submit the registration change.",
    ]
    return framed_sentence(
        rng, CATEGORY, "license_plate", frames, values={"p": plate},
        notes=SPELL_NOTE, spell_spans=[plate],
    )


def _policy(rng: random.Random) -> dict:
    ident = f"{_chars(rng, LETTERS, 2)}{rng.randint(100000000, 999999999)}"
    frames = [
        "Your policy number is {p}, effective the first of next month.",
        "I've opened case {p} for this issue.",
        "The claim was filed under reference {p}.",
        "Your member ID, {p}, is printed on the back of the card.",
        "Use identifier {p} when you upload the supporting documents.",
        "The letter lists {p} as the policy tied to this address.",
        "Can you confirm whether case {p} concerns the billing dispute?",
        "The adjuster reassigned the claim to reference {p} yesterday.",
        "Before I transfer you, please write down case number {p}.",
    ]
    return framed_sentence(
        rng, CATEGORY, "policy_case_id", frames, values={"p": ident},
        notes=SPELL_NOTE, spell_spans=[ident],
    )


# Name spelling: first/last names spelled letter by letter, as a support
# agent confirms a caller's name. Canonical text carries the hyphenated
# uppercase form (L-E-I-L-A); corpus.render maps it to each provider's
# reading control (spell()/<spell>) or leaves the hyphens literal.
# Double letters (FF, NN, TT) included on purpose — like repeated runs in
# codes, they are a real skip/merge failure surface.
SPELL_FIRST_NAMES = [
    "LEILA", "CLAUDE", "MAEVE", "GREGOR", "PHILLIP", "ANNETTE", "HARRIET",
    "SIOBHAN", "DMITRI", "YVONNE", "ISLA", "QUENTIN", "BEATRIX", "OTTO",
    "VIVIENNE", "KENJI",
]
SPELL_LAST_NAMES = [
    "CALLAHAN", "MCCONNELL", "GRIFFITH", "KENNEDY", "LLOYD", "PHILLIPS",
    "VASQUEZ", "OYELARAN", "SCHMIDT", "BJORNSTAD", "WHITTAKER", "DUBOIS",
    "MATTHEWS", "OKONKWO", "PRZYBYLSKI", "HUANG",
]

SPELL_NAME_NOTE = (
    "hyphenated capitals read as letter names, each exactly once, in order; "
    "rendered per provider: spell()/<spell> for Rime/Cartesia, literal "
    "hyphens for Deepgram/OpenAI/ElevenLabs"
)


def _hyph(name: str) -> str:
    return "-".join(name)


def _spelled_name(rng: random.Random) -> dict:
    style = rng.randrange(4)
    if style == 0:
        first = rng.choice(SPELL_FIRST_NAMES)
        last = rng.choice(SPELL_LAST_NAMES)
        sf, sl = _hyph(first), _hyph(last)
        frames = [
            "Yes, that's first name {sf} and last name {sl}.",
            "Let me read that back: first name {sf}, last name {sl}.",
            "I have first name {sf} and last name {sl} — is that right?",
            "The form separates the name as {sf} for first and {sl} for last.",
        ]
        return framed_sentence(
            rng, CATEGORY, "name_spelling", frames,
            values={"sf": sf, "sl": sl}, notes=SPELL_NAME_NOTE,
            spell_spans=[sf, sl],
        )
    if style == 1:
        name = rng.choice(SPELL_FIRST_NAMES)
        s = _hyph(name)
        frames = [
            "Yes, that's spelled {s}.",
            "The first name is spelled {s}.",
            "Correct — {s}, like it sounds.",
            "For the badge, enter the first name as {s}.",
        ]
    elif style == 2:
        name = rng.choice(SPELL_LAST_NAMES)
        s = _hyph(name)
        frames = [
            "The last name is spelled {s}.",
            "That's {s} on the account.",
            "One more time, the surname: {s}.",
            "The reservation files the family name under {s}.",
        ]
    else:
        name = rng.choice(SPELL_FIRST_NAMES + SPELL_LAST_NAMES)
        s = _hyph(name)
        frames = [
            "Can you confirm the spelling? I have {s}.",
            "I'll spell the name for you: {s}.",
            "The name comes up as {s} in our system.",
            "Please search for the customer under the spelling {s}.",
        ]
    return framed_sentence(
        rng, CATEGORY, "name_spelling", frames, values={"s": s},
        notes=SPELL_NAME_NOTE, spell_spans=[s],
    )


def generate_spelled(rng: random.Random, n: int) -> list[dict]:
    """Spelled first/last names for alphabench's name_spelling subcategory."""
    return _sample_balanced_frames(rng, _spelled_name, n, frame_count=16)


CONFUSABLE_PAIRS = ["PT", "BD", "MN", "FV", "SZ", "YI", "GK", "BV"]


def _confusable(rng: random.Random) -> dict:
    length = rng.randint(8, 12)
    chars = []
    pair = rng.choice(CONFUSABLE_PAIRS)
    pos = rng.randint(0, max(0, length - 3))
    for i in range(length):
        if i == pos:
            chars.append(pair[0])
        elif i == pos + 1:
            chars.append(pair[1])
        else:
            chars.append(rng.choice(LETTERS + DIGITS))
    # Guarantee at least one more confusable pair somewhere else.
    pair2 = rng.choice(CONFUSABLE_PAIRS)
    slot = rng.choice([j for j in range(length - 1) if j != pos and j != pos + 1])
    chars[slot] = pair2[0]
    if slot + 1 not in (pos, pos + 1):
        chars[slot + 1] = pair2[1]
    code = "".join(chars)
    frames = [
        "The reference number is {c}.",
        "Your verification code is {c}.",
        "I have code {c} on the account.",
        "Please confirm: {c}.",
        "Read the two similar letter pairs in {c} carefully.",
        "The corrected verification string is {c}, not the earlier code.",
        "Before continuing, enter {c} exactly as it appears on the screen.",
        "Does the account display reference {c} in the security section?",
    ]
    return framed_sentence(
        rng, CATEGORY, "confusable", frames, values={"c": code},
        notes=f"acoustically confusable letter pairs; {SPELL_NOTE}",
        spell_spans=[code],
    )


def _long_code(rng: random.Random) -> dict:
    length = rng.randint(20, 25)
    code = _chars(rng, LETTERS + DIGITS, length)
    frames = [
        "The full reference is {c}.",
        "Your case ID is {c} — please keep it handy.",
        "The transaction hash is {c}.",
        "I see authorization code {c} on file.",
        "Read this complete identifier without pausing: {c}.",
        "The audit log ends with the long authorization string {c}.",
        "Please compare every character in {c} with the value on your receipt.",
        "The second record, not the first, uses transaction identifier {c}.",
    ]
    return framed_sentence(
        rng, CATEGORY, "long_code", frames, values={"c": code},
        notes=(
            f"very long sequence ({length} characters); watch for skipped or "
            f"duplicated characters; {SPELL_NOTE}"
        ),
        spell_spans=[code],
    )


def _promo(rng: random.Random) -> dict:
    code = f"{rng.choice(PROMO_WORDS)}{rng.choice(['10', '15', '20', '25', '30'])}"
    frames = [
        "Use code {c} at checkout for your discount.",
        "I've applied promo code {c} to your cart.",
        "That coupon, {c}, expires at midnight on Sunday.",
    ]
    return framed_sentence(
        rng, CATEGORY, "promo_code", frames, values={"c": code},
        notes=(
            "ambiguous by design: word part may be read as a word ('save twenty') "
            "or spelled ('S-A-V-E-2-0'); excluded from the main corpus"
        ),
        spell_spans=[code],
    )


_MAKERS = [
    (_confirmation, 24),
    (_order, 20),
    (_tracking, 14),
    (_flight, 15),
    (_plate, 12),
    (_policy, 15),
]

_STANDARD_MAKERS = {
    "confirmation_code": _confirmation,
    "order_number": _order,
    "tracking_number": _tracking,
    "flight_number": _flight,
    "license_plate": _plate,
    "policy_case_id": _policy,
    "confusable": _confusable,
    "long_code": _long_code,
}

_FRAME_COUNTS = {
    "confirmation_code": 9,
    "order_number": 9,
    "tracking_number": 8,
    "flight_number": 8,
    "license_plate": 8,
    "policy_case_id": 9,
    "confusable": 8,
    "long_code": 8,
}


def _sample_balanced_frames(
    rng: random.Random,
    make,
    n: int,
    *,
    frame_count: int,
    max_attempts: int = 200_000,
) -> list[dict]:
    """Fill every source frame, with sizes differing by at most one script."""
    by_template: dict[str, list[dict]] = {}
    seen: set[str] = set()
    for _ in range(max_attempts):
        row = make(rng)
        if row["text"] in seen:
            continue
        seen.add(row["text"])
        by_template.setdefault(row["template_id"], []).append(row)
        if len(by_template) > frame_count:
            raise ValueError(
                f"generator exposed more than {frame_count} registered frames"
            )
        if len(by_template) != frame_count:
            continue
        ordered = sorted(by_template)
        quotas = {
            template_id: n // frame_count + (index < n % frame_count)
            for index, template_id in enumerate(ordered)
        }
        if all(
            len(by_template[template_id]) >= quotas[template_id]
            for template_id in ordered
        ):
            rows = [
                row
                for template_id in ordered
                for row in by_template[template_id][: quotas[template_id]]
            ]
            if len(rows) != n:
                raise AssertionError(f"balanced selection returned {len(rows)} rows")
            return rows
    raise RuntimeError(
        f"could not balance {n} rows across {frame_count} source frames"
    )


def _make(rng: random.Random) -> dict:
    maker = rng.choices([m for m, _ in _MAKERS], weights=[w for _, w in _MAKERS])[0]
    return maker(rng)


def generate(rng: random.Random, n: int) -> list[dict]:
    return sample_unique(rng, _make, n)


def generate_subcategory(
    rng: random.Random,
    subcategory: str,
    n: int,
) -> list[dict]:
    """Generate an exact registered count for one standard AlphaBench class."""
    try:
        maker = _STANDARD_MAKERS[subcategory]
    except KeyError as exc:
        raise ValueError(f"unknown AlphaBench subcategory: {subcategory}") from exc
    return _sample_balanced_frames(
        rng,
        maker,
        n,
        frame_count=_FRAME_COUNTS[subcategory],
    )


def generate_ambiguous(rng: random.Random, n: int) -> list[dict]:
    """Word-like codes (SAVE20 etc.) for the separate ambiguity bench."""
    return sample_unique(rng, _promo, n)
