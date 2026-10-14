#!/usr/bin/env python3
"""The number beats of a talking-head video, found from its words: kinetic visuals.json beats, no hand-written list.

    python3 kinetic_beats.py find edits/NAME            every candidate, its score, kept or why not (writes nothing)
    python3 kinetic_beats.py write edits/NAME [--force] the kept beats into visuals.json (plan.py runs this itself)
    python3 kinetic_beats.py words FILE.json [--per-min N] [--json]   any word-timed transcript in, its beats out
    python3 kinetic_beats.py demo                       self-check (made-up takes)

Runs when the style opts into the kinetic family (style.json "graphics": {"kinetic": true}); plan.py calls refresh()
before it reads visuals.json, so every new video gets its number beats with nobody writing them
(references/kinetic.md "Automatic beats"). Only number beats: kinetic_title and cta_follow are never placed here.

1. Candidates. numbers.py spans() over the whole run of punctuated words (captions.json, else words.json), read with
   their sentence and clause (punctuation; a pause over 0.8 s ends a sentence too). Only counts of things (figures()):
   no duration, sign ("minus five"), year, name's number ("page 42", "Planner 3"), date, clock time or address ("at
   five"), phone number, two numbers said back to back ("twenty twenty-three", "three ninety-nine"), range or ratio
   ("fifty to sixty", "one in ten"), measure ("220 degrees"), "a hundred percent sure", or lone "one" ("the best one").
   - hook: the first figure in the first sentence that is more than filler, or in its first HOOK_S, never past
     HOOK_MAX_S: money, or a count or percent of a plural thing said after it; its sub-line is a duration said in the
     same sentence ("in 3.5 weeks"), else the figure's own label. A bare figure is no hook.
   - chain (number_chain): 2-4 counts, each in its own clause, within CHAIN_S, each smaller than the one before (a
     funnel: flyers -> tastings -> orders); one said in a sentence of its own needs a funnel cue (funnel()); a lone
     "one" ends one only as a verb's object ("and signed one."), drawn bare (no verb label).
   - goal (goal_bar): a percent with "goal", "target" or "of the way" in its sentence, and a scaled figure there; the
     card comes up on the first of its words.
   - stat run (stat_stack): 2-4 labelled figures in one sentence that count different things.
   - counter: one count of COUNTER_MIN or more with a label; a stamp when an outcome word (rejected, ignored, failed,
     ghosted, lost ...) follows in the sentence. tally: 5-30 of a plural thing. money: a lone money figure. figure:
     a lone percent or a count of 31-49 (both kinetic_number).
   - step tracker (step_build): an enumeration ("two main kinds of bread", "three layers", then "one is" / "the
     other is" / "layer two is" / "step three," ...), one beat when the count is said and one per item, each item
     filled on its label (a noun, else the verb said for it: "step one is quick: you weigh" is WEIGH); "another <same
     noun>" later adds a "?" slot. One of sources, steps or ways (ENUM) ranks with a stat run (ENUM_BONUS).
2. Labels: 1-2 of the transcript's own words next to the number (the noun after it, else the verb before it), as said,
   never a number word or a date; the renderer sets them in capitals. A figure is written from what was said: "4.5k
   dollars" -> "$4.5K", "three hundred and forty" -> "340", K/M/B only when one was said and it reads as said ("2,345",
   never "2.345K"); check.py plan grounds every figure again.
3. Ranking and density: hook > chain = goal > stat run > counter > money > figure = tally > tracker beats (an item's
   fill before the count's empty wells, kept only with a fill), adjusted for clarity (labels, a stamp, more items).
   The strongest are kept, at most round(per_min x minutes) graphics in all (a tracker's beats are one graphic), the
   real cards already placed (images.json, visuals.json captures, posts, logos, titles, hand-written kinetic beats)
   counted first. The hook is always kept, over the budget when those fill it. A moving template the motion skill may
   build as a clip (budget.CLIP_TEMPLATES: a list, a flow, a before and after, a mechanism; or its placed clip) counts
   after the number beats: it neither takes their room nor keeps them away (own_cards); plan.py fits it round them.
   Between any two cards GAP_S of plain footage: a hold is cut to HOLD_TIGHT_S for it, a real card before a beat ends
   sooner (plan.py space_kinetic), and a strong beat blocked only by the hold of the one before bridges from it
   (BRIDGE_*); the next beat of the same tracker joins instead. Never over a real card, except a stat_stack beside a
   capture. No card ends on the first words of a number said after it (whole()).

Settings (style.json, taste.json): graphics.kinetic (on), graphics.kinetic_per_min (KINETIC_PER_MIN, every graphic a
minute, real ones included), graphics.kinetic_auto (false: only hand-written kinetic beats). The rate and the count
are lib/ai_editor/budget.py's, the same plan.py budget_cards keeps to: it wins over the style page's cards.per_min,
and cards.on false places none. Each beat carries its "strength" (its score, 0-1; a tracker's beats share their best)
and the hook "hook": true, so plan.py keeps the same ones when it counts the cards again.

refresh() keeps its beats ("auto": "kinetic" in visuals.json) while the cut's words, the real cards and the rate stay
the same (kinetic.auto.json holds their fingerprint), so a review note's change to one survives the next plan; any of
those changing finds them again, the note's removals and changes laid on them again (beat_key). Turned off, it clears
them (clear()). Stdlib only, deterministic.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parents[2] / "lib"))
from ai_editor import budget, numbers  # noqa: E402

VERSION = 3            # bump when the rules change: the fingerprint changes and every edit's beats are found again
KINETIC_PER_MIN = budget.DEFAULT_PER_MIN   # graphics a minute in all (real ones included), graphics.kinetic_per_min
GAP_S = 1.0            # plain footage kept between two cards, kinetic or real (plan.py bridges kinetic ones closer than 1 s)
REAL_MIN_S = 2.0       # a real card before a kinetic one ends GAP_S before it when it still holds this (plan.py space_kinetic)
LEAD_S = 0.1           # plan.CARD_LEAD_S: a card starts this long before its word
HOLD_MIN_S = 1.5       # a lockup stays this long after its last word at the least (1.2 s still + its landing)
HOLD_TIGHT_S = 1.3     # ... cut to this to leave the gap before the next card, or a number said next whole (plan.NUMBER_HOLD_S)
HOLD_WANT_S = 2.0      # and this long when nothing follows soon
BRIDGE_MIN_S = 1.0     # a card blocked only by the hold of the kinetic card before it bridges from it (plan.py bridge_kinetic)
BRIDGE_MAX_S = 12.0    # when it starts this long after that card's last word; two bridged cards are up this long at the most
BRIDGE_SCORE = 60      # and only a strong beat bridges (a counter, stat run, chain or goal; never a tally or a lone figure)
HOOK_S = 3.0           # a figure said this early is the hook, whatever the first sentence's length
HOOK_MAX_S = 6.0       # and never one said later than this (both from the first sentence that is more than filler)
CHAIN_S = 8.0          # a chain's figures are said within this
CHAIN_STEP_S = 5.0     # and each within this of the one before
COUNTER_MIN = 50       # a count this big counts up
TALLY = (5, 30)        # a count in this range of a plural thing fills tiles
TRACKER_S = 40.0       # a tracker's items are said within this of its count
SCORE = {"hook": 100, "chain": 80, "goal": 80, "stat": 70, "counter": 60, "money": 50, "figure": 45, "tally": 45,
         "fill": 30, "tracker": 22, "question": 20}   # a tracker's count alone is empty wells: kept only with a fill
ENUM_BONUS = 42        # a tracker of sources, steps or ways (the spine of the video) ranks with a stat run: fill 72
TYPE = {"hook": "kinetic_number", "chain": "number_chain", "goal": "goal_bar", "stat": "stat_stack", "counter": "kinetic_number",
        "money": "kinetic_number", "figure": "kinetic_number", "tally": "kinetic_number", "tracker": "step_build",
        "fill": "step_build", "question": "step_build"}
AUTO = "kinetic"       # visuals.json "auto" mark on the beats this script owns
STATE = "kinetic.auto.json"

STOP = set("""a an the and or but so to of in on at for from with by as into onto than then that this these those which who
whom whose what when where why how if because while i you he she it we they me him her us them my your his its our their
mine yours is are was were be been being am do does did done have has had having will would can could should shall may
might must just only also even still really very pretty quite too about around over under up down out off back here there
now right like get got gets getting go goes going gone went make made makes keep kept said say says not no yes every each
all some any more most much many few other another same such own there's here's it's i'm i've i'll you're we're they're
that's what's don't didn't doesn't can't won't wanna gonna gotta let let's per via okay ok well um uh actually basically
literally kinda sorta almost nearly ready since until after before during through without within across""".split())
FILLERS = {"uh", "um", "er", "erm", "ah", "uhm", "hmm"}
WEAK = set("""different more new other extra whole single total main complete separate big small little huge few actual real
additional unique individual entire full whole brand-new various several""".split())
DETS = set("a an the my our your his her their its this that these those some".split())
LEAD_SKIP = DETS | set("""we you i they he she it 'll will can should must need needs to have has had just then also gotta
gonna wanna simply basically pretty very really super so quite kinda actually literally""".split())
DULL = set("""simple easy hard important crucial key great good bad best worst cool interesting obvious different same fun
quick short long huge big small where when how what why""".split())
CURRENCY = {"€": "€", "$": "$", "£": "£", "euro": "€", "euros": "€", "eur": "€", "dollar": "$", "dollars": "$", "usd": "$",
            "buck": "$", "bucks": "$", "pound": "£", "pounds": "£", "quid": "£", "gbp": "£"}
OUTCOME = set("""rejected ignored failed ghosted lost declined refused cancelled canceled blocked banned denied unanswered
returned flopped bounced""".split())
GOAL = {"goal", "target"}
PREPS = set("in within under over after for just only about around".split())
ORDINAL = {"one": 1, "1": 1, "first": 1, "two": 2, "2": 2, "second": 2, "three": 3, "3": 3, "third": 3, "four": 4, "4": 4,
           "fourth": 4}
STEP_NOUNS = set("""step steps layer layers part parts phase phases tip tips rule rules level levels stage stages pillar
pillars way ways reason reasons thing things lesson lessons mistake mistakes""".split())
NEXT_CUE = {"other", "another", "second", "secondly", "third", "thirdly", "last", "lastly", "finally", "next"}
OBJECTS = set("us me them him her you it".split())   # "paid us 2.5k": the verb before is one further back
OPENERS = set("and so now okay ok then well also but".split()) | FILLERS   # passed over before a cue
CALENDAR = set("""january february march april may june july august september october november december monday tuesday
wednesday thursday friday saturday sunday""".split())   # "in March 300 people came": a date, not a name's number
IRREGULAR = {"people", "children", "men", "women", "data", "media", "feet", "teeth", "mice"}
ENUM = set("""source sources step steps way ways stage stages phase phases stream streams method methods layer layers pillar
pillars""".split())   # what a tracker counts when the speech enumerates sources or steps (ENUM_BONUS)
NAMED = STEP_NOUNS | set("""number page pages episode episodes chapter day week month year room level version season code
zip table gate row line channel track act round lap no""".split())   # "page 42", "day 30", "month three": a name, not a count
YEAR_PREP = set("in since of until by from back around year".split())   # "back in twenty nineteen": a year
LINK = {"to", "in", "or", "and"}   # "fifty to sixty", "one in ten", "between fifty and sixty": a range or a ratio
FUNNEL = set("""got get gets sent closed close signed sign converted convert booked book landed land won win turned became
ended led gave brought resulted sold sell replied answered paid bought joined showed""".split())
FUNNEL_CUE = (("to", "get", "there"), ("out", "of"), ("of", "those"), ("of", "them"), ("of", "which"))
MEASURE = set("""degree degrees gram grams kilo kilos kilogram kilograms kg kilometer kilometers kilometre kilometres km meter
meters metre metres mile miles liter liters litre litres ml cm inch inches feet foot calorie calories kcal times mph""".split())
SURE = set("sure certain honest true right agree committed convinced serious".split())   # "a hundred percent sure": an idiom
NOT_ONE = DETS | set("""best last first next only single each every no any which another other just same right whole""".split())


def low(text):
    return re.sub(r"^[^\w€$£%]+|[^\w€$£%]+$", "", text.lower().replace("’", "'"))


def shown(text):
    """A word as said, for the screen: no punctuation round it, its own case ("iPhone")."""
    return re.sub(r"^[^\w€$£]+|[^\w%]+$", "", text.replace("’", "'"))


def ends(text, marks=",.;:!?"):
    return text.rstrip().rstrip("\"')]”’").endswith(tuple(marks))


def plural(w):
    return w in IRREGULAR or (len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")))


def numword(c):
    """A number said in a word or digits ("twenty-three", "hundred", "4.5k"): never a label."""
    return bool(numbers.DIGITS.fullmatch(c)) or any(x in numbers.UNITS or x in numbers.TENS or x in numbers.BIG
                                                     for x in c.split("-") if x)


def key_of(text):
    """plan.py's word match: clean(text).lower()."""
    return re.sub(r"[^\w'’-]+", "", text).lower()


class Take:
    """The words, their sentences and clauses, and the spoken numbers in them."""

    def __init__(self, words):
        self.w = [w for w in words if w.get("type", "word") == "word" and str(w.get("text", "")).strip()]
        self.low = [low(w["text"]) for w in self.w]
        self.sent, self.clause, s, c = [], [], 0, 0
        for i, w in enumerate(self.w):
            self.sent.append(s)
            self.clause.append(c)
            nxt = self.w[i + 1] if i + 1 < len(self.w) else None
            if ends(w["text"], ".!?") or (nxt and nxt["start"] - w["end"] > 0.8):
                s, c = s + 1, c + 1
            elif ends(w["text"]):
                c += 1
        self.spans = [dict(sp, i0=sp["start"], i1=sp["end"]) for sp in numbers.spans([w["text"] for w in self.w])]
        self.keys = [key_of(w["text"]) for w in self.w]

    def t(self, i):
        return self.w[i]["start"]

    def sent_range(self, s):
        idx = [i for i, x in enumerate(self.sent) if x == s]
        return idx[0], idx[-1]

    def nth(self, i):
        """Which time word i is said in the whole take (plan.py _place "nth")."""
        return sum(1 for k in range(i + 1) if self.keys[k] == self.keys[i])

    def nth_after(self, i, start):
        """Which time word i is said once a card starting at `start` is up (plan.py word_at "nth")."""
        return sum(1 for k in range(i + 1) if self.keys[k] == self.keys[i] and self.w[k]["start"] >= start)

    def phrase(self, j, limit, skip=frozenset()):
        """Up to two of the speaker's words from j on (the noun said there): leading `skip` words passed over, stopped by
        a function word or punctuation, cut after its last plural. [] when there is none."""
        col = []
        while j <= limit and len(col) < 3:
            c, raw = self.low[j], self.w[j]["text"]
            if not c or c in FILLERS or (not col and c in skip):
                if ends(raw) and not (not col and ends(raw, ",")):
                    break
                j += 1
                continue
            if c in STOP or numword(c) or c in CALENDAR or c == "between":
                break
            col.append(j)
            if ends(raw):
                break
            j += 1
        pl = [k for k, x in enumerate(col) if plural(self.low[x])]
        if pl:
            col = col[:pl[-1] + 1]
        return col[-2:]

    def text(self, idx):
        return " ".join(shown(self.w[i]["text"]) for i in idx)


def figure_text(take, sp):
    """The figure as drawn, from what was said: "$4.5K", "340", "1,200", "40%". K/M/B only when one was said, and only
    when it reads as said: "two thousand three hundred and forty-five" is "2,345", never "2.345K"."""
    v, said = sp["value"], " ".join(take.low[sp["i0"]:sp["i1"] + 1])
    if sp["kind"] == "percent":
        return numbers.norm(v) + "%"
    scaled = bool(re.search(r"\d(k|m|bn|b)\b", said)) or any(t in numbers.SCALE for t in re.split(r"[\s-]+", said))
    body = f"{int(v):,}" if v == int(v) else numbers.norm(v)
    if scaled and v >= 1000:
        div, suf = next((d, x) for d, x in ((10 ** 9, "B"), (10 ** 6, "M"), (1000, "K")) if v >= d)
        if round(v / div, 1) == round(v / div, 6) or re.search(r"\d(k|m|bn|b)\b", said):
            body = numbers.norm(v / div) + suf
    return (currency(take, sp) if sp["kind"] == "money" else "") + body


def currency(take, sp):
    """The sign of the currency said with a money figure (in the word, or the word after or before it); "" for a bare figure."""
    for i in range(sp["i0"], sp["i1"] + 1):
        m = re.search(r"[€$£]", take.w[i]["text"])
        if m:
            return m[0]
    for i in (sp["i1"] + 1, sp["i0"] - 1):
        if 0 <= i < len(take.w) and take.low[i] in CURRENCY:
            return CURRENCY[take.low[i]]
    return ""


def label_of(take, sp):
    """(word indices of the label, "after"|"before"): the noun said after the figure (its currency word and an "of"
    passed over: "1.2k euros of seeds"), else the verb said just before it ("sign one", "paid us 2.5k"). ([], None)
    when neither."""
    _, end = take.sent_range(take.sent[sp["i1"]])
    nxt = next((take.low[k] for k in range(sp["i1"] + 1, end + 1) if take.low[k] not in FILLERS), "")
    skip = WEAK | set(CURRENCY) | {"of"} | ({"in", "on"} if nxt in CURRENCY else set())   # "2k dollars on ads"
    after = take.phrase(sp["i1"] + 1, end, skip) if not ends(take.w[sp["i1"]]["text"], ".!?") else []
    if after and take.low[after[0]] in MEASURE:
        return [], None   # "220 degrees", "500 grams", "fifty times": a measure, not a count of things
    if after:
        return after, "after"
    k = sp["i0"] - 1
    while k >= 0 and (take.low[k] in FILLERS or k == sp["i0"] - 1 and take.low[k] in OBJECTS):
        k -= 1
    if k >= 0 and take.sent[k] == take.sent[sp["i0"]] and not ends(take.w[k]["text"]) and take.low[k] not in STOP \
            and not numword(take.low[k]) and take.low[k] not in WEAK | CALENDAR and re.fullmatch(r"[a-z'-]+", take.low[k]):
        return [k], "before"
    return [], None


def figures(take):
    """The spoken numbers worth a graphic: each with its sentence, clause, label and how it is drawn. Leaves out what
    is no count of things: a duration (a sub-line, never a figure), a sign said with it ("minus five"), a year
    ("2019", "back in two thousand and nineteen"), a name's number ("GPT-4", "Planner 3", "page 42", "day 30", "layer
    one": an ordinal the tracker reads), a date ("June 21"), a clock time or an address ("at five", "at 221"), a phone
    number or an ID (a leading 0, 7+ digits), two numbers said back to back ("twenty twenty-three", "three ninety-nine",
    "five five five": a year, a price, digits), a range or a ratio ("fifty to sixty", "between fifty and sixty", "one in
    ten"; of "from 200 to 12K" only the result), and a lone "one" ("one is", "the best one"), which only ends a chain
    after a verb ("and signed one.")."""
    out, spans = [], take.spans
    pair = set()
    for a, b in zip(spans, spans[1:]):
        gap = take.low[a["i1"] + 1:b["i0"]]
        back = b["i0"] == a["i1"] + 1 and not ends(take.w[a["i1"]]["text"])
        ranged = len(gap) == 1 and gap[0] in LINK and not ends(take.w[a["i1"]]["text"]) and b["kind"] != "duration" and (
            gap[0] != "and" or a["i0"] and take.low[a["i0"] - 1] == "between") or gap == ["out", "of"]
        if back or ranged:
            pair.add(a["i0"])
            if not (ranged and a["i0"] and take.low[a["i0"] - 1] == "from"):
                pair.add(b["i0"])
    for sp in spans:
        i0, i1 = sp["i0"], sp["i1"]
        raw = [take.w[i]["text"] for i in range(i0, i1 + 1)]
        if sp["value"] < 0 or i0 in pair:
            continue
        if sp["kind"] == "percent" and sp["value"] == 100 and (i1 + 1 >= len(take.w) or take.low[i1 + 1] in SURE or ends(take.w[i1]["text"])):
            continue   # "a hundred percent sure", "I agree a hundred percent."
        if any(re.search(r"[a-z]", r.lower()) and re.search(r"\d", r) and not numbers.DIGITS.fullmatch(low(r)) for r in raw):
            continue   # glued to a name: "GPT-4", "V2"
        digits = re.sub(r"[^\d]", "", raw[0]) if numbers.DIGITS.fullmatch(low(raw[0])) else ""
        if len(raw) == 1 and digits and (len(digits) > 1 and digits[0] == "0" or len(digits) >= 7 and "," not in raw[0]):
            continue   # a phone number or an ID
        prev = take.low[i0 - 1] if i0 else ""
        prev_raw = take.w[i0 - 1]["text"] if i0 else ""
        nxt = take.low[i1 + 1] if i1 + 1 < len(take.w) else ""
        if prev in NAMED or prev in CALENDAR or nxt in CALENDAR or (prev_raw[:1].isupper() and prev not in STOP | CALENDAR and i0
                                                                       and take.sent[i0 - 1] == take.sent[i0] and take.sent_range(take.sent[i0])[0] != i0 - 1
                                                                       and not ends(prev_raw)):
            continue   # an ordinal, a version or a date: "step one", "page 42", "Planner 3", "June 21"
        v = sp["value"]
        f = dict(sp, sent=take.sent[i0], clause=take.clause[i0], t=take.t(i0), text=figure_text(take, sp))
        f["label"], f["label_from"] = label_of(take, sp)
        things = f["label_from"] == "after" and plural(take.low[f["label"][-1]])   # "2,000 people", never a year
        if sp["kind"] == "count" and v == int(v) and 1900 <= v <= 2100 and (re.fullmatch(r"\d{4}", low(raw[0])) or prev in YEAR_PREP
                                                                             and not things):
            continue   # a year
        if prev == "at" and sp["kind"] == "count" and not things:
            continue   # "at five", "at 221 Baker Street": a time or an address ("we're at sixty-three regulars" stays)
        f["weak"] = v <= 1 and sp["kind"] == "count"
        # a lone "one" may end a chain only as a verb's object at its clause's end: "and signed one."
        f["end_ok"] = f["weak"] and i0 == i1 and prev not in NOT_ONE and re.fullmatch(r"[a-z'-]+", prev or "-") is not None \
            and not numword(prev) and (ends(take.w[i1]["text"]) or nxt in ("and", "but", "so", "then", ""))
        # the figure's own word: its first, unless that is "a" ("a hundred and twenty-seven" lands on "hundred")
        f["word"] = i0 + 1 if take.low[i0] in ("a", "an") and i1 > i0 else i0
        out.append(f)
    return out


def durations(take):
    return [sp for sp in take.spans if sp["kind"] == "duration"]


# ---------------------------------------------------------------- candidates

class Card:
    """One candidate beat: its class, trigger word, parts and score."""

    def __init__(self, take, cls, i0, props, parts, score, why, tracker=None):
        self.take, self.cls, self.i0, self.props, self.score, self.why, self.tracker = take, cls, i0, props, score, why, tracker
        self.s = round(max(0.0, take.t(i0) - LEAD_S), 3)
        self.last = max(take.t(i) for i in parts)
        self.e_min = round(self.last + HOLD_MIN_S, 3)
        self.e_want = round(self.last + HOLD_WANT_S, 3)
        self.e = self.e_want
        self.parts = parts
        self.drop = None
        self.note = None   # why a kept card is kept anyway (the hook over the budget)

    @property
    def type(self):
        return TYPE[self.cls]

    def beat(self):
        """The visuals.json beat plan.py reads (references/kinetic.md): the card's word and nth, each part's word
        (its nth once the card is up when it was said earlier in the card), hold_s from the card's start."""
        tk, props = self.take, json.loads(json.dumps(self.props))

        def fill(node):
            if isinstance(node, list):
                for x in node:
                    fill(x)
            elif isinstance(node, dict):
                first = None
                for k in [k for k in node if k.startswith("_")]:
                    out, i = k[1:], node.pop(k)
                    n = tk.nth_after(i, self.s)
                    if first is not None and n != first:
                        continue   # one nth per node: a part that needs another one keeps its default time
                    first = n
                    node[out] = shown(tk.w[i]["text"])
                    if n > 1:
                        node["nth"] = n
                for v in node.values():
                    fill(v)
        fill(props)
        out = {"word": shown(tk.w[self.i0]["text"]), "nth": tk.nth(self.i0), "kind": "anim", "type": self.type,
               "hold_s": round(self.e - self.s, 2), "props": props, "auto": AUTO,
               "strength": round(min(1.0, max(0.0, getattr(self, "strength", self.score) / 100)), 2)}
        if self.cls == "hook":
            out["hook"] = True
        return out

    def line(self):
        said = " ".join(self.take.w[i]["text"] for i in range(self.i0, min(len(self.take.w), self.i0 + 8)))
        note = f"  ({self.note})" if self.note and not self.drop else ""
        return f"{self.s:6.2f}-{self.e:6.2f}  {self.cls:8} {self.type:14} {self.score:5.1f}  {said[:60]}{note}"


def label_parts(take, f, key="label", word="_label_word"):
    if not f["label"]:
        return {}
    return {key: take.text(f["label"]), word: f["label"][0]}


def clarity(fs):
    """+3 a figure whose label reads (1-2 words), -8 one with none."""
    return sum(3 if f["label"] else -8 for f in fs)


FILLER_SENT = OPENERS | set("okay alright right yeah yes hey hi guys look listen um uh".split())


def hook(take, figs):
    """The hook: the first figure said in the first sentence that is more than filler ("So. Um. Okay." passed over), or
    in its first HOOK_S, never past HOOK_MAX_S: a money figure, or a count or percent of a plural thing said after it
    ("fifty loaves", "forty percent of buyers"). A bare figure ("I wake up at five", "a hundred percent sure", "won three
    to one") is no hook."""
    real = lambda s: any(take.low[i] not in FILLER_SENT for i in range(take.sent_range(s)[0], take.sent_range(s)[1] + 1))  # noqa: E731
    s0 = next((s for s in sorted(set(take.sent)) if real(s)), None)
    if s0 is None:
        return None
    a0, first = take.sent_range(s0)
    t0 = take.t(a0)
    for f in figs:
        if f["weak"] or f["kind"] not in ("money", "count", "percent") or f["i0"] < a0:
            continue
        if f["i0"] > first and f["t"] - t0 > HOOK_S or f["t"] - t0 > HOOK_MAX_S:
            return None
        if f["kind"] != "money" and not (f["label_from"] == "after" and plural(take.low[f["label"][-1]])):
            continue
        sub, parts = [], [f["word"]]
        d = next((d for d in durations(take) if take.sent[d["i0"]] == f["sent"] and d["i0"] > f["i1"]), None)
        if d:
            unit = d["i1"] + 1 if d["i1"] + 1 < len(take.w) and take.low[d["i1"] + 1] in numbers.DURATION else None
            pre = []
            k = d["i0"] - 1
            while k > f["i1"] and len(pre) < 2 and take.low[k] in PREPS and not ends(take.w[k]["text"]):
                pre.insert(0, k)
                k -= 1
            sub = [{"text": shown(take.w[k]["text"]), "_word": k} for k in pre]
            sub.append({"text": numbers.norm(d["value"]), "_word": d["i0"], "key": True})
            if unit is not None:
                sub.append({"text": shown(take.w[unit]["text"]), "_word": unit})
            parts += [x["_word"] for x in sub]
        elif f["label"]:
            sub = [{"text": shown(take.w[k]["text"]), "_word": k} for k in f["label"]]
            sub[-1]["key"] = True
            parts += f["label"]
        props = {"num": f["text"], "variant": "hook", "_word": f["word"]}
        if sub:
            props["sub"] = sub
        return Card(take, "hook", f["word"], props, parts, SCORE["hook"] + (3 if sub else -5), "the first figure")
    return None


def funnel(take, f):
    """A figure said as the next step of a funnel: a funnel verb in its clause before it or just after it ("I got four
    calls", "eighty signed up"), or "to get there", "out of", "of those" in its sentence."""
    a, z = take.sent_range(f["sent"])
    near = [take.low[k] for k in range(a, min(z, f["i1"] + 2) + 1) if take.clause[k] == f["clause"]]
    said = take.low[a:z + 1]
    return any(w in FUNNEL for w in near) or any(tuple(said[k:k + len(q)]) == q for q in FUNNEL_CUE for k in range(len(said)))


def chains(take, figs):
    """Every funnel: 2-4 counts, each in its own clause and smaller than the one before, close together; a count said
    in a sentence of its own only with a funnel cue (funnel: "We have 80 members. We also have 12 coaches." is a list).
    A lone "one" only ends one, after its verb ("and signed one."). An item's label is the noun said after it; a figure
    with only a verb before it ("1" of "signed one") is drawn bare."""
    counts = [f for f in figs if f["kind"] == "count" and (f["label"] or f["end_ok"])]
    out = []
    for a in range(len(counts)):
        if counts[a]["weak"]:
            continue
        run = [counts[a]]
        for f in counts[a + 1:]:
            p = run[-1]
            if p["weak"] or len(run) == 4 or f["weak"] and not f["end_ok"]:
                break
            if f["value"] >= p["value"] or f["clause"] == p["clause"] or f["t"] - p["t"] > CHAIN_STEP_S \
                    or f["t"] - run[0]["t"] > CHAIN_S or f["sent"] != p["sent"] and not funnel(take, f):
                break
            if any(g["kind"] != "count" and p["i1"] < g["i0"] < f["i0"] for g in figs):
                break   # a money figure or a percent between: two different things
            run.append(f)
        if len(run) < 2 or run[0]["value"] < 3:
            continue
        if len({f["sent"] for f in run}) == 1 and any(g["sent"] == run[0]["sent"] and not g["weak"] and g not in run for g in figs):
            continue   # "80 members, 12 coaches and 9.2k in revenue": a list of stats, not a funnel
        noun = lambda f: f["label_from"] == "after"  # noqa: E731
        items = [{"num": f["text"], "_word": f["word"], **(label_parts(take, f) if noun(f) else {})} for f in run]
        parts = [f["word"] for f in run] + [f["label"][0] for f in run if noun(f)]
        out.append(Card(take, "chain", run[0]["word"], {"items": items}, parts,
                        SCORE["chain"] + 4 * (len(run) - 2) + clarity([f for f in run if not f["weak"]]) / len(run),
                        f"{len(run)} counts, each smaller"))
    return out


def goals(take, figs):
    out = []
    for f in figs:
        if f["kind"] != "percent":
            continue
        a, b = take.sent_range(f["sent"])
        said = take.low[a:b + 1]
        gw = next((k for k in range(a, b + 1) if take.low[k] in GOAL), None)
        way = any(said[k:k + 3] == ["of", "the", "way"] for k in range(len(said)))
        tgt = next((g for g in figs if g["sent"] == f["sent"] and g is not f and g["kind"] in ("count", "money")
                    and (g["value"] >= 1000 or any(t in numbers.SCALE for t in take.low[g["i0"]:g["i1"] + 1]))), None)
        if (gw is None and not way) or not tgt:
            continue
        props = {"pct": f["text"], "_word_pct": f["word"], "_count_word": f["i1"], "target": tgt["text"], "_word_target": tgt["word"]}
        parts = [f["word"], f["i1"], tgt["word"]]
        if gw is not None:
            props["_word_goal"] = gw
            parts.append(gw)
        # "our 20k goal is forty percent done": the card comes up on the first of its words
        out.append(Card(take, "goal", min(f["word"], tgt["word"]), props, parts, SCORE["goal"], "a percent of a goal"))
    return out


def stat_runs(take, figs):
    out = []
    for s in sorted({f["sent"] for f in figs}):
        fs = [f for f in figs if f["sent"] == s and not f["weak"] and f["kind"] in ("count", "money", "percent")]
        labelled = [f for f in fs if f["label"]]
        if len(labelled) < 2 or len({take.text(f["label"]).lower() for f in labelled}) < len(labelled):
            continue
        fs = [f for f in fs if f["label"] or f["kind"] == "money"][:4]
        if all(f["kind"] == "count" for f in fs) and all(b["value"] < a["value"] and b["clause"] != a["clause"] for a, b in zip(fs, fs[1:])):
            continue   # a funnel: the chain shows it
        stats = [{"num": f["text"], "_word": f["word"], **label_parts(take, f)} for f in fs]
        parts = [f["word"] for f in fs] + [f["label"][0] for f in fs if f["label"]]
        out.append(Card(take, "stat", fs[0]["word"], {"stats": stats}, parts,
                        SCORE["stat"] + 3 * (len(fs) - 2) + clarity(fs) / len(fs), f"{len(fs)} figures, different things"))
    return out


def singles(take, figs):
    """counter (with a stamp), tally, money and lone figures."""
    out = []
    for f in figs:
        v, k = f["value"], f["kind"]
        if f["weak"] or f["label"] and take.low[f["label"][-1]] in GOAL:
            continue   # "our 20k goal" is the goal bar's target, never a count of things
        lab = [{"text": shown(take.w[i]["text"]), "_word": i} for i in f["label"]] if f["label_from"] == "after" else []
        if lab:
            lab[-1]["key"] = True
        land = f["label"][0] if f["label_from"] == "after" and take.t(f["label"][0]) - take.t(f["i1"]) < 1.2 else f["i1"]
        parts = [f["word"]] + list(f["label"])
        if k == "money":
            props = {"num": f["text"], "variant": "hook", "_word": f["word"], **({"sub": lab} if lab else {})}
            out.append(Card(take, "money", f["word"], props, parts, SCORE["money"] + (3 if lab else -5) + (2 if "K" in f["text"] else 0), "a money figure"))
        elif k == "count" and v >= COUNTER_MIN and f["label"]:
            a, b = take.sent_range(f["sent"])
            st = next((i for i in range(f["i1"] + 1, b + 1) if take.low[i] in OUTCOME), None)
            props = {"num": f["text"], "variant": "counter", "_word": f["word"], "_land_word": land, **({"sub": lab} if lab else {})}
            if st is not None:
                props["stamp"] = {"text": shown(take.w[st]["text"]), "_word": st}
                parts.append(st)
            out.append(Card(take, "counter", f["word"], props, parts, SCORE["counter"] + (5 if st is not None else 0) + clarity([f]),
                            "a big count" + (" and its outcome" if st is not None else "")))
        elif k == "count" and TALLY[0] <= v <= TALLY[1] and v == int(v) and f["label"] and plural(take.low[f["label"][-1]]):
            props = {"num": f["text"], "variant": "tally", "_word": f["word"], "_land_word": land, **({"sub": lab} if lab else {})}
            out.append(Card(take, "tally", f["word"], props, parts, SCORE["tally"] + clarity([f]), "a small count of things"))
        elif (k == "percent" or k == "count" and TALLY[1] < v < COUNTER_MIN) and (f["label"] or k == "percent"):
            props = {"num": f["text"], "variant": "hook", "_word": f["word"], **({"sub": lab} if lab else {})}
            out.append(Card(take, "figure", f["word"], props, parts, SCORE["figure"] + clarity([f]), "a lone figure"))
    return out


def plain_verb(take, k):
    return re.fullmatch(r"[a-z'-]+", take.w[k]["text"].strip(",.:;!?")) is not None and take.low[k] not in \
        STOP | LEAD_SKIP | DULL | WEAK | FILLERS and not numword(take.low[k])


def item_label(take, j, end):
    """A tracker item's label: the noun phrase after the cue's "is", ":" or "," (its article passed over). A list of
    names doing the step ("Planner Pro, Oven Mate, and Timer Box bake it") is named by its verb, so the labels stay
    parallel; an item with no plain noun ("step one is quick: you weigh the flour", "step two is where we knead it")
    by the first verb said after it, in its sentence or the next."""
    lab = take.phrase(j, end, LEAD_SKIP)
    nxt = lab[-1] + 1 if lab else end + 1
    if lab and ends(take.w[lab[-1]]["text"], ",") and nxt <= end and take.w[nxt]["text"][:1].isupper() \
            and "and" in take.low[nxt:min(end, nxt + 6) + 1]:
        a = nxt + take.low[nxt:min(end, nxt + 6) + 1].index("and")
        v = next((k for k in range(a + 2, end + 1) if plain_verb(take, k)), None)
        return [v] if v is not None else []
    if lab and take.low[lab[0]] not in DULL:
        return lab
    stop = take.sent_range(take.sent[end] + 1)[1] if end + 1 < len(take.w) else end
    return next(([k] for k in range(j, stop + 1) if plain_verb(take, k)), [])


def cue_items(take, a, limit_t):
    """The enumerated items said after word a: [(cue word, label words, ordinal or None)], in order."""
    out = []
    for c in sorted({take.clause[i] for i in range(a, len(take.w)) if take.t(i) <= limit_t}):
        i = max(a, take.clause.index(c))
        b1 = take.sent_range(take.sent[i])[1]
        while i <= b1 and (take.low[i] in OPENERS or take.low[i] == "for" and i < b1 and take.low[i + 1] in STEP_NOUNS):
            i += 1   # "So", "Now for step two"
        if i > b1:
            continue
        w0, w1 = take.low[i], take.low[i + 1] if i + 1 <= b1 else ""
        w2 = take.low[i + 2] if i + 2 <= b1 else ""
        cue, n = None, None
        if w0 in STEP_NOUNS and (w1 in ORDINAL or w1 == "number" and w2 in ORDINAL):
            cue, n = i, ORDINAL[w2 if w1 == "number" else w1]
        elif w0 == "number" and w1 in ORDINAL:
            cue, n = i, ORDINAL[w1]
        elif w0 in ("one", "first", "firstly") or w0 == "the" and w1 == "first":
            cue, n = i if w0 != "the" else i + 1, 1
        elif w0 in NEXT_CUE or w0 in ("the", "my", "our", "your") and w1 in NEXT_CUE:
            cue = i if w0 in NEXT_CUE else i + 1
            if take.low[cue] == "another":
                continue   # "another <noun>" is the next one asked about, never an item (question())
        if cue is None:
            continue
        # the label: after the first "is", "are", ":" or "," in the sentence once past the cue
        j, lab = cue + 1, []
        while j <= b1:
            if take.low[j] in ("is", "are", "was") or ends(take.w[j]["text"], ",:"):
                lab = item_label(take, j + 1, b1)
                break
            j += 1
        if not any(c0 == cue for c0, _, _ in out):   # "Now, step three": its clause and the opener's lead to one cue
            out.append((cue, lab, n))
    return out


def trackers(take, figs):
    """Step trackers: a count of 2-4 things said, then that many items ("one is", "the other is", "layer two is",
    "step three,"); or items with their own ordinals and no count. One candidate per beat."""
    out, used = [], set()
    starts = []
    for sp in take.spans:   # "two main kinds of bread", "three layers": the count is said with what it counts
        if sp["kind"] != "count" or not (2 <= sp["value"] <= 4) or sp["value"] != int(sp["value"]):
            continue
        _, end = take.sent_range(take.sent[sp["i1"]])
        noun = take.phrase(sp["i1"] + 1, end, WEAK)
        if noun and plural(take.low[noun[-1]]):
            starts.append((sp["i1"], int(sp["value"]), noun))
    for i in range(len(take.w)):   # "step one," with no count said before it
        if take.low[i] in STEP_NOUNS and i + 1 < len(take.w) and ORDINAL.get(take.low[i + 1]) == 1:
            starts.append((i, None, []))
    for a, n, noun in sorted(starts):
        if a in used:
            continue
        items = cue_items(take, a if n is None else a + 1, take.t(a) + TRACKER_S)
        if n is None:   # the ordinals themselves: 1, 2, 3 ... in order
            seq = []
            for it in items:
                if it[2] == len(seq) + 1:
                    seq.append(it)
            items = seq
        else:   # "one is", "the other is" in turn, or the ordinals in order
            seq = []
            for it in items:
                if it[2] is None or it[2] == len(seq) + 1:
                    seq.append(it)
            items = seq[:n]
        if len(items) < 2 or (n and len(items) < n) or any(not lab for _, lab, _ in items) or len(items) > 4:
            continue
        used.update(c for c, _, _ in items)
        labels = [take.text(lab) for _, lab, _ in items]
        tid = f"tracker-{len(out) + 1}"
        q = question(take, items[-1][0], noun) if noun and len(items) < 4 else None
        slots = lambda states: [dict(s) for s in states]   # noqa: E731
        base = [{"label": lb, "state": "empty"} for lb in labels] + ([{"state": "off"}] if q is not None else [])
        beats = []
        if n:
            st = slots(base)
            for x in st[:len(labels)]:
                x["_word"] = a
            beats.append(("tracker", a, st, [a], f"{n} {take.text(noun)} said"))
        for k, (cue, lab, _) in enumerate(items):
            st = slots(base)
            for x in st[:k]:
                x["state"] = "filled"
            st[k].update(state="filled", _word=lab[0])
            beats.append(("fill", cue, st, [cue, lab[0]], f"item {k + 1}: {labels[k]}"))
        if q is not None:
            st = slots(base)
            for x in st[:len(labels)]:
                x["state"] = "filled"
            st[-1].update(state="question", _word=q)
            beats.append(("question", q, st, [q], f"another {take.text(noun[-1:])}"))
        enum = ENUM_BONUS if any(take.low[x] in ENUM for x in noun) or n is None and take.low[a] in ENUM else 0
        cards = [Card(take, cls, i0, {"id": tid, "slots": st}, parts, SCORE[cls] + (2 if n else 0) + enum, why, tracker=tid)
                 for cls, i0, st, parts, why in beats]
        if fits(cards[0]):
            out += cards
        else:   # labels too wide for their wells: one word each, else no tracker
            for c in cards:
                for x in c.props["slots"]:
                    if x.get("label"):
                        x["label"] = x["label"].split()[-1]
            out += cards if fits(cards[0]) else []
    return out


def question(take, after, noun):
    """"another <the tracker's noun>" (or "next", "a third") said after its last item: a "?" slot pops there."""
    head = take.low[noun[-1]].rstrip("s")
    for i in range(after + 1, len(take.w) - 1):
        if take.low[i] in ("another", "next", "third", "fourth") and take.low[i + 1].rstrip("s") == head:
            return i
    return None


def fits(card):
    """check.py plan's estimate of whether the renderer draws it (a chain or a tracker too wide for the grid)."""
    from check import kinetic_fit
    plain = json.loads(json.dumps(card.props), object_hook=lambda d: {k: v for k, v in d.items() if not k.startswith("_")})
    return not [f for f in kinetic_fit({"start": 0.0, "anim": {"type": card.type, "props": plain}}, "c", "9:16") if f["level"] == "FAIL"]


def candidates(take):
    figs = figures(take)
    out = [c for c in [hook(take, figs)] if c] + chains(take, figs) + goals(take, figs) + stat_runs(take, figs) + singles(take, figs) \
        + trackers(take, figs)
    keep = []
    for c in out:
        if c.type == "number_chain" and not fits(c):
            for it in c.props["items"]:
                if it.get("label"):
                    it["label"] = it["label"].split()[-1]
            if not fits(c):
                continue
        if c.last - c.s > 9:
            c.score -= 5   # a long beat reads as one less clearly
        keep.append(c)
    return keep


# ---------------------------------------------------------------- the edit's real cards and the budget

def real_cards(take, visuals, images, style, duration):
    """[(start, end, kind, is_picture)]: every card the edit already has (images.json, visuals.json captures, posts,
    logos, anims, titles and ctas, and kinetic beats written by hand), at its word, for the budget and the gaps. A
    motion skill clip counts as the beat it replaced (its "fallback"), so placing one never moves the number beats."""
    try:
        from plan import card_defaults
        hold = card_defaults(style or {})[0]
    except Exception:   # noqa: BLE001  a style plan.py cannot read: its default hold
        hold = 2.5
    out, seen = [], set()

    def at(word, nth, after):
        hits = [i for i, k in enumerate(take.keys) if k == key_of(str(word or ""))]
        hits = hits[nth - 1:nth] if nth else [i for i in hits if take.t(i) > after]
        return take.t(hits[0]) if hits else None
    after = -1.0
    for v in [x.get("fallback") or x for x in visuals] + list(images):
        if v.get("auto") == AUTO or not v.get("word") and v.get("kind") != "title":
            continue
        k = (key_of(str(v.get("word", ""))), v.get("nth") or 1)
        if v.get("kind") == "capture" or "src" in v:
            if k in seen:
                continue   # a capture beat and the image capture.mjs fetched for it: one card
            seen.add(k)
        if v.get("kind") in ("list", "stamp"):
            continue
        t = at(v.get("word"), v.get("nth"), after) if v.get("word") else 0.0
        if t is None:
            continue
        after = t
        s = max(0.0, t - LEAD_S)
        h = v.get("hold_s") or (3.8 if v.get("kind") == "title" else 2.4 if v.get("kind") == "cta" else hold)
        picture = v.get("kind") == "capture" or "src" in v
        lead = 0.3 if v.get("layout") in ("scene", "split") else 0   # a scene grows in before its word (plan.SCENE_LEAD_S)
        out.append((round(max(0.0, s - lead), 3), round(min(duration, s + h), 3), v.get("type") or v.get("kind") or "image", picture))
    return sorted(out)


def own_cards(real):
    """The real_cards counted before the number beats: all but a moving template the motion skill may build as a clip
    (budget.CLIP_TEMPLATES, or the clip that replaced one: real_cards reads it as its template). Those come after the
    numbers (references/kinetic.md "Motion clips"): plan.py budget_cards keeps them only in the room the number beats
    leave, and drops one up with a kept number beat."""
    return [r for r in real if r[2] not in budget.CLIP_TEMPLATES]


def rate(style):
    """Graphics a minute in all: budget.per_min, graphics.kinetic_per_min (KINETIC_PER_MIN unset), over the style
    page's cards.per_min; 0 with cards off. Read as on: this runs only once the style opted in."""
    return budget.per_min({**style, "graphics": {**(style.get("graphics") or {}), "kinetic": True}})


def unit(c):
    """What a card counts as in the budget: one graphic, the beats of one tracker together (the same graphic coming
    back, budget.group)."""
    return c.tracker or id(c)


def tight(c):
    return round(c.last + HOLD_TIGHT_S, 3)


def whole(take, c, e):
    """e, or earlier: a card that hides the captions never ends on the first words of a number said after its own
    ("a hundred and" hidden, "sixty-four" shown reads 64): it ends as that number is said, when it still holds
    HOLD_TIGHT_S after its last part. Else plan.py whole_numbers holds it over the whole number."""
    for sp in take.spans:
        t0, t1 = take.t(sp["i0"]), take.w[sp["i1"]]["end"]
        if c.s < t0 < e < t1 + 0.6 and t0 >= tight(c):
            k = sp["i0"] - 1   # its caption page may start a word sooner ("about a" | "hundred and"): end before that word
            return round(take.t(k) if take.sent[k] == take.sent[sp["i0"]] and take.t(k) >= tight(c) else t0, 3)
    return e


def select(cands, real, duration, per_min, take=None):
    """The strongest candidates within the budget (a tracker's beats one graphic), none over a real card (a stat_stack
    may sit beside a capture), GAP_S of footage between any two: a card's hold is cut to HOLD_TIGHT_S for it, a real
    card before one ends sooner when it still holds REAL_MIN_S (plan.py space_kinetic), and a stronger card blocked only by
    the hold of the kinetic card before it bridges from it (that one holds until it starts, plan.py bridge_kinetic; two
    cards at the most, BRIDGE_MAX_S). The next beat of one tracker joins instead. Sets each card's end; none ends on the
    first words of a number said after it (whole)."""
    if per_min <= 0:
        for c in cands:
            c.drop = "cards are off"
        return []
    total = budget.count(per_min, duration)
    room = max(0, total - len(real))
    kept, bridged = [], {}   # bridged: id(card) -> the card it bridges into (its next)
    paired = set()
    for c in sorted(cands, key=lambda c: (-c.score, c.s, c.cls)):
        new = not (c.tracker and any(o.tracker == c.tracker for o in kept))
        if c.cls == "hook" and len({unit(o) for o in kept}) >= room:
            c.note = f"the hook, kept over the budget of {total}: the edit's own cards ({len(real)}) fill it"
        elif new and len({unit(o) for o in kept}) >= room:
            c.drop = f"over the budget ({total} graphics at {per_min:g} a minute, {len(real)} already placed)"
            continue
        if c.cls == "tracker" and not any(o.tracker == c.tracker and o.cls == "fill" for o in kept):
            c.drop = "none of its items is kept: its slots would stay empty"
            continue
        bridge = None
        for o in kept:
            a, b = (o, c) if o.s <= c.s else (c, o)
            if a.tracker and a.tracker == b.tracker and b.s - a.s >= 0.5 and not any(
                    x.tracker == a.tracker and a.s < x.s < b.s for x in kept):
                continue   # the next beat of the same tracker joins it
            if b.s - tight(a) >= GAP_S:
                continue
            if c.score >= BRIDGE_SCORE and b.s - a.last >= BRIDGE_MIN_S and b.e_min - a.s <= BRIDGE_MAX_S and bridge is None \
                    and not {id(a), id(b)} & paired \
                    and not any(a.s < x.s < b.s for x in kept) and not (a.tracker or b.tracker):
                bridge = (a, b)
                continue
            c.drop = f"too close to the {o.cls} at {o.s:.2f} s"
            break
        else:
            for s, e, kind, pic in real:
                if c.type == "stat_stack" and pic and s < c.e_min and c.s < e:
                    continue   # stats beside the capture of them
                if s >= c.s and s - tight(c) < GAP_S or s < c.s and e > c.s - GAP_S and c.s - GAP_S - s < REAL_MIN_S:
                    c.drop = f"too close to the {kind} card at {s:.2f} s"
                    break
        if not c.drop:
            kept.append(c)
            if bridge:
                bridged[id(bridge[0])] = bridge[1]
                paired.update({id(bridge[0]), id(bridge[1])})
    kept.sort(key=lambda c: c.s)
    for c in kept:   # a tracker's beats stand or fall together when plan.py counts the cards (budget.pick)
        c.strength = max(o.score for o in kept if o is c or (c.tracker and o.tracker == c.tracker))
    walls = sorted([(c.s, c) for c in kept] + [(s, None) for s, e, kind, pic in real], key=lambda x: x[0])
    for c in kept:
        if id(c) in bridged:
            c.e = bridged[id(c)].s   # it holds until the next one starts (plan.py bridge_kinetic)
            continue
        e, joined = c.e_want, None
        for s, o in ((s, o) for s, o in walls if s > c.s):
            if o is None and c.type == "stat_stack" and s < c.e_min:
                continue   # the capture it sits beside
            if o is not None and o.tracker and o.tracker == c.tracker and s - c.e_min < 1.0:
                joined = s   # plan.py holds the tracker until its next beat, which carries on from it
            else:
                e = min(e, s - GAP_S)
            break
        if joined is not None:
            c.e = joined
            continue
        e = max(tight(c), e)   # never under HOLD_TIGHT_S; the gap checks above left room for it
        c.e = round(min(duration, whole(take, c, e) if take else e), 3)
    return kept


def find(words, style=None, visuals=(), images=(), duration=None):
    """(kept cards, every candidate) for a take."""
    take = Take(words)
    if not take.w:
        return [], []
    duration = duration or take.w[-1]["end"]
    cands = candidates(take)
    real = own_cards(real_cards(take, visuals, images, style or {}, duration))
    return select(cands, real, duration, rate(style or {}), take), cands


def beats(words, style=None, visuals=(), images=(), duration=None):
    """The visuals.json beats for a take, in spoken order."""
    return [c.beat() for c in find(words, style, visuals, images, duration)[0]]


# ---------------------------------------------------------------- beside the motion skill

# The motion skill's kinds (motion.py KINDS) a clip may take beside kinetic titles: what the number beats do not
# cover, a list, a flow, a before and after, a mechanism (an app at work, a curve). Never a "counter": the numbers are
# the titles'. Nor a "logo" cluster: a real-source card, kept as its template.
MOTION_KINDS = ("list", "flow", "before_after", "ui_demo", "curve")


def split(words, style, visuals=(), images=(), duration=None):
    """With kinetic titles on (graphics.kinetic), what the number beats leave to the motion skill (references/kinetic.md
    "Motion clips"); None when off, or in a split or board layout (plan.py drops kinetic cards there), so route.py and
    motion.py run upstream's way. Else a dict:
    said: every time a number beat says a part, kept or not (the finder would cover that line: it is the titles'), and
          the word of each kinetic beat written by hand;
    kept: [(start, end, word, nth)] the beats the finder keeps (none with graphics.kinetic_auto false) and those written
          by hand (word None: visuals.json has them), as plan.py places them: no clip is up with one;
    units: the graphics the kept automatic beats are (a tracker one; hand-written ones count as the edit's own cards);
    cards: the kept automatic beats as budget.pick ranks them in plan.py (start, end, type and props, strength, hook);
    allowance: budget.allowance for the take; duration: the length it is counted over.
    visuals: the edit's beats as written, a motion clip read as its template; the automatic beats are found again (as
    route.py does), so a pick before plan.py ever ran sees the same beats. duration: the cut's length, as plan.py
    probes it (video_duration), else the last word's end."""
    if not ((style or {}).get("graphics") or {}).get("kinetic") or ((style or {}).get("layout") or {}).get("mode") in ("split", "board"):
        return None
    take = Take(words)
    if not take.w:
        return {"said": [], "kept": [], "units": 0, "cards": [], "allowance": 0, "duration": 0}
    duration = duration or take.w[-1]["end"]
    view = [v.get("fallback") or v for v in visuals]
    kept, cands = find(words, style, [v for v in view if v.get("auto") != AUTO], images, duration)
    kept = kept if auto_on(style) else []
    said = {round(c.s + LEAD_S, 3) for c in cands} | {round(take.t(i), 3) for c in cands for i in c.parts}
    spans = [(c.s, c.e, b["word"], b["nth"]) for c in kept for b in [c.beat()]]
    hand = [v for v in view if v.get("auto") != AUTO and v.get("type") in budget.KINETIC_TYPES]
    for s, e, _, _ in real_cards(take, hand, (), style, duration):   # written by hand (or by a review note): the titles' too
        said.add(round(s + LEAD_S, 3))
        spans.append((s, e, None, None))   # its own beat in visuals.json times the clip before it
    cards = [{"start": c.s, "end": c.e, "anim": {"type": b["type"], "props": b["props"]}, "strength": b["strength"],
              "hook": bool(b.get("hook"))} for c in kept for b in [c.beat()]]
    return {"said": sorted(said), "kept": sorted(spans, key=lambda x: x[:2]), "units": len({unit(c) for c in kept}),
            "cards": cards, "allowance": budget.allowance(style, duration), "duration": duration}


def video_duration(edit):
    """The cut's length in seconds as plan.py reads it (ffprobe of cut.mp4 in the edit folder), or None without one, so
    the budget and the beats found before the plan are counted over the same length as the plan's."""
    import subprocess
    video = Path(edit) / "cut.mp4"
    if not video.exists():
        return None
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return float(out) if out else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


# ---------------------------------------------------------------- the edit

def words_of(edit, words_path=None):
    p = Path(words_path) if words_path else edit / "captions.json" if (edit / "captions.json").exists() else edit / "words.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("words", []) if isinstance(data, dict) else data


def fingerprint(words, real, per_min):
    w = [[x["text"], round(x["start"], 2)] for x in words if x.get("type", "word") == "word"]
    return hashlib.sha1(json.dumps([VERSION, w, real, per_min]).encode("utf-8")).hexdigest()[:16]


def auto_on(style):
    g = style.get("graphics") or {}
    return bool(g.get("kinetic")) and g.get("kinetic_auto", True) is not False


def beat_key(b):
    """A beat's identity from one find to the next: its type, word (and nth for a tracker's beats) and the figures or
    labels it shows, so a review note's change to it is found again after a re-cut."""
    shown_ = re.findall(r'"(?:num|pct|target|label)": "([^"]*)"', json.dumps(b.get("props") or {}, ensure_ascii=False))
    return "|".join([str(b.get("type")), key_of(str(b.get("word", ""))), str(b.get("nth", 1) if b.get("type") == "step_build" else "")]
                     + shown_)


def clear(edit, log=None):
    """The style turned the automatic beats off (graphics.kinetic or graphics.kinetic_auto false): the beats this
    script wrote leave visuals.json, and kinetic.auto.json goes. Hand-written beats stay. Returns how many left."""
    edit = Path(edit)
    vp, sp = edit / "visuals.json", edit / STATE
    visuals = json.loads(vp.read_text(encoding="utf-8")) if vp.exists() else []
    rest = [v for v in visuals if v.get("auto") != AUTO]
    if len(rest) != len(visuals):
        vp.write_text(json.dumps(rest, indent=1), encoding="utf-8")
        print(f"kinetic: automatic beats off, {len(visuals) - len(rest)} removed from visuals.json", file=log or sys.stderr)
    if sp.exists():
        sp.unlink()
    return len(visuals) - len(rest)


def refresh(edit, style, words_path=None, duration=None, force=False, log=None):
    """plan.py's step: the automatic number beats in visuals.json, found again only when the cut's words, the real
    cards or the rate changed (or force). A review note's change to one of them is kept through that: a beat it removed
    stays out, and the fields it changed are laid on the beat found again (kinetic.auto.json "removed" and "edits",
    matched by beat_key; delete that file to start over). Off (auto_on false), it clears the ones it wrote. Returns
    the beats it owns now. Prints one line per beat to log (stderr)."""
    log = log or sys.stderr
    edit = Path(edit)
    if not auto_on(style):
        clear(edit, log)
        return []
    words = words_of(edit, words_path)
    vp, ip, sp = edit / "visuals.json", edit / "images.json", edit / STATE
    visuals = json.loads(vp.read_text(encoding="utf-8")) if vp.exists() else []
    images = json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else []
    take = Take(words)
    if not take.w:
        return []
    duration = duration or take.w[-1]["end"]
    rest = [v for v in visuals if v.get("auto") != AUTO]
    mine = [v for v in visuals if v.get("auto") == AUTO]
    pm = rate(style)
    fp = fingerprint(words, real_cards(take, rest, images, style, duration), pm)
    state = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    if not force and state.get("fingerprint") == fp:
        print(f"kinetic: {len(mine)} automatic number beat{'s' if len(mine) != 1 else ''} kept (same cut, cards and rate; "
              "kinetic_beats.py write --force finds them again)", file=log)
        return mine
    # what the review notes did to the beats written last time: removed ones stay out, changed fields are kept
    written = {beat_key(b): b for b in state.get("written", [])}
    now = {beat_key(b): b for b in mine}
    removed = set(state.get("removed", [])) | {k for k in written if k not in now}
    edits = dict(state.get("edits", {}))
    for k, b in now.items():
        if k in written and b != written[k]:
            edits[k] = {**edits.get(k, {}), **{f: v for f, v in b.items() if written[k].get(f) != v}}
    kept, cands = find(words, style, rest, images, duration)
    new, out = [], []
    for c in kept:
        b = c.beat()
        k = beat_key(b)
        if k in removed:
            out.append(f"  (left out: a review note removed the {b['type']} on '{b['word']}')")
            continue
        new.append({**b, **edits.get(k, {})})
        out.append("  " + c.line() + ("  (kept the review's change)" if k in edits else ""))
    vp.write_text(json.dumps(rest + new, indent=1), encoding="utf-8")
    sp.write_text(json.dumps({"fingerprint": fp, "beats": len(new), "per_min": pm, "written": new, "removed": sorted(removed),
                              "edits": edits}, indent=1), encoding="utf-8")
    print(f"kinetic: {len(new)} number beat{'s' if len(new) != 1 else ''} of {len(cands)} candidates into visuals.json "
          f"({pm:g} graphics a minute in all):", file=log)
    for line in out:
        print(line, file=log)
    return new


def report(kept, cands, out=sys.stdout):
    for c in sorted(cands, key=lambda c: c.s):
        print(("KEPT  " if c in kept else "      ") + c.line() + ("" if c in kept else f"   ({c.drop or 'not chosen'})"), file=out)
    print(f"{len(kept)} kept of {len(cands)} candidates", file=out)


# ---------------------------------------------------------------- demo

def timed(text, t0=0.0, step=0.32):
    """Made-up word timings: each word `step` long, a comma adds 0.15 s, a full stop 0.4 s."""
    out, t = [], t0
    for w in text.split():
        out.append({"text": w, "start": round(t, 2), "end": round(t + step - 0.04, 2), "type": "word"})
        t += step + (0.4 if ends(w, ".!?") else 0.15 if ends(w) else 0)
    return out


BAKERY = ("Our 20k goal for the year is forty percent done. We bake in two stages. The first stage is the starter, and the "
          "second stage is the cold proof. Last spring we handed out three hundred and forty flyers, got sixty tastings, and "
          "booked twelve cafe orders. One cafe paid us 4.5k dollars in three and a half weeks. Next we may add another stage.")
GYM = ("Our little gym opened in a cold garage next to the station. Today eighty members, twelve coaches and 9.2k dollars of "
       "monthly revenue keep it going. Last winter we mailed a hundred and twenty local offices, and most of those letters "
       "were ignored. We also built eighteen workouts for beginners. Train with us.")
PODCAST = ("Our podcast hit 50k downloads in six months. So here's the plan. Step one, we record the episode. Step two, we "
           "cut the clips. Step three, we post every clip. Last week a sponsor paid us 2.5k dollars for one episode. "
           "That is it.")
GARDEN = ("Here is how our garden shop works. We run it on Planner 3 and it costs nothing. We sold thirty-five lemon trees "
          "this spring, and fifty percent of buyers came back. We also sold 1.2k euros of seeds, and eleven raised beds, "
          "and nine hundred bulbs in one week. The other news is the shop. Follow along.")
STALL = ("Our flower stall had a slow start this year, so we tried everything. We baked sixteen kinds of cookies for the market. "
         "Then we mailed three hundred flyers, got forty calls, and booked nine weddings. And we knocked on a hundred and sixty "
         "doors, and most of them refused. That is how it went.")
# Shapes that are no count of things, said as an opening line: no candidate at all, or only the ones named (a sign
# or a part said with a number is that number; a list said over sentences is no funnel; a pronoun "one" ends none).
NOT_FIGURES = [
    ("I wake up at five every day and bake until nine. Then I sleep.", []),
    ("We open at 7:30 and close at 6. People queue at the door.", []),
    ("I was twenty-two when I started. Now I am thirty-five years old.", []),
    ("Call us at 555 1234 or text 0612345678 any time. We answer fast.", []),
    ("Our number is five five five, one two three four. Call any time.", []),
    ("We are at 221 Baker Street. Come and see us.", []),
    ("Our zip code is 90210. Everyone knows it.", []),
    ("Back in twenty twenty-three we opened the shop. It changed everything.", []),
    ("In two thousand and nineteen I quit my job. Then I started baking.", []),
    ("I was born in nineteen ninety-five and I love bread.", []),
    ("I am a hundred percent sure this works. Try it.", []),
    ("We won three to one against the other bakery. It was close.", []),
    ("On June 21 we opened, and on July 4 we closed for a day.", []),
    ("A loaf costs three ninety-nine. That is cheap.", []),
    ("We sell between fifty and sixty loaves a day. Some days more.", []),
    ("One in ten customers buys a cake. The rest buy bread.", []),
    ("Turn to page 42 of the recipe book. It is the best one.", []),
    ("Day 30 of baking every day. Still going.", []),
    ("Bake it at two hundred and twenty degrees for forty minutes. Then let it rest.", []),
    ("Use five hundred grams of flour and three hundred and fifty grams of water. Mix well.", []),
    ("I tried a lot of ovens. This one is the best one I ever had. The other one broke after a week.", []),
    ("It was minus five degrees outside and we still had sixty people in line.", ["hook:60", "counter:60"]),
    ("We sold half a million cookies last year. Insane.", ["hook:500K", "counter:500K"]),
    ("We have eighty members. We also have twelve coaches. And we make 9k a month.", ["hook:80", "counter:80", "tally:12"]),
    ("We baked forty cakes. We sold twelve, and I kept the best one.", ["hook:40", "chain:40>12", "figure:40"]),
    ("I sent sixty messages, got four calls, and that one changed everything.", ["hook:60", "chain:60>4", "counter:60"]),
    ("We made two thousand three hundred and forty-five dollars this month. Not bad.", ["hook:$2,345", "money:$2,345"]),
    ("So. Um. Okay. Let me tell you. This year we made eighty thousand euros from one shop.", ["hook:€80K", "money:€80K"]),
]


def brief(c):
    p = c.beat()["props"]
    if c.cls == "chain":
        return "chain:" + ">".join(i["num"] for i in p["items"])
    return f"{c.cls}:{p.get('num') or p.get('pct') or ''}"


def demo():
    many = {"graphics": {"kinetic": True, "kinetic_per_min": 30}}   # room for every candidate the rules allow
    bake = timed(BAKERY)
    kept, cands = find(bake, many)
    by = {}
    for c in cands:
        by.setdefault(c.cls, c)
    # the bakery: no hook (no count of things in the opening line), a goal, a tracker of two stages with a "?" slot, a funnel
    assert "hook" not in by, by["hook"].line()
    g = by["goal"].beat()["props"]
    assert g == {"pct": "40%", "word_pct": "forty", "count_word": "percent", "target": "20K", "word_target": "20k",
                 "word_goal": "goal"} and by["goal"].beat()["word"] == "20k", g
    ch = by["chain"].beat()["props"]["items"]
    assert [(i["num"], i["label"]) for i in ch] == [("340", "flyers"), ("60", "tastings"), ("12", "cafe orders")], ch
    assert ch[0]["word"] == "three" and ch[2]["label_word"] == "cafe", ch
    tr = [c for c in cands if c.tracker]
    assert [c.cls for c in tr] == ["tracker", "fill", "fill", "question"] and len({c.tracker for c in tr}) == 1, [c.cls for c in tr]
    sl = [c.beat()["props"]["slots"] for c in tr]
    assert [s["label"] for s in sl[0][:2]] == ["starter", "cold proof"] and sl[0][2] == {"state": "off"}, sl[0]
    assert sl[0][0]["word"] == "two" and [s["state"] for s in sl[2]] == ["filled", "filled", "off"] and sl[2][1]["word"] == "cold", sl
    assert sl[3][2] == {"state": "question", "word": "another"}, sl[3]
    assert tr[1].beat()["word"] == "first" and tr[2].beat()["word"] == "second", "an item's beat starts on its cue"
    assert tr[1].score == SCORE["fill"] + 2 + ENUM_BONUS, "a tracker of stages is the take's spine: it ranks with a stat run"
    assert by["money"].beat()["props"]["num"] == "$4.5K"

    gym = timed(GYM)
    kept, cands = find(gym, many)
    by = {c.cls: c for c in cands}   # the last of each
    st = by["stat"].beat()["props"]["stats"]
    assert [(s["num"], s.get("label")) for s in st] == [("80", "members"), ("12", "coaches"), ("$9.2K", "monthly revenue")], st
    co = next(c for c in cands if c.cls == "counter" and "stamp" in c.props).beat()["props"]
    assert co["num"] == "120" and co["variant"] == "counter" and co["stamp"] == {"text": "ignored", "word": "ignored"}, co
    assert [x["text"] for x in co["sub"]] == ["local", "offices"] and co["land_word"] == "local" and co["word"] == "hundred", co
    ta = by["tally"].beat()["props"]
    assert ta["num"] == "18" and ta["variant"] == "tally" and [x["text"] for x in ta["sub"]] == ["workouts"], ta
    assert "hook" not in by and "chain" not in by, "no figure in the opening line; 80 members, 12 coaches and $9.2K is a list"

    pod = timed(PODCAST)
    kept, cands = find(pod, many)
    by = {c.cls: c for c in reversed(cands)}
    hp = by["hook"].beat()["props"]
    assert hp["num"] == "50K" and [x["text"] for x in hp["sub"]] == ["in", "6", "months"], hp
    steps = [c.beat() for c in cands if c.tracker]
    assert [s["props"]["slots"][k]["label"] for k, s in enumerate(steps)] == ["record", "cut", "post"], steps
    assert [(s["word"], s["nth"]) for s in steps] == [("Step", 1), ("Step", 2), ("Step", 3)], "ordinals, no count said"
    assert [x["state"] for x in steps[0]["props"]["slots"]] == ["filled", "empty", "empty"], steps[0]
    assert by["money"].beat()["props"]["num"] == "$2.5K" and "sub" not in by["money"].beat()["props"]
    # steps with no plain noun are named by their verb; a list of names doing a step, by the verb they do it with
    rt = timed("Our bakery runs on a simple routine every day. There are three steps to this. Step one is quick: you weigh "
               "the flour. Now for step two, Planner Pro, Oven Mate, and Timer Box mix it. Step three is where we bake.")
    sl = [c.beat()["props"]["slots"] for c in find(rt, many)[1] if c.tracker]
    assert [x["label"] for x in sl[0]] == ["weigh", "mix", "bake"] and len(sl) == 4, sl

    gar = timed(GARDEN)
    cands = find(gar, {"graphics": {"kinetic": True}})[1]
    nums = [n for c in cands for n in re.findall(r'"num": "([^"]+)"', json.dumps(c.beat()))]
    assert "3" not in nums and "1" not in nums, ("a name's number (Planner 3) and a lone 'one' are never a figure", nums)
    assert {c.beat()["props"]["num"] for c in cands if c.cls == "figure"} == {"35", "50%"}, [c.line() for c in cands]
    st = [[(s["num"], s["label"]) for s in c.beat()["props"]["stats"]] for c in cands if c.cls == "stat"]
    assert st == [[("35", "lemon trees"), ("50%", "buyers")], [("€1.2K", "seeds"), ("11", "raised beds"), ("900", "bulbs")]], st
    assert not [c for c in cands if c.tracker], "'the other news' is no item: no count or ordinals were said"

    # what is no count of things never becomes a card: times, ages, phone digits, addresses, years, dates, prices,
    # ranges, ratios, names' numbers, measures, a pronoun "one", a sign or a part said with the number
    for text, want in NOT_FIGURES:
        got = sorted({brief(c) for c in find(timed(text), {"graphics": {"kinetic": True, "kinetic_per_min": 60}})[1]})
        assert got == sorted(want), (text, got)

    # grounding: every figure is one check.py reads as said; every label word is said, and none is a number or a date
    from check import said_numbers
    for ws in [bake, gym, pod, gar, timed(STALL)] + [timed(t) for t, _ in NOT_FIGURES]:
        said, pct, _ = said_numbers(" ".join(w["text"] for w in ws))
        vocab = {low(w["text"]) for w in ws}
        for c in find(ws, {"graphics": {"kinetic": True, "kinetic_per_min": 60}})[1]:
            b = json.dumps(c.beat(), ensure_ascii=False)
            for n in re.findall(r'"(?:num|pct|target)": "([^"]+)"', b):
                assert all(numbers.norm(w["value"]) in said and (w["kind"] != "percent" or numbers.norm(w["value"]) in pct)
                           for w in numbers.written(n)), (n, c.line())
            for t in re.findall(r'"(?:label|text)": "([^"]+)"', b):
                assert all(low(x) in vocab or numbers.written(x) for x in t.split()), (t, c.line())
            for t in re.findall(r'"label": "([^"]+)"', b):
                assert not any(numword(low(x)) or low(x) in CALENDAR for x in t.split()), (t, c.line())

    # ranking and density: 8 a minute over the 23 s bakery take is 3 graphics, a tracker's beats one of them
    k8 = find(bake, {"graphics": {"kinetic": True}})[0]
    assert [c.cls for c in k8] == ["goal", "fill", "fill", "chain", "question"], [c.line() for c in k8]
    assert [c.cls for c in find(pod, {"graphics": {"kinetic": True, "kinetic_per_min": 1}})[0]] == ["hook"], "the hook stays"
    assert find(bake, {"graphics": {"kinetic": True}, "cards": {"on": False}})[0] == [], "cards off: none"
    assert [c.line() for c in find(bake, {**many, "cards": {"per_min": 4}})[0]] == [c.line() for c in find(bake, many)[0]], \
        "the graphics budget wins over the style page's cards.per_min (budget.py)"
    sb = beats(pod, {"graphics": {"kinetic": True}})
    assert sb[0]["hook"] is True and sb[0]["strength"] == 1.0 and not any(b.get("hook") for b in sb[1:]), sb
    assert len({b["strength"] for b in sb if b["type"] == "step_build"}) == 1, "a tracker's beats share their strength"
    # the strongest win, not the first come: a counter blocked only by a chain's hold bridges from it (the chain holds
    # until it starts) and the weaker tally loses the last place
    stall = timed(STALL)
    ks = find(stall, {"graphics": {"kinetic": True, "kinetic_per_min": 6}})[0]
    assert [c.cls for c in ks] == ["chain", "counter"] and ks[0].e == ks[1].s, [c.line() for c in ks]
    assert [c.cls for c in find(stall, {"graphics": {"kinetic": True, "kinetic_per_min": 9}})[0]] == ["tally", "chain", "counter"]
    # a card never ends on the first words of a number said after it: it ends as that number starts
    nx = timed("It was a quiet month at the shop, so we tried the post. We sent ninety letters, got twelve replies, and signed four deals. And about a hundred and twenty people "
               "ignored us. Fine.")
    k1 = find(nx, {"graphics": {"kinetic": True, "kinetic_per_min": 3}})[0]
    a_ = next(w["start"] for w, x in zip(nx, nx[1:]) if w["text"] == "a" and x["text"] == "hundred")
    assert [c.cls for c in k1] == ["chain"] and k1[0].e == a_, ([c.line() for c in k1], a_)
    # plain footage between cards: GAP_S between any two kept, except a tracker's next beat or a bridge, which join
    for ws in (bake, gym, pod, gar, stall):
        ks = find(ws, {"graphics": {"kinetic": True, "kinetic_per_min": 60}})[0]
        for a, b in zip(ks, ks[1:]):
            assert b.s - a.e >= GAP_S - 1e-6 or a.e == b.s, (a.line(), b.line())
        assert all(c.last < c.e and (c.e >= c.last + HOLD_TIGHT_S - 1e-6 or any(o.s == c.e for o in ks) or c.e == ws[-1]["end"])
                   for c in ks), \
            [c.line() for c in ks]
    # a real card (the user's photo on "flyers") takes the chain's place and its share of the budget
    kr = find(bake, {"graphics": {"kinetic": True}}, images=[{"src": "images/flyer.png", "word": "flyers", "nth": 1, "hold_s": 3}])[0]
    assert "chain" not in {c.cls for c in kr} and len({unit(c) for c in kr}) == 2, [c.line() for c in kr]
    # ... and a capture beat with its fetched image is one card, not two
    cap = [{"kind": "capture", "word": "flyers", "nth": 1, "url": "https://example.com/flyer"}]
    kc = find(bake, {"graphics": {"kinetic": True}}, visuals=cap, images=[{"src": "images/capture-1-flyers.png", "word": "flyers", "nth": 1}])[0]
    assert len({unit(c) for c in kc}) == 2, [c.line() for c in kc]
    # a real card ending under GAP_S before a kinetic card ends sooner (plan.py space_kinetic) when it holds REAL_MIN_S
    near = [{"src": "images/stall.png", "word": "slow", "nth": 1, "hold_s": 4.4}]   # 1.7-6.1 s, the tally at 5.25 s
    assert "tally" in {c.cls for c in find(stall, many, images=near)[0]}
    # a stat_stack may sit beside the capture of its own figures; nothing else goes under a real card
    cap = [{"kind": "capture", "word": "coaches", "nth": 1, "url": "https://example.com/stats", "hold_s": 3}]
    kg = find(gym, many, visuals=cap)[0]
    assert {"stat", "counter"} <= {c.cls for c in kg}, [c.line() for c in kg]
    assert "tally" not in {c.cls for c in find(gym, many, visuals=[{**cap[0], "word": "eighteen"}])[0]}
    # a moving template the motion skill may build as a clip counts after the number beats: where the photo above took
    # the chain's place and a share, the same list template (or its placed clip) takes neither
    tp = [{"word": "flyers", "nth": 1, "kind": "anim", "type": "notes", "hold_s": 3}]
    clip = [{"word": "flyers", "nth": 1, "kind": "anim", "type": "video_card", "motion": "01-flyers", "fallback": tp[0]}]
    alone = [c.line() for c in find(bake, {"graphics": {"kinetic": True}})[0]]
    assert [c.line() for c in find(bake, {"graphics": {"kinetic": True}}, visuals=tp)[0]] == alone
    assert [c.line() for c in find(bake, {"graphics": {"kinetic": True}}, visuals=clip)[0]] == alone
    # ... and the hook is kept when the edit's own cards fill the budget, saying so (2 photos, 1 graphic at 4 a minute)
    two = [{"src": f"images/{w}.png", "word": w, "nth": 1} for w in ("record", "post")]
    kh = find(timed(PODCAST), {"graphics": {"kinetic": True, "kinetic_per_min": 4}}, images=two)[0]
    assert [c.cls for c in kh] == ["hook"] and "kept over the budget" in kh[0].line(), [c.line() for c in kh]
    demo_plan(bake)
    demo_refresh(bake)
    n = sum(len(find(timed(t), {"graphics": {"kinetic": True}})[1]) for t in (BAKERY, GYM, PODCAST, GARDEN, STALL))
    print(f"kinetic_beats ok ({n} candidates in 5 made-up takes, {len(NOT_FIGURES)} shapes that are no count)")


def demo_plan(bake):
    """plan.py reads the beats as written: each lands on its word, every part timed, in the kinetic lane."""
    import plan
    meta = {"video": "cut.mp4", "width": 1080, "height": 1920, "fps": 30, "duration": bake[-1]["end"] + 0.5}
    st = {"graphics": {"kinetic": True, "kinetic_per_min": 30}}
    vis = beats(bake, st)
    p = plan.build({**st, "captions": {"words_per_caption": 3}}, bake, meta, visuals=vis)
    kc = [c for c in p["cards"] if c.get("lane") == "kinetic"]
    assert len(kc) == len(vis) and p["kinetic"] is True, (len(kc), len(vis))
    # at the default rate plan.py's own count (budget.py) keeps exactly the beats the finder chose
    v8 = beats(bake, {"graphics": {"kinetic": True}})
    p8 = plan.build({"graphics": {"kinetic": True}, "captions": {"words_per_caption": 3}}, bake, meta, visuals=v8)
    assert [c["trigger_word"] for c in p8["cards"]] == [b["word"] for b in v8], (p8["cards"], v8)
    first = {c["anim"]["type"]: c for c in reversed(kc)}
    assert first["number_chain"]["anim"]["props"]["items"][2]["label_at"] > 0, first["number_chain"]
    gb = first["goal_bar"]["anim"]["props"]
    # "our 20k goal is forty percent done": the card comes up on the target, the % lands on its own word after
    assert 0 < gb["at_target"] < gb["at_goal"] < gb["at_pct"] < gb["count_at"], gb
    pod = timed(PODCAST)
    pp = plan.build({**st, "captions": {"words_per_caption": 3}}, pod, {**meta, "duration": pod[-1]["end"] + 0.5}, visuals=beats(pod, st))
    hk = pp["cards"][0]
    assert hk["anim"]["props"]["sub"][1]["at"] > hk["anim"]["props"]["at"], hk
    # a number card held past the start of a number said after it (a review note's long hold) never cuts it in half:
    # plan.py whole_numbers ends it as that number's first page starts, and check.py plan FAILs a plan that does not
    nx = timed("It was a quiet month at the shop, so we tried the post. We sent ninety letters, got twelve replies, and "
               "signed four deals. And about a hundred and twenty people ignored us. Fine.")
    v = beats(nx, {"graphics": {"kinetic": True, "kinetic_per_min": 3}})
    mid = next(w["end"] for w, x in zip(nx, nx[1:]) if w["text"] == "hundred" and x["text"] == "and") + 0.05
    v[0]["hold_s"] = round(mid - (next(w["start"] for w in nx if w["text"] == "ninety") - LEAD_S), 2)
    a_ = next(w["start"] for w, x in zip(nx, nx[1:]) if w["text"] == "a" and x["text"] == "hundred")
    stw = {**st, "captions": {"words_per_caption": 2}}
    px = plan.build(stw, nx, {**meta, "duration": nx[-1]["end"] + 0.5}, visuals=v)
    chunks, card = px["captions"]["chunks"], px["cards"][0]
    first = next(c for c in chunks if any(abs(w["start"] - a_) < 1e-6 for w in c["words"]))
    assert card["end"] == round(first["start"], 3), (card["end"], first)
    assert plan.split_numbers(px["cards"], chunks, nx) == []
    from check import check_plan
    bad = {**px, "cards": [{**card, "end": round(mid, 3)}]}
    assert plan.split_numbers(bad["cards"], chunks, nx) and any("hides the captions over the start of" in f["what"] and
                                                              f["level"] == "FAIL" for f in check_plan(bad)), "check.py plan FAILs it"


def demo_refresh(bake):
    """refresh(): writes its beats into visuals.json beside the hand-written ones, keeps them (and a change made to
    one) while nothing changes; finds them again when the words do, a review note's removal and changes kept; clears
    them when the style turns them off."""
    import tempfile
    import io
    d = Path(tempfile.mkdtemp(prefix="kinetic_beats_"))
    (d / "words.json").write_text(json.dumps(bake), encoding="utf-8")
    mine = [{"kind": "capture", "word": "flyers", "nth": 1, "url": "https://example.com/flyers", "format": "sticker"}]
    (d / "visuals.json").write_text(json.dumps(mine), encoding="utf-8")
    style = {"graphics": {"kinetic": True}}
    quiet = io.StringIO()
    vis_now = lambda: json.loads((d / "visuals.json").read_text(encoding="utf-8"))  # noqa: E731
    assert refresh(d, {"graphics": {}}, log=quiet) == [] and vis_now() == mine
    new = refresh(d, style, log=quiet)
    vis = vis_now()
    assert vis[0] == mine[0] and vis[1:] == new and all(v["auto"] == AUTO for v in new) and new[0]["type"] == "goal_bar", vis
    units = {(b["props"].get("id") if b["type"] == "step_build" else i) for i, b in enumerate(new)}
    assert len(units) == budget.allowance(style, bake[-1]["end"]) - 1, new   # the capture counted first
    # a review note removes the goal bar and shortens the first fill
    vis = [v for v in vis if v.get("type") != "goal_bar"]
    vis[1]["hold_s"] = 2.0
    (d / "visuals.json").write_text(json.dumps(vis), encoding="utf-8")
    assert refresh(d, style, log=quiet) == vis[1:], "kept while the cut, the cards and the rate are the same"
    (d / "words.json").write_text(json.dumps(bake[:-6]), encoding="utf-8")   # a re-cut: the beats are found again ...
    again = refresh(d, style, log=quiet)
    assert "goal_bar" not in {b["type"] for b in again} and again[0]["hold_s"] == 2.0, again   # ... the note's changes kept
    st = json.loads((d / STATE).read_text(encoding="utf-8"))
    assert len(st["removed"]) == 1 and st["removed"][0].startswith("goal_bar|") and list(st["edits"].values()) == [{"hold_s": 2.0}], st
    assert refresh(d, style, force=True, log=quiet) == again
    # turned off (kinetic_auto false, or kinetic off): the beats it wrote leave visuals.json, hand-written ones stay
    assert refresh(d, {"graphics": {"kinetic": True, "kinetic_auto": False}}, log=quiet) == [] and vis_now() == mine
    assert not (d / STATE).exists()


# ---------------------------------------------------------------- CLI

def main():
    a = sys.argv[1:]
    if a == ["demo"]:
        return demo()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["find", "write", "words"])
    ap.add_argument("path", help="the edit folder (find, write) or a word-timed transcript (words)")
    ap.add_argument("--style", help="style.json (default: the edit's, with the user's settings over it)")
    ap.add_argument("--per-min", type=float, help="graphics a minute in all (default: graphics.kinetic_per_min, else 8)")
    ap.add_argument("--force", action="store_true", help="write: find them again even when nothing changed")
    ap.add_argument("--json", action="store_true", help="words: print the visuals.json beats")
    o = ap.parse_args()
    p = Path(o.path)
    if o.cmd == "words":
        data = json.loads(p.read_text(encoding="utf-8"))
        words = data.get("words", []) if isinstance(data, dict) else data
        style = {"graphics": {"kinetic": True, **({"kinetic_per_min": o.per_min} if o.per_min is not None else {})}}
        kept, cands = find(words, style)
        if o.json:
            print(json.dumps([c.beat() for c in kept], indent=1))
        else:
            report(kept, cands)
        return
    if o.style:
        style = json.loads(Path(o.style).read_text(encoding="utf-8"))
    else:
        from plan import effective_style
        from ai_editor import profile
        style = effective_style(p / "style.json", profile.load(), p, count=False)
    style = {**style, "graphics": {**(style.get("graphics") or {}), "kinetic": True}} if o.cmd == "find" else style
    if o.per_min is not None:
        style["graphics"] = {**(style.get("graphics") or {}), "kinetic_per_min": o.per_min}
    if o.cmd == "write":
        if not auto_on(style):
            sys.exit("this style has not opted into kinetic titles (graphics.kinetic) or turned the automatic beats off "
                     "(graphics.kinetic_auto false); nothing written")
        refresh(p, style, force=o.force, log=sys.stdout)
        return
    vis = json.loads((p / "visuals.json").read_text(encoding="utf-8")) if (p / "visuals.json").exists() else []
    imgs = json.loads((p / "images.json").read_text(encoding="utf-8")) if (p / "images.json").exists() else []
    kept, cands = find(words_of(p), style, [v for v in vis if v.get("auto") != AUTO], imgs)
    report(kept, cands)


if __name__ == "__main__":
    main()
