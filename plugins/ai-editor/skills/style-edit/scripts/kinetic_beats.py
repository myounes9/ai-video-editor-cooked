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
   their sentence and clause (punctuation; a pause over 0.8 s ends a sentence too):
   - hook: the first money, count or percent figure in the first 3 s or the first sentence; its sub-line is a
     duration said in the same sentence ("in 3.5 weeks"), else the figure's own label.
   - chain (number_chain): 2-4 counts, each in its own clause, within CHAIN_S, each smaller than the one before (a
     funnel: flyers -> tastings -> one signed).
   - goal (goal_bar): a percent with "goal", "target" or "of the way" in its sentence, and a scaled figure there.
   - stat run (stat_stack): 2-4 labelled figures in one sentence that count different things.
   - counter: one count of COUNTER_MIN or more with a label; a stamp when an outcome word (rejected, ignored, failed,
     ghosted, lost ...) follows in the sentence. tally: 5-30 of a plural thing. money: a lone money figure. figure:
     a lone percent or a count of 31-49 (both kinetic_number).
   - step tracker (step_build): an enumeration ("two main kinds of bread", "three layers", then "one is" / "the
     other is" / "layer two is" / "step three," ...), one beat when the count is said and one per item, each item
     filled on its label; "another <same noun>" later adds a "?" slot. Each beat is its own candidate.
2. Labels: 1-2 of the transcript's own words next to the number (the noun after it, else the verb before it), as said;
   the renderer sets them in capitals. A figure is written from what was said: "4.5k dollars" -> "$4.5K", "three hundred
   and forty" -> "340", K/M/B only when one was said (check.py plan grounds every figure again).
3. Ranking and density: hook > chain = goal > stat run > counter > money > figure = tally > tracker beats (an item's
   fill before the count's empty wells, kept only with a fill), adjusted
   for clarity (labels, a stamp, more items). The strongest are kept, at most round(per_min x minutes) graphics in
   all, the real cards already placed (images.json, visuals.json captures, posts, logos, titles, hand-written kinetic
   beats) counted first. The hook is always kept. Between any two cards GAP_S of plain footage (the next beat of the
   same tracker joins instead); never over a real card, except a stat_stack beside a capture.

Settings (style.json, taste.json): graphics.kinetic (on), graphics.kinetic_per_min (KINETIC_PER_MIN, every graphic a
minute, real ones included), graphics.kinetic_auto (false: only hand-written kinetic beats). The user's cards.per_min
caps the rate (plan.py thin_cards would cut evenly past it); cards.on false places none.

refresh() keeps its beats ("auto": "kinetic" in visuals.json) while the cut's words, the real cards and the rate stay
the same (kinetic.auto.json holds their fingerprint), so a review note's change to one survives the next plan; any of
those changing finds them again. Stdlib only, deterministic.
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
from ai_editor import numbers  # noqa: E402

VERSION = 1            # bump when the rules change: the fingerprint changes and every edit's beats are found again
KINETIC_PER_MIN = 8    # graphics a minute in all (real captures and screenshots included), graphics.kinetic_per_min
GAP_S = 1.0            # plain footage kept between two kinetic cards (plan.py bridges any closer than its 1 s)
REAL_GAP_S = 0.5       # and at the least beside a real card (GAP_S when the beat's hold allows it)
LEAD_S = 0.1           # plan.CARD_LEAD_S: a card starts this long before its word
HOLD_MIN_S = 1.5       # a lockup stays this long after its last word at the least (1.2 s still + its landing)
HOLD_WANT_S = 2.0      # and this long when nothing follows soon
HOOK_S = 3.0           # a figure said this early is the hook, whatever the first sentence's length
CHAIN_S = 8.0          # a chain's figures are said within this
CHAIN_STEP_S = 5.0     # and each within this of the one before
COUNTER_MIN = 50       # a count this big counts up
TALLY = (5, 30)        # a count in this range of a plural thing fills tiles
TRACKER_S = 40.0       # a tracker's items are said within this of its count
SCORE = {"hook": 100, "chain": 80, "goal": 80, "stat": 70, "counter": 60, "money": 50, "figure": 45, "tally": 45,
         "fill": 30, "tracker": 22, "question": 20}   # a tracker's count alone is empty wells: kept only with a fill
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


def low(text):
    return re.sub(r"^[^\w€$£%]+|[^\w€$£%]+$", "", text.lower().replace("’", "'"))


def shown(text):
    """A word as said, for the screen: no punctuation round it, its own case ("SaaS")."""
    return re.sub(r"^[^\w€$£]+|[^\w%]+$", "", text.replace("’", "'"))


def ends(text, marks=",.;:!?"):
    return text.rstrip().rstrip("\"')]”’").endswith(tuple(marks))


def plural(w):
    return w in IRREGULAR or (len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")))


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
            if c in STOP or numbers.DIGITS.fullmatch(c) or c in numbers.UNITS or c in numbers.TENS:
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
    """The figure as drawn, from what was said: "$4.5K", "340", "1,200", "40%". K/M/B only when one was said."""
    v, said = sp["value"], " ".join(take.low[sp["i0"]:sp["i1"] + 1])
    if sp["kind"] == "percent":
        return numbers.norm(v) + "%"
    scaled = bool(re.search(r"\d(k|m|bn|b)\b", said)) or any(t in numbers.SCALE for t in re.split(r"[\s-]+", said))
    if scaled and v >= 1000:
        for div, suf in ((10 ** 9, "B"), (10 ** 6, "M"), (1000, "K")):
            if v >= div:
                body = numbers.norm(v / div) + suf
                break
    else:
        body = f"{int(v):,}" if v == int(v) else numbers.norm(v)
    return (currency(take, sp) if sp["kind"] == "money" else "") + body


def currency(take, sp):
    """The sign of the currency said with a money figure (in the word, or the word after or before it); "" for MRR."""
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
    if after:
        return after, "after"
    k = sp["i0"] - 1
    while k >= 0 and (take.low[k] in FILLERS or k == sp["i0"] - 1 and take.low[k] in OBJECTS):
        k -= 1
    if k >= 0 and take.sent[k] == take.sent[sp["i0"]] and not ends(take.w[k]["text"]) and take.low[k] not in STOP \
            and not numbers.DIGITS.fullmatch(take.low[k]) and take.low[k] not in WEAK and re.fullmatch(r"[a-z'-]+", take.low[k]):
        return [k], "before"
    return [], None


def figures(take):
    """The spoken numbers worth a graphic: each with its sentence, clause, label and how it is drawn. Leaves out a
    duration (a sub-line, never a figure), a year, a name's number ("GPT-4", "Opus 5.5", "layer one": an ordinal the
    tracker reads) and a lone "one" ("one is", "one of"), which only ends a chain."""
    out = []
    for sp in take.spans:
        i0, i1 = sp["i0"], sp["i1"]
        raw = [take.w[i]["text"] for i in range(i0, i1 + 1)]
        if any(re.search(r"[a-z]", r.lower()) and re.search(r"\d", r) and not numbers.DIGITS.fullmatch(low(r)) for r in raw):
            continue   # glued to a name: "GPT-4", "V2"
        prev = take.low[i0 - 1] if i0 else ""
        prev_raw = take.w[i0 - 1]["text"] if i0 else ""
        if prev in STEP_NOUNS or prev == "number" or (prev_raw[:1].isupper() and prev not in STOP | CALENDAR and i0 and
                                                       take.sent[i0 - 1] == take.sent[i0] and take.sent_range(take.sent[i0])[0] != i0 - 1
                                                       and not ends(prev_raw)):
            continue   # an ordinal or a version: "step one", "Opus 5.5"
        v = sp["value"]
        if sp["kind"] == "count" and v == int(v) and 1900 <= v <= 2100 and re.fullmatch(r"\d{4}", low(raw[0])):
            continue   # a year
        f = dict(sp, sent=take.sent[i0], clause=take.clause[i0], t=take.t(i0), text=figure_text(take, sp))
        f["label"], f["label_from"] = label_of(take, sp)
        f["weak"] = v <= 1 and sp["kind"] == "count"
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
        return {"word": shown(tk.w[self.i0]["text"]), "nth": tk.nth(self.i0), "kind": "anim", "type": self.type,
                "hold_s": round(self.e - self.s, 2), "props": props, "auto": AUTO}

    def line(self):
        said = " ".join(self.take.w[i]["text"] for i in range(self.i0, min(len(self.take.w), self.i0 + 8)))
        return f"{self.s:6.2f}-{self.e:6.2f}  {self.cls:8} {self.type:14} {self.score:5.1f}  {said[:60]}"


def label_parts(take, f, key="label", word="_label_word"):
    if not f["label"]:
        return {}
    return {key: take.text(f["label"]), word: f["label"][0]}


def clarity(fs):
    """+3 a figure whose label reads (1-2 words), -8 one with none."""
    return sum(3 if f["label"] else -8 for f in fs)


def hook(take, figs):
    first = take.sent_range(0)[1] if take.w else -1
    for f in figs:
        if f["weak"] or f["kind"] not in ("money", "count", "percent"):
            continue
        if f["i0"] > first and f["t"] > HOOK_S:
            return None
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


def chains(take, figs):
    """Every funnel: 2-4 counts, each in its own clause and smaller than the one before, close together."""
    counts = [f for f in figs if f["kind"] == "count" and f["label"]]
    out = []
    for a in range(len(counts)):
        if counts[a]["weak"]:
            continue
        run = [counts[a]]
        for f in counts[a + 1:]:
            p = run[-1]
            if p["weak"] or len(run) == 4:
                break
            if f["value"] >= p["value"] or f["clause"] == p["clause"] or f["t"] - p["t"] > CHAIN_STEP_S \
                    or f["t"] - run[0]["t"] > CHAIN_S:
                break
            if any(g["kind"] != "count" and p["i1"] < g["i0"] < f["i0"] for g in figs):
                break   # a money figure or a percent between: two different things
            run.append(f)
        if len(run) < 2 or run[0]["value"] < 3:
            continue
        if len({f["sent"] for f in run}) == 1 and any(g["sent"] == run[0]["sent"] and not g["weak"] and g not in run for g in figs):
            continue   # "80 members, 12 coaches and 9.2k in revenue": a list of stats, not a funnel
        items = [{"num": f["text"], "_word": f["word"], **label_parts(take, f)} for f in run]
        parts = [f["word"] for f in run] + [f["label"][0] for f in run]
        out.append(Card(take, "chain", run[0]["word"], {"items": items}, parts,
                        SCORE["chain"] + 4 * (len(run) - 2) + clarity(run) / len(run), f"{len(run)} counts, each smaller"))
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
        out.append(Card(take, "goal", f["word"], props, parts, SCORE["goal"], "a percent of a goal"))
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


def item_label(take, j, end):
    """A tracker item's label: the noun phrase after the cue's "is", ":" or "," (its article passed over)."""
    lab = take.phrase(j, end, LEAD_SKIP)
    return lab if lab and take.low[lab[0]] not in DULL else []


def cue_items(take, a, limit_t):
    """The enumerated items said after word a: [(cue word, label words, ordinal or None)], in order."""
    out = []
    for c in sorted({take.clause[i] for i in range(a, len(take.w)) if take.t(i) <= limit_t}):
        i = max(a, take.clause.index(c))
        b1 = take.sent_range(take.sent[i])[1]
        while i <= b1 and take.low[i] in OPENERS:
            i += 1
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
        cards = [Card(take, cls, i0, {"id": tid, "slots": st}, parts, SCORE[cls] + (2 if n else 0), why, tracker=tid)
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
    logos, anims, titles and ctas, and kinetic beats written by hand), at its word, for the budget and the gaps."""
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
    for v in list(visuals) + list(images):
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


def rate(style):
    """Graphics a minute in all: graphics.kinetic_per_min (KINETIC_PER_MIN), under the user's cards.per_min; 0 with
    cards off."""
    g = style.get("graphics") or {}
    cfg = style.get("cards") or {}
    if cfg.get("on") is False:
        return 0.0
    pm = g.get("kinetic_per_min")
    pm = KINETIC_PER_MIN if pm is None else float(pm)
    return min(pm, float(cfg["per_min"])) if cfg.get("per_min") is not None else pm


def select(cands, real, duration, per_min):
    """The strongest candidates within the budget, none over a real card (a stat_stack may sit beside a capture),
    GAP_S of footage between any two (the next beat of one tracker joins instead). Sets each card's end."""
    if per_min <= 0:
        for c in cands:
            c.drop = "cards are off"
        return []
    total = round(per_min * duration / 60)
    budget = max(0, total - len(real))
    kept = []
    for c in sorted(cands, key=lambda c: (-c.score, c.s, c.cls)):
        if c.cls != "hook" and len(kept) >= budget:
            c.drop = f"over the budget ({total} graphics at {per_min:g} a minute, {len(real)} already placed)"
            continue
        if c.cls == "tracker" and not any(o.tracker == c.tracker and o.cls == "fill" for o in kept):
            c.drop = "none of its items is kept: its slots would stay empty"
            continue
        for o in kept:
            a, b = (o, c) if o.s <= c.s else (c, o)
            if a.tracker and a.tracker == b.tracker and b.s - a.s >= 0.5 and not any(
                    x.tracker == a.tracker and a.s < x.s < b.s for x in kept):
                continue   # the next beat of the same tracker joins it
            if b.s - a.e_min < GAP_S:
                c.drop = f"too close to the {o.cls} at {o.s:.2f} s"
                break
        else:
            for s, e, kind, pic in real:
                if c.type == "stat_stack" and pic and s < c.e_min and c.s < e:
                    continue   # stats beside the capture of them
                if s - c.e_min < REAL_GAP_S and c.s - e < REAL_GAP_S:
                    c.drop = f"too close to the {kind} card at {s:.2f} s"
                    break
        if not c.drop:
            kept.append(c)
    kept.sort(key=lambda c: c.s)
    walls = sorted([(c.s, c) for c in kept] + [(s, None) for s, e, kind, pic in real], key=lambda x: x[0])
    for c in kept:
        e, joined = c.e_want, None
        for s, o in ((s, o) for s, o in walls if s > c.s):
            if o is None and c.type == "stat_stack" and s < c.e_min:
                continue   # the capture it sits beside
            if o is not None and o.tracker and o.tracker == c.tracker and s - c.e_min < 1.0:
                joined = s   # plan.py holds the tracker until its next beat, which carries on from it
            else:
                e = min(e, s - GAP_S)   # never under e_min: beside a real card the gap may be REAL_GAP_S
            break
        c.e = joined if joined is not None else round(min(duration, max(c.e_min, e)), 3)
    return kept


def find(words, style=None, visuals=(), images=(), duration=None):
    """(kept cards, every candidate) for a take."""
    take = Take(words)
    if not take.w:
        return [], []
    duration = duration or take.w[-1]["end"]
    cands = candidates(take)
    real = real_cards(take, visuals, images, style or {}, duration)
    return select(cands, real, duration, rate(style or {})), cands


def beats(words, style=None, visuals=(), images=(), duration=None):
    """The visuals.json beats for a take, in spoken order."""
    return [c.beat() for c in find(words, style, visuals, images, duration)[0]]


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


def refresh(edit, style, words_path=None, duration=None, force=False, log=None):
    """plan.py's step: the automatic number beats in visuals.json, found again only when the cut's words, the real
    cards or the rate changed (or force). Returns the beats it owns now. Prints one line per beat to log (stderr)."""
    log = log or sys.stderr
    edit = Path(edit)
    if not auto_on(style):
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
    kept, cands = find(words, style, rest, images, duration)
    new = [c.beat() for c in kept]
    vp.write_text(json.dumps(rest + new, indent=1), encoding="utf-8")
    sp.write_text(json.dumps({"fingerprint": fp, "beats": len(new), "per_min": pm}, indent=1), encoding="utf-8")
    print(f"kinetic: {len(new)} number beat{'s' if len(new) != 1 else ''} of {len(cands)} candidates into visuals.json "
          f"({pm:g} graphics a minute in all):", file=log)
    for c in kept:
        print("  " + c.line(), file=log)
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


BAKERY = ("We made 4.5k dollars in three and a half weeks, and here's everything we did to get there. So we bake two main "
          "kinds of bread. One is a sourdough that we launched last month, and the other is a seeded rye. To find buyers we "
          "printed three hundred and forty flyers. We got six cafe tastings, and we were able to sign one. And right now we "
          "are at forty percent of our 20k goal, and we need another kind of bread to get there.")
GYM = ("This year our little gym grew a lot. Right now we have eighty members, twelve coaches, and 9.2k dollars in "
       "monthly revenue. To get there I sent a hundred and twenty emails to local offices and got ignored every single "
       "time. Then we tested eighteen different workouts with our members. So come and train with us.")
PODCAST = ("Our podcast hit 50k downloads in six months. So here's the plan. Step one, we record the episode. Step two, we "
           "cut the clips. Step three, we post every clip. Last week a sponsor paid us 2.5k dollars for one episode. "
           "That is it.")
GARDEN = ("Here is how our garden shop works. We run it on Planner 3 and it costs nothing. We sold thirty-five lemon trees "
          "this spring, and fifty percent of buyers came back. We also sold 1.2k euros of seeds, and eleven raised beds, "
          "and nine hundred bulbs in one week. The other news is the shop. Follow along.")


def demo():
    many = {"graphics": {"kinetic": True, "kinetic_per_min": 30}}   # room for every candidate the rules allow
    bake = timed(BAKERY)
    kept, cands = find(bake, many)
    by = {}
    for c in cands:
        by.setdefault(c.cls, c)
    # the bakery: the hook with its duration as the sub-line, a funnel, a goal, a tracker of two with a "?" slot
    h = by["hook"].beat()
    assert h["type"] == "kinetic_number" and h["props"]["num"] == "$4.5K" and h["props"]["variant"] == "hook", h
    assert [x["text"] for x in h["props"]["sub"]] == ["in", "3.5", "weeks"] and (h["word"], h["nth"]) == ("4.5k", 1), h
    ch = by["chain"].beat()["props"]["items"]
    assert [(i["num"], i["label"]) for i in ch] == [("340", "flyers"), ("6", "cafe tastings"), ("1", "sign")], ch
    assert ch[0]["word"] == "three" and ch[1]["label_word"] == "cafe" and ch[2]["label_word"] == "sign", ch
    g = by["goal"].beat()["props"]
    assert g == {"pct": "40%", "word_pct": "forty", "count_word": "percent", "target": "20K", "word_target": "20k",
                 "word_goal": "goal"}, g
    tr = [c for c in cands if c.tracker]
    assert [c.cls for c in tr] == ["tracker", "fill", "fill", "question"] and len({c.tracker for c in tr}) == 1, [c.cls for c in tr]
    sl = [c.beat()["props"]["slots"] for c in tr]
    assert [s["label"] for s in sl[0][:2]] == ["sourdough", "seeded rye"] and sl[0][2] == {"state": "off"}, sl[0]
    assert sl[0][0]["word"] == "two" and [s["state"] for s in sl[2]] == ["filled", "filled", "off"] and sl[2][1]["word"] == "seeded", sl
    assert sl[3][2] == {"state": "question", "word": "another"}, sl[3]
    assert tr[1].beat()["word"] == "One" and tr[2].beat()["word"] == "other", "an item's beat starts on its cue"
    assert kept[0].cls == "hook" and {"chain", "goal", "fill"} <= {c.cls for c in kept}, [c.line() for c in kept]

    gym = timed(GYM)
    kept, cands = find(gym, many)
    by = {c.cls: c for c in cands}   # the last of each
    st = by["stat"].beat()["props"]["stats"]
    assert [(s["num"], s.get("label")) for s in st] == [("80", "members"), ("12", "coaches"), ("$9.2K", "monthly revenue")], st
    co = next(c for c in cands if c.cls == "counter" and "stamp" in c.props).beat()["props"]
    assert co["num"] == "120" and co["variant"] == "counter" and co["stamp"] == {"text": "ignored", "word": "ignored"}, co
    assert [x["text"] for x in co["sub"]] == ["emails"] and co["land_word"] == "emails" and co["word"] == "hundred", co
    ta = by["tally"].beat()["props"]
    assert ta["num"] == "18" and ta["variant"] == "tally" and [x["text"] for x in ta["sub"]] == ["workouts"], ta
    assert "hook" not in by and "chain" not in by, "no figure in the first sentence; 80 members, 12 coaches and $9.2K is a list"

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

    gar = timed(GARDEN)
    cands = find(gar, {"graphics": {"kinetic": True}})[1]
    nums = [n for c in cands for n in re.findall(r'"num": "([^"]+)"', json.dumps(c.beat()))]
    assert "3" not in nums and "1" not in nums, ("a name's number (Planner 3) and a lone 'one' are never a figure", nums)
    assert {c.beat()["props"]["num"] for c in cands if c.cls == "figure"} == {"35", "50%"}, [c.line() for c in cands]
    st = [[(s["num"], s["label"]) for s in c.beat()["props"]["stats"]] for c in cands if c.cls == "stat"]
    assert st == [[("35", "lemon trees"), ("50%", "buyers")], [("€1.2K", "seeds"), ("11", "raised beds"), ("900", "bulbs")]], st
    assert not [c for c in cands if c.tracker], "'the other news' is no item: no count or ordinals were said"

    # grounding: every figure is one check.py reads as said, every word on screen one the take says
    from check import said_numbers
    for ws in (bake, gym, pod, gar):
        said, pct, _ = said_numbers(" ".join(w["text"] for w in ws))
        vocab = {low(w["text"]) for w in ws}
        for c in find(ws, {"graphics": {"kinetic": True, "kinetic_per_min": 60}})[1]:
            b = json.dumps(c.beat(), ensure_ascii=False)
            for n in re.findall(r'"(?:num|pct|target)": "([^"]+)"', b):
                assert all(numbers.norm(w["value"]) in said and (w["kind"] != "percent" or numbers.norm(w["value"]) in pct)
                           for w in numbers.written(n)), (n, c.line())
            for t in re.findall(r'"(?:label|text)": "([^"]+)"', b):
                assert all(low(x) in vocab or numbers.written(x) for x in t.split()), (t, c.line())

    # ranking and density: 8 a minute over the 30 s bakery take is 4 graphics: the strongest, the hook always
    k8 = find(bake, {"graphics": {"kinetic": True}})[0]
    assert [c.cls for c in k8] == ["hook", "fill", "chain", "goal"], [c.line() for c in k8]
    assert [c.cls for c in find(bake, {"graphics": {"kinetic": True, "kinetic_per_min": 1}})[0]] == ["hook"], "the hook stays"
    assert find(bake, {"graphics": {"kinetic": True}, "cards": {"on": False}})[0] == [], "cards off: none"
    assert len(find(bake, {**many, "cards": {"per_min": 4}})[0]) == 2, "the user's cards cap wins"
    # plain footage between cards: GAP_S between any two kept, except the next beat of one tracker, which joins
    for ws in (bake, gym, pod, gar):
        ks = find(ws, {"graphics": {"kinetic": True, "kinetic_per_min": 60}})[0]
        for a, b in zip(ks, ks[1:]):
            assert b.s - a.e >= GAP_S - 1e-6 or (a.tracker and a.tracker == b.tracker and a.e == b.s), (a.line(), b.line())
        assert all(c.last < c.e and (c.e >= c.last + HOLD_MIN_S - 1e-6 or any(o.tracker and o.tracker == c.tracker and o.s == c.e for o in ks))
                   for c in ks), [c.line() for c in ks]
    # a real card (the user's photo on "flyers") takes the chain's place and its share of the budget
    kr = find(bake, {"graphics": {"kinetic": True}}, images=[{"src": "images/flyer.png", "word": "flyers", "nth": 1, "hold_s": 3}])[0]
    assert "chain" not in {c.cls for c in kr} and len(kr) == 3, [c.line() for c in kr]
    # ... and a capture beat with its fetched image is one card, not two
    cap = [{"kind": "capture", "word": "flyers", "nth": 1, "url": "https://example.com/flyer"}]
    assert len(find(bake, {"graphics": {"kinetic": True}}, visuals=cap, images=[{"src": "images/capture-1-flyers.png", "word": "flyers", "nth": 1}])[0]) == 3
    # a stat_stack may sit beside the capture of its own figures; nothing else goes under a real card
    cap = [{"kind": "capture", "word": "coaches", "nth": 1, "url": "https://example.com/stats", "hold_s": 3}]
    kg = find(gym, many, visuals=cap)[0]
    assert {"stat", "counter"} <= {c.cls for c in kg}, [c.line() for c in kg]
    assert "tally" not in {c.cls for c in find(gym, many, visuals=[{**cap[0], "word": "eighteen"}])[0]}
    demo_plan(bake)
    demo_refresh(bake)
    n = sum(len(find(timed(t), {"graphics": {"kinetic": True}})[1]) for t in (BAKERY, GYM, PODCAST, GARDEN))
    print(f"kinetic_beats ok ({n} candidates in 4 made-up takes)")


def demo_plan(bake):
    """plan.py reads the beats as written: each lands on its word, every part timed, in the kinetic lane."""
    import plan
    meta = {"video": "cut.mp4", "width": 1080, "height": 1920, "fps": 30, "duration": bake[-1]["end"] + 0.5}
    vis = beats(bake, {"graphics": {"kinetic": True, "kinetic_per_min": 30}})
    p = plan.build({"graphics": {"kinetic": True}, "captions": {"words_per_caption": 3}}, bake, meta, visuals=vis)
    kc = [c for c in p["cards"] if c.get("lane") == "kinetic"]
    assert len(kc) == len(vis) and p["kinetic"] is True, (len(kc), len(vis))
    first = {c["anim"]["type"]: c for c in reversed(kc)}
    assert first["number_chain"]["anim"]["props"]["items"][2]["label_at"] > 0, first["number_chain"]
    gb = first["goal_bar"]["anim"]["props"]
    assert gb["at_pct"] > 0 and gb["count_at"] > gb["at_pct"] and gb["at_target"] > gb["count_at"] and gb["at_goal"] > gb["at_target"], gb
    hk = kc[0]
    assert hk["anim"]["props"]["sub"][1]["at"] > hk["anim"]["props"]["at"], hk


def demo_refresh(bake):
    """refresh(): writes its beats into visuals.json beside the hand-written ones, keeps them (and a change made to
    one) while nothing changes, finds them again when the words do; off unless graphics.kinetic."""
    import tempfile
    import io
    d = Path(tempfile.mkdtemp(prefix="kinetic_beats_"))
    (d / "words.json").write_text(json.dumps(bake), encoding="utf-8")
    mine = [{"kind": "capture", "word": "sourdough", "nth": 1, "url": "https://example.com/bread", "format": "sticker"}]
    (d / "visuals.json").write_text(json.dumps(mine), encoding="utf-8")
    style = {"graphics": {"kinetic": True}}
    quiet = io.StringIO()
    assert refresh(d, {"graphics": {}}, log=quiet) == [] and json.loads((d / "visuals.json").read_text(encoding="utf-8")) == mine
    new = refresh(d, style, log=quiet)
    vis = json.loads((d / "visuals.json").read_text(encoding="utf-8"))
    assert vis[0] == mine[0] and vis[1:] == new and all(v["auto"] == AUTO for v in new) and new[0]["type"] == "kinetic_number", vis
    assert len(new) == round(KINETIC_PER_MIN * bake[-1]["end"] / 60) - 1, len(new)   # the capture counted first
    vis[1]["hold_s"] = 2.0   # a review note changed the hook
    (d / "visuals.json").write_text(json.dumps(vis), encoding="utf-8")
    assert refresh(d, style, log=quiet)[0]["hold_s"] == 2.0, "kept while the cut, the cards and the rate are the same"
    assert refresh(d, {"graphics": {"kinetic": True, "kinetic_auto": False}}, log=quiet) == []
    (d / "words.json").write_text(json.dumps(bake[:-12]), encoding="utf-8")   # a re-cut
    again = refresh(d, style, log=quiet)
    assert again[0]["hold_s"] != 2.0 and len(json.loads((d / "visuals.json").read_text(encoding="utf-8"))) == 1 + len(again)
    assert refresh(d, style, force=True, log=quiet) == again


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
