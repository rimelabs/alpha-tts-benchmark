# Text-Normalization Cases Covered by the Evaluation Corpus

Reference examples of written-form patterns and expected readings. The exact
frozen prompts are the corpus files listed in `configs/run_design.json`;
this reference does not add prompts or change the rendering code.

Code spans use provider-specific reading controls in
[corpus/render.py](../corpus/render.py). Rime receives a complete code token
inside `spell()`, with whitespace and display hashes removed. For example,
`MDB5416` becomes `spell(MDB5416)`. The other providers use their configured
character tags or plain-text character sequences. Text outside marked spans
remains canonical text. Spelled names follow the renderer's separate handling
of visual hyphens.

## Phone numbers (all fictional 555-01XX)

| # | Case | Written form | Expected reading |
|---|---|---|---|
| 1 | NANP, parenthesized | `(617) 555-0100` | digits in order; grouped or individual both fine |
| 2 | NANP, hyphenated | `415-555-0192` | same |
| 3 | Toll-free, leading 1 | `1-833-555-0130` | "one eight three three…" or "one, eight, three, three…" |
| 4 | Toll-free, parenthesized | `1 (877) 555-0127` | same |
| 5 | Toll-free, bare | `844-555-0155` | same |
| 6 | E.164, spaces | `+1 720 555 0138` | "+" as "plus" or absorbed into "one" |
| 7 | E.164, hyphens | `+1-212-555-0135` | same |
| 8 | Extension | `…555-0127, extension 8108` | extension digits individually or as pairs |
| 9 | Emergency short code | `call 911` (in prose) | "nine one one" |

Deliberately excluded: dot-separated numbers (`952.555.0130`).

## Alphanumerics (arrive inside `spell()`; fused, separator-free)

| # | Case | Written form (canonical) | Expected reading |
|---|---|---|---|
| 10 | Letters+digits code | `MDB5416` | every character individually |
| 11 | Unstructured 6-char | `SMPNK7` | every character individually (no word-reading of substrings) |
| 12 | Long mixed code | `XED91580BC` (3L+5D+2L) | every character, exactly once, in order |
| 13 | Deliberate runs | `BBB333ASDF` | repeated characters each spoken (deletion/insertion stress) |
| 14 | Order number | `order BL87792148` | 2 letters + 8 digits, all individual |
| 15 | UPS-style tracking | `1ZK7M2Q471852963` | 16 fused characters; watch for skipped/duplicated characters |
| 16 | USPS-style tracking | `QD519254933US` | every character; trailing "US" as letters, not "us" |
| 17 | Flight number | `B62441`, `UA1189` | letters as letters, digits individually or grouped |
| 18 | License plate | `5OXK616` | every character; `O` vs `0` distinction matters |
| 19 | Policy/case/member ID | `IP889944416` | 2 letters + 9 digits, all individual |
| 20 | Confusable characters | `I`/`1`, `O`/`0`, `B`/`8` adjacencies | must not merge or swap |

Alphanumeric code tokens in this corpus contain no separators (`-`, spaces,
or `#`). This keeps separator verbalization outside the code-reading task.
Spelled names retain their visual separators.

Held out (separate ambiguity bench, not in main corpus): word-like codes
(`SAVE20`) where "save twenty" vs. "S-A-V-E, two, zero" are both defensible.

## Dates & times

| # | Case | Written form | Expected reading |
|---|---|---|---|
| 21 | Month D, YYYY | `April 13, 2026` | "April thirteenth, twenty twenty-six" |
| 22 | Numeric date | `10/21/2025` | as a date — never "ten twenty-firsts" or a fraction |
| 23 | ISO date | `2027-08-11` | as a date — never "minus" |
| 24 | Ordinal-first | `the 21st of April` | ordinal suffix honored |
| 25 | Weekday + ordinal | `Tuesday, June 9th` | ordinal honored |
| 26 | 12-hour time | `2:14 PM`, `5:59 a.m.` | both AM/PM casings; `:00` as "o'clock" or omitted |
| 27 | 24-hour time | `17:50` (always ≥ 13:00) | "five fifty PM" or "seventeen fifty" |
| 28 | Time + zone word | `10:00 AM Central` | zone as written |
| 29 | Time + zone abbrev | `1:10 PM EST`, `ET`, `CT`, `PT`, `CDT` | letters or expanded |
| 30 | Word times | `noon`, `midnight`, `4 o'clock` | as written |
| 31 | Date range, en dash | `June 7–11` | "June seventh to (through) the eleventh" — both endpoints |
| 32 | Date range, worded | `from September 12 to September 15` | both endpoints |
| 33 | Time range | `between 9:00 AM and 1:30 PM` | both endpoints |
| 34 | Duration | `7 to 10 business days`, `24 to 48 hours`, `90 days` | cardinals |

## Amounts & units

| # | Case | Written form | Expected reading |
|---|---|---|---|
| 35 | Dollars and cents | `$46.44` | "forty-six dollars and forty-four cents" |
| 36 | Thousands separator | `$8,225.80` | full magnitude + cents; comma never spoken |
| 37 | Price point | `$199.99` | "one ninety-nine ninety-nine" or full form |
| 38 | Whole dollars | `$115` | no spurious cents |
| 39 | Whole percent | `10%` | "ten percent" |
| 40 | Decimal percent | `21.25%` | "twenty-one point two five percent" — decimal digits individually |
| 41 | Rate + APR | `5.3% APR` | "A-P-R" as letters |
| 42 | Decimal distance | `18.8 miles` | "eighteen point eight" |
| 43 | Dosage | `1000 mg` | "milligrams" expanded |
| 44 | Temperature | `83°F` | "eighty-three degrees (Fahrenheit)" |
| 45 | Data size | `500 GB` | "gigabytes" or "G-B" |
| 46 | Decimal weight | `42.3 pounds` | "forty-two point three" |
| 47 | Energy | `250 kWh` | "kilowatt-hours" or letters |
| 48 | X of Y | `installment 1 of 19` | two cardinals |

## Addresses & contact

| # | Case | Written form | Expected reading |
|---|---|---|---|
| 49 | Full street address | `673 Bristol Lane, Minneapolis, MN 55401` | house number as cardinal or grouped; `MN` letters or "Minnesota"; ZIP digits individually |
| 50 | 4-digit house number | `3409 Maple Court` | "thirty-four oh nine" or digits |
| 51 | Unit designator | `Apt 17`, `Suite C`, `Unit 2B` | designator + value spoken; `2B` as "two B" |
| 52 | Role email | `service@example.org` | "@" as "at", "." as "dot" |
| 53 | Initial-dot-surname email | `y.szymanski@example.com` | leading single letter, then "dot", then surname pronounced (not spelled) |
| 54 | Name+digits email | `elena67@example.net` | digits spoken before the "at" |
| 55 | URL with www | `www.example.com/account` | "www" as letters (or "triple-w"), dots and "slash" spoken |
| 56 | Bare domain + path | `example.com/support/chat` | both slashes spoken |
| 57 | Bare domain | `example.com` | "example dot com" |
| 58 | Spelled name | `O-K-A-F-O-R` | letter names, each once, in order; provider-specific spelling control |

## Outside corpus coverage

The corpus does not cover these patterns:

- Vanity numbers (`1-800-FLOWERS`)
- Card/account last-4 ("card ending in 6411")
- Large-magnitude money (`$1.5 million`)
- Negative amounts / credits (`-$25.00`)
- Fractions (`½`, `3/4 inch` — currently only dates use slash)
- Abbreviation ambiguity (`Dr.` drive/doctor, `St.` street/saint)
- `No. 12` ("number twelve")
- Ordinal-only ("you're 3rd in line")
- Roman numerals (`Section IV`)
- Serial numbers with special characters (`SN: 88-A/4`)
- Currency other than USD (`€45`, `£30`)
- Mixed-case codes (`aB3x9k`) — corpus codes are uppercase-only
