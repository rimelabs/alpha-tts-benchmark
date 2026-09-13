"""Render provider-specific synthesis input from canonical corpus text.

The corpus stores the script shown to listeners and its ``spell_spans``.
Rendering expresses those spans using each provider's reading controls:
Rime spell(), SSML say-as, Cartesia spell tags, or plain-text character
sequences. ElevenLabs receives letter names and digits written as words.
A leading display hash is omitted in the configured provider styles.
Spelled-name hyphens are visual separators, not spoken content.

Preview the inputs for a corpus:

    uv run python -m corpus.render --style plaintext data/alphabench.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STYLES = (
    "rime",
    "ssml",
    "cartesia",
    "plaintext",
    "deepgram",
    "elevenlabs",
)

DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}

# A span already written letter-by-letter in the canonical text, e.g.
# "C-A-L-L-A-H-A-N" (name spelling). Codes are fused tokens,
# so any single-character hyphen chain is a pre-spelled span.
PRESPELLED = re.compile(r"^[A-Z](?:-[A-Z])+$")


def hyphenate(span: str, joiner: str = "-") -> str:
    """Proposed plain-text standard: characters hyphen-joined, separators
    made audible.

    Within a group, every character is joined by hyphens. In-code hyphens
    are part of the code and are verbalized as the word "dash"; whitespace
    is pure grouping and becomes a comma pause.

        L2X-8XH               ->  L-2-X, dash, 8-X-H
        XQ47B                 ->  X-Q-4-7-B
        1Z B8B D6P 62         ->  1-Z, B-8-B, D-6-P, 6-2
    """
    parts: list[str] = []
    group: list[str] = []

    def flush() -> None:
        if group:
            parts.append(joiner.join(group))
            group.clear()

    for ch in span:
        if ch.isalnum():
            group.append(ch)
        elif ch == "-":
            flush()
            parts.append("dash")
        elif ch.isspace():
            flush()
        # any other character is dropped
    flush()
    return ", ".join(parts)


def elevenlabs_spoken_form(span: str) -> str:
    """Write the intended character sequence without separator punctuation.

    Commas separate characters, digits are written as words, and only a
    hyphen present in the underlying identifier becomes the word "dash".
    Visual separators in spelled names are removed before this function.
    """
    tokens: list[str] = []
    for ch in span:
        if ch.isdigit():
            tokens.append(DIGIT_WORDS[ch])
        elif ch.isalpha():
            tokens.append(ch.upper())
        elif ch == "-":
            tokens.append("dash")
        # Whitespace and a leading hash are grouping or display syntax. They
        # are not part of AlphaBench's required spoken character sequence.
    return ", ".join(tokens)


def render_span(span: str, style: str) -> str:
    if PRESPELLED.match(span):
        # Pre-spelled name (C-A-L-L-A-H-A-N): the hyphens are joiners, not
        # part of the content — no "dash" should ever be spoken. Providers
        # with reading control get the fused name inside their tag; every
        # plaintext style and Deepgram keep the visual hyphens literal.
        letters = span.replace("-", "")
        if style == "rime":
            return f"spell({letters})"
        if style == "ssml":
            return f'<say-as interpret-as="characters">{letters}</say-as>'
        if style == "cartesia":
            return f"<spell>{letters}</spell>"
        if style in ("plaintext", "deepgram"):
            return span
        if style == "elevenlabs":
            return elevenlabs_spoken_form(letters)
        raise ValueError(f"unknown style {style!r}; expected one of {STYLES}")
    if style == "rime":
        # One spell() around the whole token: whitespace is stripped
        # (spell() does its own chunking), hyphens stay inside. A leading
        # '#' absorbed from the surrounding text is dropped, matching the
        # plain-text standard — '#' omission is a passing reading and
        # keeps the spoken content of all conditioned inputs equivalent.
        return f"spell({''.join(span.split()).replace('#', '')})"
    if style == "ssml":
        return f'<say-as interpret-as="characters">{span}</say-as>'
    if style == "cartesia":
        # Use Cartesia's character tag for each segment and verbalize
        # identifier hyphens between tags. Omit a leading display hash.
        segments = span.replace("#", "").split("-")
        return ", dash, ".join(f"<spell>{seg}</spell>" for seg in segments)
    if style == "plaintext":
        return hyphenate(span)
    if style == "deepgram":
        # Separate characters with commas; identifier hyphens become
        # the word "dash" through the shared formatter.
        return hyphenate(span, joiner=", ")
    if style == "elevenlabs":
        return elevenlabs_spoken_form(span)
    raise ValueError(f"unknown style {style!r}; expected one of {STYLES}")


def render_text(text: str, spell_spans: list[str], style: str) -> str:
    for span in spell_spans:
        if span not in text:
            raise ValueError(f"spell span {span!r} not found in text {text!r}")
        target = span
        if style in (
            "rime",
            "plaintext",
            "cartesia",
            "deepgram",
            "elevenlabs",
        ) and f"#{span}" in text:
            # Absorb and omit the display hash with the span. The corpus
            # notes permit this reading without spoken symbol content.
            target = f"#{span}"
        text = text.replace(target, render_span(target, style), 1)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--style", choices=STYLES, required=True)
    args = parser.parse_args()

    for line in args.manifest.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        rendered = render_text(row["text"], row.get("spell_spans", []), args.style)
        json.dump({"id": row["id"], "input": rendered}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
