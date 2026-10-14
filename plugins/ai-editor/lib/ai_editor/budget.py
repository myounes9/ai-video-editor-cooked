#!/usr/bin/env python3
"""How many graphics a video gets, once kinetic titles are on: one count for every card a viewer sees (a kinetic
title, a capture, a post, a logo), shared by the beat finder (which beats get a graphic) and plan.py (the cards it
keeps), so the two never disagree. Stdlib only, deterministic.

    python3 budget.py demo      self-check

Settings, style.json (or the user's taste.json) "graphics":
  kinetic           true: the kinetic family may be planned (references/kinetic.md); without it there is no budget
                    here and plan.py keeps its own rules (cards.per_min, the creator's rate).
  kinetic_per_min   graphics a minute IN TOTAL, kinetic and real-source together (default 8). It wins over the style
                    page's cards.per_min; cards.on false still means none.

allowance(style, duration_s): the most graphics for that length, or None when kinetic titles are off.
pick(items, n): the n strongest graphics, in their own order (a step tracker's beats, one props "id", are one). The hook (an item with "hook": true, else the first one starting
in the opening HOOK_S) is always kept. Strength is an item's "strength" (0-1, the beat finder's score), else
REAL_STRENGTH for a real source (a capture, post, logo) and KINETIC_STRENGTH for a kinetic beat. One that would
leave under MIN_PLAIN_S of plain footage beside one already kept counts TOUCH_PENALTY less, so the picks spread out
and the speaker's own zooms happen between them; a much stronger beat still wins.
"""
import math
import sys

DEFAULT_PER_MIN = 8.0
HOOK_S = 3.0           # a graphic starting this early is the hook
MIN_PLAIN_S = 1.0      # plain footage the picker leaves between two graphics, when the budget allows
TOUCH_PENALTY = 0.2    # strength a beat loses for leaving less than that beside one already kept
REAL_STRENGTH = 0.75   # a real source with no score: what is said, shown as it is (PRINCIPLES.md "Looking real")
KINETIC_STRENGTH = 0.5
KINETIC_TYPES = ("kinetic_number", "number_chain", "goal_bar", "step_build", "stat_stack", "kinetic_title", "cta_follow")


def per_min(style):
    """Graphics a minute for this style, or None when kinetic titles are off (no shared budget)."""
    g = (style or {}).get("graphics") or {}
    if not g.get("kinetic"):
        return None
    if ((style or {}).get("cards") or {}).get("on") is False:
        return 0.0
    v = g.get("kinetic_per_min")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else DEFAULT_PER_MIN


def count(pm, duration_s):
    """The most graphics at pm a minute in a video this long: rounded half up, at least one when the rate is above 0."""
    if pm <= 0 or duration_s <= 0:
        return 0
    return max(1, math.floor(duration_s / 60 * pm + 0.5))


def allowance(style, duration_s):
    """The most graphics in a video this long (count()), or None with kinetic off."""
    pm = per_min(style)
    return None if pm is None else count(pm, duration_s)


def remaining(style, duration_s, taken):
    """What is left for the beat finder once `taken` graphics are spoken for (the user's own captures, posts, logos).
    None with kinetic off."""
    n = allowance(style, duration_s)
    return None if n is None else max(0, n - taken)


def kind(item):
    """An item's type: a plan card's or a visuals.json beat's anim type, else "src" for a picture."""
    a = item.get("anim") or {}
    return a.get("type") or item.get("type") or ("src" if item.get("src") or item.get("kind") in ("capture", "post", "logo") else None)


def strength(item):
    s = item.get("strength", item.get("_strength"))
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    return KINETIC_STRENGTH if kind(item) in KINETIC_TYPES else REAL_STRENGTH


def is_hook(item):
    return bool(item.get("hook", item.get("_hook")))


def group(item):
    """The beats of one step_build tracker (its props "id") are one graphic coming back: they count once, are kept or
    left out together, and are never spaced apart."""
    a = item.get("anim") or item
    return (a.get("props") or {}).get("id") if a.get("type") == "step_build" else None


def pick(items, n, start=lambda i: i["start"], end=lambda i: i.get("end", i["start"])):
    """The items to keep for n graphics (None: all), in their own order: the hook, then one graphic at a time the
    strongest (a tracker's beats are one graphic, its strength their best), one that would leave under MIN_PLAIN_S
    beside one already kept counting TOUCH_PENALTY less (ties: the earlier)."""
    items = list(items)
    order = sorted(range(len(items)), key=lambda i: start(items[i]))
    units = {}
    for i in order:
        units.setdefault(group(items[i]) or ("one", i), []).append(i)
    units = list(units.values())
    if n is None or len(units) <= n:
        return items
    if n <= 0:
        return []
    hook = next((u for u in units if any(is_hook(items[i]) for i in u)), None)
    if hook is None:
        hook = next((u for u in sorted(units, key=lambda u: start(items[u[0]])) if start(items[u[0]]) < HOOK_S), None)
    keep = [] if hook is None else [hook]
    touches = lambda u: any(start(items[i]) - end(items[k]) < MIN_PLAIN_S and start(items[k]) - end(items[i]) < MIN_PLAIN_S  # noqa: E731
                            for i in u for v in keep for k in v)
    while len(keep) < n:
        rest = [u for u in units if u not in keep]
        keep.append(max(rest, key=lambda u: (max(strength(items[i]) for i in u) - TOUCH_PENALTY * touches(u), -start(items[u[0]]))))
    return [items[i] for i in sorted(i for u in keep for i in u)]


def demo():
    st = {"graphics": {"kinetic": True}}
    assert per_min({}) is None and allowance({}, 60) is None and remaining({}, 60, 2) is None
    assert per_min(st) == DEFAULT_PER_MIN and allowance(st, 60) == 8 and allowance(st, 55) == 7 and allowance(st, 4) == 1
    assert allowance({"graphics": {"kinetic": True, "kinetic_per_min": 4}}, 90) == 6
    assert allowance({**st, "cards": {"on": False}}, 60) == 0 and allowance({**st, "cards": {"per_min": 2}}, 60) == 8
    assert remaining(st, 60, 3) == 5 and remaining(st, 60, 12) == 0
    c = lambda s, e, k="kinetic_number", **x: {"start": s, "end": e, "anim": {"type": k}, **x}  # noqa: E731
    # a picture with no score outranks a kinetic beat with none; a score wins over both
    assert strength({"src": "images/a.png"}) == REAL_STRENGTH and strength(c(0, 1)) == KINETIC_STRENGTH
    assert strength(c(0, 1, strength=0.9)) == 0.9 and strength({"kind": "capture", "word": "x"}) == REAL_STRENGTH
    cards = [c(0.4, 3.0), c(3.2, 6.0, strength=0.9), c(6.2, 9.0, strength=0.8), c(12.0, 15.0, strength=0.3),
             {"src": "images/menu.png", "start": 20.0, "end": 23.0}, c(23.3, 26.0, strength=0.95)]
    # 3 kept: the hook (the opening one, weak as it is), then the strongest, one that leaves under a second of
    # footage beside a kept one counting less: 3.2 (0.9) touches the hook, so 6.2 (0.8) goes first
    got = pick(cards, 3)
    assert got == [cards[0], cards[2], cards[5]], [(x["start"]) for x in got]
    # a much stronger beat still wins over a spaced weak one
    assert pick(cards, 4) == [cards[0], cards[1], cards[2], cards[5]]
    # a hook said later and marked by the beat finder wins over the opening one
    hk = [c(0.4, 3.0), c(10.0, 12.0, hook=True, strength=0.1), c(14.0, 16.0, strength=0.9)]
    assert pick(hk, 1) == [hk[1]] and pick(hk, 2) == hk[1:]
    # all fit: all kept
    assert pick(cards, 5) == [cards[0], cards[1], cards[2], cards[4], cards[5]] and pick(cards, 9) == cards and pick(cards, 0) == []
    assert pick(cards, None) == cards
    # a tracker's next beat joins the one before: no spacing penalty between them, so it is kept with it
    tk = lambda s, e, **x: c(s, e, "step_build", **x) | {"anim": {"type": "step_build", "props": {"id": "t"}}}  # noqa: E731
    tr = [c(0.4, 2.0), tk(5.0, 7.0, strength=0.3), tk(7.0, 9.0, strength=0.3), c(9.2, 11.0, strength=0.25)]
    assert pick(tr, 3) == tr and count(8, 30) == 4 and count(8, 4) == 1 and count(0, 60) == 0
    # ... and a tracker that comes back later is still one graphic: kept or left out whole
    tb = [c(0.4, 2.0), tk(5.0, 7.0, strength=0.7), c(10.0, 12.0, strength=0.6), tk(20.0, 22.0, strength=0.7), c(25.0, 27.0, strength=0.4)]
    assert pick(tb, 3) == tb[:4] and pick(tb, 2) == [tb[0], tb[1], tb[3]], [x["start"] for x in pick(tb, 2)]
    print("budget demo ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        demo()
    else:
        print(__doc__)
        sys.exit(2)
