#!/usr/bin/env python3
"""Numbers as people say and write them. Stdlib only, deterministic.

    python3 numbers.py read "I sent three hundred and forty messages"   the spans, one JSON line each
    python3 numbers.py demo                                             self-check

spans(words): every number spoken in a transcript, with the words that say it. "three hundred and forty"
-> 340, "seven hundred twenty-six" -> 726, "a hundred and twenty-seven" -> 127 ("a" counts only before
hundred, thousand, million, billion), "4.5k" / "four point five k" / "4.5 thousand" -> 4500, "two and a
half" -> 2.5, "half a million" -> 500000, "minus five" -> -5 (its "minus" is the span's first word), "fifty
percent" -> 50 (kind percent). Each span is {"start", "end", "value", "kind", "text"}: start and end are indices into the words (end included, so words[end] is the last word that
says it, scale and "percent" included), kind is count, percent, money (a currency sign or word, or
MRR/ARR, after it) or duration (seconds ... years after it). Words are the caption or transcript words
as given; a string is split on spaces. Punctuation ends a number ("sign one, two" is 1 and 2), and so
does a number of the same or a bigger scale ("one hundred and two hundred" is 100 and 200). Without
punctuation neighbouring number words join ("a thousand and three" is 1003), so read the transcript's
punctuated words, not caption chunks.

written(text): the numbers written on a card, scaled: "4.5K", "EUR 4.5K", "€4.5K" -> 4500, "20K" ->
20000, "1,200" -> 1200, "50%" -> 50 (percent), "-5" -> -5 (a minus sign straight before the digits, not after a
letter or digit: "GPT-4" and "5-10" stay positive). Each keeps `raw`, the bare digits (4.5).

norm(value): the one string form both sides compare ("4500", "2.5").

check.py grounds a card's numbers in what was said with it; route.py and plan.py time graphics to a
span's words.
"""
import sys

if __name__ == "numbers":
    # Imported as the top-level `numbers` because a script in this folder put it first on sys.path
    # (home.py, review.py, presets.py ... do): the importer (statistics, fractions, numpy) wants the
    # standard library's numbers, so load that one in this module's place.
    import importlib.machinery
    import importlib.util
    import os
    _here = os.path.dirname(os.path.abspath(__file__))
    _spec = importlib.machinery.PathFinder.find_spec("numbers", [p for p in sys.path if os.path.abspath(p or ".") != _here])
    _std = importlib.util.module_from_spec(_spec)
    sys.modules["numbers"] = _std
    _spec.loader.exec_module(_std)

import json
import re

UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
BIG = {"hundred": 100, "thousand": 1000, "million": 10 ** 6, "billion": 10 ** 9}
# After a number only: "four point five k", "five grand", "2 bn".
SCALE = {"thousand": 1000, "k": 1000, "grand": 1000, "million": 10 ** 6, "billion": 10 ** 9, "bn": 10 ** 9}
SUFFIX = {"k": 1000, "m": 10 ** 6, "b": 10 ** 9, "bn": 10 ** 9}
MONEY = {"euro", "euros", "dollar", "dollars", "buck", "bucks", "pound", "pounds", "quid", "eur", "usd", "gbp", "mrr", "arr",
         "€", "$", "£"}
DURATION = {"second", "seconds", "sec", "secs", "minute", "minutes", "min", "mins", "hour", "hours", "hr", "hrs", "day",
            "days", "week", "weeks", "month", "months", "year", "years"}
FILLERS = {"uh", "um", "er", "erm", "ah", "uhm", "hmm"}
FRACTION = {"half": 0.5, "quarter": 0.25}
SIGN = {"minus", "negative"}   # before a number: "minus five degrees" is -5, never 5
STOP = ",.;:!?"
# One spoken word that is digits: "4.5k", "€4.5k", "1,200", "50%", "3x".
DIGITS = re.compile(r"([$€£])?(\d[\d,]*(?:\.\d+)?)(k|m|bn|b|%|x)?")
ASCII_DIGITS = re.compile(r"[0-9]+")   # "seven point 25"
# Digits on a card: "4.5K", "EUR 4.5K", "€ 4.5k", "20K", "50%", "2 million"; after any dot too ("No.1", "...37").
WRITTEN = re.compile(r"(?i)(?:([$€£])\s?|\b(eur|usd|gbp)\s?)?((?<![\w.])[-−])?(\d[\d,]*(?:\.\d+)?)"
                     r"(?:\s?(%)|(k|m|bn|b)\b|\s(thousand|million|billion|percent)\b)?")


def norm(v):
    """The string both sides compare: 7500.0 -> "7500", 2.5 -> "2.5"."""
    return str(round(float(v), 6)).removesuffix(".0")


def _num(v):
    v = round(float(v), 6)
    return int(v) if v == int(v) else v


def _clean(w):
    return w.lower().strip(" \"'“”‘’()[]").rstrip(STOP)


def _tokens(words):
    """[(word index, token, stop)]: a word split at its hyphens ("seventy-two"); stop marks the last
    token of a word that ends in punctuation."""
    out = []
    for i, w in enumerate(words):
        core = w.lower().strip(" \"'“”‘’()[]")
        stop = bool(core) and core[-1] in STOP
        core = core.rstrip(STOP)
        parts = [core] if DIGITS.fullmatch(core) else [p for p in core.split("-") if p]
        for j, p in enumerate(parts):
            out.append((i, p, stop and j == len(parts) - 1))
    return out


def _ahead(toks, k):
    """The scale that ends the number words from token k: 100 for "two hundred", 1000 for "fifty thousand" and
    "two hundred thousand", 0 for "fifty". Tells "one hundred and two hundred" (two numbers) from "one thousand
    and five hundred" (one)."""
    hundred = 0
    while k < len(toks):
        t = toks[k][1]
        if t in SCALE:
            return SCALE[t]
        if t == "hundred":
            hundred = 100
        elif not (t in UNITS or t in TENS or t == "and"):
            break
        if toks[k][2]:
            break
        k += 1
    return hundred


def _read(toks, i):
    """The number that starts at token i: (tokens used, value, percent, money) or None."""
    total, cur, last, big, pct, money, best = 0, 0, None, float("inf"), False, False, None
    tok = lambda k: toks[k][1] if k < len(toks) else ""   # noqa: E731
    n = i
    while n < len(toks):
        t, nxt, took = toks[n][1], tok(n + 1), 1
        lit = DIGITS.fullmatch(t)
        if lit and last is None:
            v, suf, money = float(lit[2].replace(",", "")), (lit[3] or "").lower(), bool(lit[1])
            if suf in SUFFIX:
                total, big, last = v * SUFFIX[suf], SUFFIX[suf], "scale"
            else:
                cur, last, pct = v, "digits", suf == "%"
        elif t in ("a", "an") and last is None and nxt in BIG:
            cur, last = 1, "a"
        elif t in FRACTION and last is None and nxt in ("a", "an") and tok(n + 2) in BIG and not toks[n][2]:
            cur, last, took = FRACTION[t], "a", 2   # "half a million" is 500000, never "a million"
        elif (t in UNITS or t in TENS) and last in ("hundred", "scale") and (_ahead(toks, n) == 100 if last == "hundred"
                                                                         else _ahead(toks, n) >= big):
            break   # "one hundred two hundred", "one million two million": two numbers
        elif t in UNITS and (last == "tens" and 0 < UNITS[t] < 10 or last in (None, "and", "hundred", "scale") and cur % 100 == 0):
            cur, last = cur + UNITS[t], "unit"
        elif t in TENS and last in (None, "and", "hundred", "scale") and cur % 100 == 0:
            cur, last = cur + TENS[t], "tens"
        elif t == "hundred" and (last in ("unit", "tens", "a") or last == "digits" and cur == int(cur)) and 0 < cur < 100:
            cur, last = cur * 100, "hundred"
        elif t in SCALE and last in ("unit", "tens", "hundred", "a", "digits", "point", "half") and SCALE[t] < big:
            total, cur, big, last, money = total + cur * SCALE[t], 0, SCALE[t], "scale", money or t == "grand"
        elif t == "and" and last in ("hundred", "scale") and (nxt in UNITS or nxt in TENS):
            if _ahead(toks, n + 1) == 100 if last == "hundred" else _ahead(toks, n + 1) >= big:
                break   # "between one hundred and two hundred"
            last = "and"
        elif t == "and" and last in ("unit", "tens", "hundred", "digits") and nxt in ("a", "an") and tok(n + 2) in FRACTION \
                and not toks[n + 1][2]:
            cur, last, took = cur + FRACTION[tok(n + 2)], "half", 3
        elif t == "point" and last in ("unit", "tens", "digits") and cur == int(cur) and (UNITS.get(nxt, 10) < 10 or ASCII_DIGITS.fullmatch(nxt)):
            k, digits = n + 1, ""
            while k < len(toks) and (UNITS.get(toks[k][1], 10) < 10 or ASCII_DIGITS.fullmatch(toks[k][1])):
                digits += str(UNITS.get(toks[k][1], toks[k][1]))
                k += 1
                if toks[k - 1][2]:
                    break
            cur, last, took = cur + float("0." + digits), "point", k - n
        elif t in ("percent", "%") and last not in (None, "a", "and"):
            pct, last = True, "percent"
        elif t == "per" and nxt == "cent" and last not in (None, "a", "and"):
            pct, last, took = True, "percent", 2
        else:
            break
        n += took
        if last not in ("a", "and"):
            best = (n, total + cur, pct, money)
        if toks[n - 1][2] or pct:
            break
    return best


def spans(words):
    """Every spoken number: [{"start", "end", "value", "kind", "text"}], start/end word indices (end included)."""
    words = words.split() if isinstance(words, str) else list(words)
    toks, out, i = _tokens(words), [], 0
    while i < len(toks):
        r = _read(toks, i)
        if not r:
            i += 1
            continue
        n, value, pct, money = r
        start, end = toks[i][0], toks[n - 1][0]
        after = next((_clean(w) for w in words[end + 1:] if _clean(w) not in FILLERS), "")
        before = _clean(words[start - 1]) if start else ""
        if before in SIGN and words[start - 1].rstrip()[-1:] not in STOP:
            start, value = start - 1, -value   # "minus five": the sign is said, so the span starts on it
            before = _clean(words[start - 1]) if start else ""
        kind = ("percent" if pct else "money" if money or after in MONEY or before in MONEY
                else "duration" if after in DURATION else "count")
        out.append({"start": start, "end": end, "value": _num(value), "kind": kind, "text": " ".join(words[start:end + 1])})
        i = n
    return out


def written(text):
    """The numbers written in a display text: [{"value", "raw", "kind", "text"}], value scaled by K/M/B or
    thousand/million, raw the bare digits."""
    out = []
    for m in WRITTEN.finditer(text):
        raw = float(m[4].rstrip(",").replace(",", "")) * (-1 if m[3] else 1)
        scale = SUFFIX.get((m[6] or "").lower()) or SCALE.get((m[7] or "").lower()) or 1
        pct = bool(m[5]) or (m[7] or "").lower() == "percent"
        out.append({"value": _num(raw * scale), "raw": _num(raw), "kind": "percent" if pct else "money" if m[1] or m[2] else "count",
                    "text": m[0].strip()})
    return out


# A sample take (made up), line by line: what was said, and the numbers in it as (value, kind, start, end).
# It has the shapes a real talking-head take has. A line ends where the transcript broke it: "seven hundred
# twenty-six," is money only once the next line's "uh, dollars" follows (the whole take, below).
SAMPLE_TAKE = [
    ("Our ice cream van has nine flavours, and we added two this summer.", [(9, "count", 5, 5), (2, "count", 10, 10)]),
    ("Last month it took, uh, four hundred and eighty-one dollars on one Saturday.", [(481, "money", 5, 8), (1, "count", 11, 11)]),
    ("The best seller is mango, and about, uh, a hundred and twenty-seven, uh, people asked for it by name.",
     [(127, "count", 8, 11)]),
    ("We tested eighteen recipes before that one worked.", [(18, "count", 2, 2), (1, "count", 6, 6)]),
    ("Then a school booked us for a 3.5k dollars party in two and a half weeks.", [(3500, "money", 7, 7), (2.5, "duration", 11, 14)]),
    ("We handed out three hundred and forty leaflets in six towns.", [(340, "count", 3, 6), (6, "count", 9, 9)]),
    ("Sixty-three regulars now pay seven hundred twenty-six,", [(63, "count", 0, 0), (726, "count", 4, 6)]),
    ("uh, dollars a year for a pass.", []),
    ("That puts us at forty percent of our 20k target for the season.", [(40, "percent", 4, 5), (20000, "count", 8, 8)]),
    ("Next summer we want 4.5k dollars a week in three and a half months.", [(4500, "money", 4, 4), (3.5, "duration", 9, 12)]),
    ("We sold half a million scoops, even at minus two degrees.", [(500000, "count", 2, 4), (-2, "count", 8, 9)]),
    ("See you at the beach.", []),
]


def demo():
    for line, want in SAMPLE_TAKE:
        got = [(s["value"], s["kind"], s["start"], s["end"]) for s in spans(line)]
        assert got == want, (line, got)
    # the whole take as one run of words: every number in it, in order, and what it counts
    every = [(s["value"], s["kind"]) for s in spans(" ".join(line for line, _ in SAMPLE_TAKE))]
    assert every == [(9, "count"), (2, "count"), (481, "money"), (1, "count"), (127, "count"), (18, "count"), (1, "count"),
                     (3500, "money"), (2.5, "duration"), (340, "count"), (6, "count"), (63, "count"), (726, "money"),
                     (40, "percent"), (20000, "count"), (4500, "money"), (3.5, "duration"), (500000, "count"), (-2, "count")], every
    s = spans("about a hundred and twenty-seven, uh, door knocks".split())[0]
    assert (s["start"], s["end"], s["text"]) == (1, 4, "a hundred and twenty-seven,"), s
    one = lambda t: [(x["value"], x["kind"]) for x in spans(t)]   # noqa: E731
    for said, want in [("four point five k", 4500), ("4.5 thousand", 4500), ("4.5k", 4500), ("3.5k", 3500), ("20k", 20000),
                       ("sixty-three", 63), ("sixty three", 63), ("eighteen", 18), ("two and a half", 2.5),
                       ("a hundred and twenty-seven", 127), ("seven hundred twenty-six", 726), ("two thousand and twenty four", 2024),
                       ("three million two hundred thousand", 3200000), ("1,200", 1200), ("zero", 0), ("a thousand", 1000),
                       ("seven point 25", 7.25)]:
        assert [v for v, _ in one(said)] == [want], (said, one(said))
    assert one("fifty percent") == [(50, "percent")] and one("50%") == [(50, "percent")] and one("ten per cent") == [(10, "percent")]
    assert one("five grand") == [(5000, "money")] and one("€4.5k") == [(4500, "money")] and one("$20 a month") == [(20, "money")]
    assert one("in three days") == [(3, "duration")] and one("twelve dollars") == [(12, "money")]
    # "a" alone is not one; separate numbers stay separate; punctuation ends a number
    assert one("give me a follow") == [] and one("a half") == [] and one("one two three") == [(1, "count"), (2, "count"), (3, "count")]
    assert one("twenty twenty four") == [(20, "count"), (24, "count")] and one("one, two") == [(1, "count"), (2, "count")]
    assert one("two hundred and") == [(200, "count")] and one("seven point") == [(7, "count")]
    # a number of the same or a bigger scale starts a new one, "and" or not; a smaller one joins
    for said, want in [("between one hundred and two hundred", [100, 200]), ("one hundred two hundred", [100, 200]),
                       ("one million two million", [1000000, 2000000]), ("one thousand and five hundred", [1500]),
                       ("two hundred fifty thousand", [250000]), ("one hundred twenty thousand", [120000]),
                       ("I sent 5 hundred messages", [500]), ("a thousand. And three people", [1000, 3])]:
        assert [v for v, _ in one(said)] == want, (said, one(said))
    w = lambda t: [(x["value"], x["raw"], x["kind"]) for x in written(t)]   # noqa: E731
    assert w("4.5K") == [(4500, 4.5, "count")] and w("€4.5K") == w("EUR 4.5K") == [(4500, 4.5, "money")], w("€4.5K")
    assert w("20K") == [(20000, 20, "count")] and w("3.5k") == [(3500, 3.5, "count")] and w("340") == [(340, 340, "count")]
    assert w("50%") == [(50, 50, "percent")] and w("1,200 users, 3x") == [(1200, 1200, "count"), (3, 3, "count")]
    assert w("2 million") == [(2000000, 2, "count")] and w("5 min") == [(5, 5, "count")] and w("power2.out") == [(2, 2, "count")]
    assert w("No.1") == [(1, 1, "count")] and w("...37 clients") == w("Ep.37") == [(37, 37, "count")]   # a dot before is no decimal
    # "half a <scale>" is half of it; a said minus is the number's sign (both drawn wrong before: 1M, 5)
    assert one("half a million") == [(500000, "count")] and one("half a thousand dollars") == [(500, "money")]
    assert one("minus five degrees") == [(-5, "count")] and one("negative 3 percent") == [(-3, "percent")]
    assert one("half of them") == [] and one("minus, five") == [(5, "count")]
    assert w("-5") == [(-5, -5, "count")] and w("GPT-4") == [(4, 4, "count")] and w("5-10 days") == [(5, 5, "count"), (10, 10, "count")]
    assert norm(4500.0) == "4500" and norm(2.5) == "2.5" and norm(0.1 * 3) == "0.3"
    # run from this folder (sys.path[0] here), the standard library still gets its own numbers module
    import subprocess
    from pathlib import Path
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import statistics, fractions; "
                        "print(statistics.median([1, 2, 3]), fractions.Fraction(1, 2))", str(Path(__file__).resolve().parent)],
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.split() == ["2", "1/2"], r.stderr
    print(f"demo ok ({len(every)} numbers in the sample take)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["demo"]:
        demo()
    elif len(a) == 2 and a[0] == "read":
        for s in spans(a[1]):
            print(json.dumps(s))
    else:
        sys.exit(__doc__)
