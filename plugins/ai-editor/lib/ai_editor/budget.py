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
pick(items, n): the n strongest, in their own order. The hook (an item with "hook": true, else the first one starting
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


def allowance(style, duration_s):
    """The most graphics in a video this long (at least one when the rate is above 0), or None with kinetic off."""
    pm = per_min(style)
    if pm is None:
        return None
    if pm <= 0 or duration_s <= 0:
        return 0
    return max(1, math.floor(duration_s / 60 * pm + 0.5))


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


def pick(items, n, start=lambda i: i["start"], end=lambda i: i.get("end", i["start"])):
    """The n items to keep (None: all), in their own order: the hook, then one at a time the strongest, a beat that
    would leave under MIN_PLAIN_S beside one already kept counting TOUCH_PENALTY less (ties: the earlier)."""
    items = list(items)
    if n is None or len(items) <= n:
        return items
    if n <= 0:
        return []
    order = sorted(range(len(items)), key=lambda i: start(items[i]))
    hook = next((i for i in order if is_hook(items[i])), None)
    if hook is None:
        hook = next((i for i in order if start(items[i]) < HOOK_S), None)
    keep = [] if hook is None else [hook]
    touches = lambda i: any(start(items[i]) - end(items[k]) < MIN_PLAIN_S and start(items[k]) - end(items[i]) < MIN_PLAIN_S
                            for k in keep)
    while len(keep) < n:
        rest = [i for i in order if i not in keep]
        keep.append(max(rest, key=lambda i: (strength(items[i]) - TOUCH_PENALTY * touches(i), -start(items[i]))))
    return [items[i] for i in sorted(keep)]


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
    print("budget demo ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        demo()
    else:
        print(__doc__)
        sys.exit(2)
