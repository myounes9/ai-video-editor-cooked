#!/usr/bin/env python3
"""Bespoke motion clips for a style-edit: one HyperFrames + GSAP composition per beat that needs motion.

    python3 motion.py pick edits/NAME [--max 8]   visuals.json -> edits/NAME/motion/<id>/ (template + brief.md)
    python3 motion.py check edits/NAME/motion/ID  every gate, the render, the sheets -> ID/gates.json
    python3 motion.py place edits/NAME            passed clips -> visuals.json video_card beats; failed: the template
    python3 motion.py status edits/NAME           one line per clip
    python3 motion.py strips VIDEO --at 3.2,9.1 --out strips.png [--safe]   10 fps strips round each time
    python3 motion.py demo                        self-check (offline)

pick: the beats route.py's picks sent to a moving template (a count, a list of notes, a flow, a before and
after, a run, a mechanism: MOTION_TYPES) become clips, and so does a beat routed elsewhere whose sentence is a
list, a number, steps or a before and after (promote_type). Each gets the template filled with its size, duration,
id, look and the said words' times in clip seconds (clip t=0 is the card's first frame, CARD_LEAD_S before
its word), and a brief for one clip-builder agent. Beats with under MIN_S of room keep their template.
check: check_clip.py, `hyperframes lint`, `check --at-transitions`, render, check_motion.py, measure_ink.py,
check_composition.py (advisory), a 1 fps contact sheet and a 10 fps strip of the first 1.2 s.
place: a clip whose last check passed replaces its beat with a video_card of the render, `start_s` set from
clip_motion.py so the motion finishes 0.25 s before the card leaves; the template beat is kept under "fallback"
and comes back for a clip that did not pass. Never edits anything but visuals.json and images/motion-*.mp4.
Beside kinetic titles (style.json graphics.kinetic, the fork): the number beats are the titles', so pick takes only a
list, a flow, a before and after or a mechanism on a line no number beat says, ending before the next such line, never
up with one, and only the clips the graphics budget keeps, each ranked as its template as plan.py ranks it: the
user's real cards first, then the number beats, then a moving template's clip in what they leave (split_beats;
style-edit references/kinetic.md "Motion clips"); place keeps a beat's template when the titles have
since taken its line. Kinetic titles off: upstream's picks, beats_for unchanged.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
PLUGIN = SKILL.parents[1]
sys.path.insert(0, str(HERE))

HF_VERSION = "0.8.155"     # setup.py installs exactly this (MOTION_PKGS); 0.7.x had other flags
GSAP_VERSION = "3.14.2"
MOTION_TYPES = ("likes", "progress", "curve", "notes", "terminal", "chat", "toasts", "side_by_side", "flow", "logo_cluster")
# style.json "motion": {"engine": "clips"|"templates", "amount": 0-1, "kinds": {kind: bool}, "look": "default"}.
# A kind names what the sentence is doing; each maps to the template formats a clip replaces.
KINDS = {"counter": ("likes",), "list": ("notes",), "flow": ("flow",), "before_after": ("side_by_side",),
         "ui_demo": ("progress", "terminal", "chat", "toasts"), "curve": ("curve",), "logo": ("logo_cluster",)}
CARD_LEAD_S = 0.1          # plan.py: a card lands this long before its word
MIN_S = 1.0                # less room than this and the beat keeps its template
HOLD_S = 2.5               # a beat with no hold_s
SIZE = {"9:16": (1200, 630), "16:9": (1280, 720)}   # card canvas: shown at about 800 px wide, so 1.5x sharp
FINISH_S = 0.25            # motion ends this long before the card leaves (visual-system.md "Watch the animation FINISH")
ROUNDS = 3                 # check rounds a clip-builder gets before the beat falls back to its template

# The default look (references/looks.md): the house look, neutral. A style overrides ground, ink, accent, font.
DEFAULT_LOOK = {"name": "default", "ground": "#FFFFFF", "paper": "#FDF8EC", "ink": "#171614", "muted": "#6B6862",
                "accent": None, "stop": "#FF3040", "ok": "#3DDC84", "font": "TikTok Sans", "radius": 28,
                "stroke": {"container": 6, "connector": 3, "texture": 1.2}}
PRESETS = {  # remotion/src/look.tsx, the parts a clip uses; "paper" is the 50/50 style's ground, "board" Motion design's
    "paper": {"ground": "#FDF8EC", "ink": "#171614"},
    "board": {"ground": "#0B0B0D", "ink": "#F4F6FA"},   # the Motion design style's canvas: near-black, silver-white ink
    "editorial": {"ground": "#F2EEE6", "ink": "#141414", "accent": "#E5482C"},
    "editorial-dark": {"ground": "#151413", "ink": "#F2EEE6", "accent": "#FF5A36"},
    "mono": {"ground": "#FFFFFF", "ink": "#0A0A0A", "font": "IBM Plex Sans"},
    "poster-red": {"ground": "#E2321B", "ink": "#111111", "accent": "#F7D23B"},
    "poster-green": {"ground": "#1E4A2C", "ink": "#F4EFE2", "accent": "#F5D63D"},
    "poster-blue": {"ground": "#1F3FD1", "ink": "#F4EFE2", "accent": "#FF7A59"},
}


def home():
    return Path(os.environ.get("AI_EDITOR_HOME", "").strip() or Path.home() / ".ai-video-editor")


def hf_bin():
    """The pinned HyperFrames CLI setup installed, or None."""
    b = home() / "motion" / "node_modules" / ".bin" / ("hyperframes.cmd" if os.name == "nt" else "hyperframes")
    return b if b.exists() else None


def clean(t):
    return re.sub(r"[^\w'’-]+", "", t).lower()


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:24] or "beat"


def word_time(words, word, nth=1, after=-1.0):
    """Start of the nth time `word` is said (the next one after `after` without nth), like plan.py _place."""
    hits = [w for w in words if clean(w["text"]) == clean(word)]
    hits = hits[nth - 1:nth] if nth else [w for w in hits if w["start"] > after]
    return hits[0]["start"] if hits else None


def sentences(words):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None or w["text"].rstrip().endswith((".", "?", "!")) or nxt["start"] - w["end"] > 0.8:
            out.append({"text": " ".join(x["text"] for x in cur).strip(), "start": cur[0]["start"], "end": cur[-1]["end"]})
            cur = []
    return out


def look_for(style, profile=None):
    """The clip look: DEFAULT_LOOK, then the style's look preset, then the brand kit's or creator's ink, accent, font."""
    look = json.loads(json.dumps(DEFAULT_LOOK))
    sl = (style or {}).get("look") or {}
    pick_ = ((style or {}).get("motion") or {}).get("look") if isinstance((style or {}).get("motion"), dict) else None
    if pick_ in PRESETS:   # the style page's Motion look wins over the style's card look
        look.update(PRESETS[pick_], name=pick_)
    elif sl.get("preset") in PRESETS:
        look.update(PRESETS[sl["preset"]], name=sl["preset"])
    brand = ((profile or {}).get("brand") or {})
    for k, src in (("ink", "ink"), ("accent", "accent"), ("font", "font"), ("ground", "ground")):
        v = sl.get(src) or brand.get(src)
        if v:
            look[k] = v
            look["name"] = look["name"] if look["name"] != "default" else "default + style"
    return look


def motion_cfg(style):
    """style.json "motion" with defaults: clips on, every kind, look "default". amount: the share of moving beats
    built as clips (0 none, 0.5 some, 1 lots); with none set, a measured style's animation share
    (creator-teardown graphics.kinds "animation", in percent) decides, else 1."""
    m = (style or {}).get("motion") or {}
    m = m if isinstance(m, dict) else {}
    kinds = {k: bool((m.get("kinds") or {}).get(k, True)) for k in KINDS}
    share = (((style or {}).get("graphics") or {}).get("kinds") or {}).get("animation")
    amount = m.get("amount", round(min(1.0, share / 100), 2) if isinstance(share, (int, float)) else 1.0)
    return {"engine": m.get("engine", "clips"), "amount": float(amount), "kinds": kinds, "look": m.get("look", "default")}


def allowed_types(cfg):
    return tuple(t for k, ts in KINDS.items() if cfg["kinds"][k] for t in ts) if cfg["engine"] == "clips" else ()


def promote_type(line):
    """The moving template a sentence asks for, whatever visual-prep routed there: a before and after, a number,
    steps (first... then...) or a natural list (four or more items said in a row: "a, b, c and d"). None: no motion."""
    sys.path.insert(0, str(SKILL.parent / "style-edit" / "scripts"))
    import route
    if route.VERSUS.search(line):
        return "side_by_side"
    if route.NUM.search(line):
        return "likes"
    if len(route.STEPS.findall(line)) >= 2:
        return "flow"
    if line.count(",") >= 3 or (line.count(",") >= 2 and re.search(r",? (?:and|or) ", line)):
        return "notes"
    return None


def beats_for(visuals, words, aspect="9:16", max_n=8, images=(), types=MOTION_TYPES, amount=1.0, face=None):
    """The visuals.json beats that become clips: [{id, i, word, nth, start, dur, words, line, ...}].
    types: the template formats clips may replace (style.json motion kinds); amount: the share of them built.
    A beat routed to anything else (a card, a capture, a sticker) whose sentence is a list, a number, steps or a
    before and after becomes a clip too (promote_type), one per sentence, when no animation is there already."""
    times, after = [], -1.0
    for v in list(visuals) + list(images):
        t = word_time(words, v["word"], v.get("nth"), after) if v.get("word") else None
        if t is not None:
            times.append(t)
    times.sort()
    sents = sentences(words)
    sent_of = lambda t: next((k for k, s in enumerate(sents) if s["start"] <= t <= s["end"] + 0.05), None)   # noqa: E731
    animated = {sent_of(t) for v in visuals if v.get("kind") == "anim" and v.get("word")
                for t in [word_time(words, v["word"], v.get("nth", 1))] if t is not None}
    out = []
    for i, v in enumerate(visuals):
        if not v.get("word"):
            continue
        t = word_time(words, v["word"], v.get("nth", 1))
        if t is None:
            continue
        if v.get("kind") != "anim":   # routed elsewhere: a clip only when the sentence itself moves
            si = sent_of(t)
            pt = promote_type(sents[si]["text"]) if si is not None and si not in animated else None
            if pt not in types:
                continue
            animated.add(si)
            v = {**v, "type": pt, "props": {}, "promoted": v.get("kind")}
        elif v.get("type") not in types:
            continue
        start = round(max(0.0, t - CARD_LEAD_S), 3)
        nxt = next((x - CARD_LEAD_S for x in times if x > t + 1e-6), words[-1]["end"] + 0.5)
        dur = round(min(nxt, start + max(v.get("hold_s") or HOLD_S, MIN_S)) - start, 2)
        if dur < MIN_S:
            continue
        si = next((k for k, s in enumerate(sents) if s["start"] <= t <= s["end"] + 0.05), None)
        said = [{"w": w["text"], "t": round(w["start"] - start, 2)} for w in words if start <= w["start"] < start + dur]
        out.append({"id": f"{len(out) + 1:02d}-{slug(v['word'])}", "i": i, "word": v["word"], "nth": v.get("nth", 1),
                    "type": v["type"], "props": v.get("props") or {}, "start": start, "dur": dur, "clock": "cut",
                    "size": card_size(face, start, start + dur, aspect), "words": said,
                    "line": sents[si]["text"] if si is not None else "", **({"promoted": v["promoted"]} if v.get("promoted") else {}),
                    "before": sents[si - 1]["text"] if si else "", "after": sents[si + 1]["text"] if si is not None and si + 1 < len(sents) else ""})
    n = min(max_n, int(len(out) * max(0.0, min(1.0, amount)) + 0.5))   # half up: 1 beat at "some" is 1 clip, not 0
    if len(out) > n:   # keep the longest windows: a bespoke clip pays off most where it holds longest
        keep = {b["id"] for b in sorted(out, key=lambda b: -b["dur"])[:n]}
        out = [b for b in out if b["id"] in keep]
    return out


# beats_for exactly as upstream ai-editor 2.7.8 ships it: with kinetic titles off pick calls it as upstream does, and
# split_beats only wraps it. The demo checks this hash; when an upstream merge changes beats_for, check split_beats
# still fits round it, then put the new hash here.
BEATS_FOR_SHA = "e8bf4d2f053be04fc716c6de1858937e7e17b00bd41924d9bc4e10420b212e46"


def kinetic_split(style, words, visuals, images=(), duration=None):
    """What kinetic titles leave to the clips (style-edit kinetic_beats.split), or None when they are off. duration:
    the cut's length (kinetic_beats.video_duration), as plan.py counts the budget over it."""
    if not (((style or {}).get("graphics") or {}).get("kinetic")):
        return None
    sys.path[:0] = [str(SKILL.parent / "style-edit" / "scripts"), str(PLUGIN / "lib")]
    import kinetic_beats
    return kinetic_beats.split(words, style, visuals, images, duration)


def split_types(types):
    """The template formats a clip may replace beside kinetic titles: kinetic_beats.MOTION_KINDS' (a list, a flow, a
    before and after, a mechanism), never a counter's ("likes") or a logo cluster's."""
    sys.path.insert(0, str(SKILL.parent / "style-edit" / "scripts"))
    import kinetic_beats
    return tuple(t for t in types if any(t in KINDS[k] for k in kinetic_beats.MOTION_KINDS))


def split_veto(b, split, sents, types):
    """Why beat b (beats.json) is no clip beside kinetic titles, or None: a type the titles own, its line says a number
    beat, its window runs over a line one says (a count left out over the budget too: the line is still the titles'),
    or it is up with a kept one."""
    if b["type"] not in types:
        return "the numbers are the kinetic titles'"
    si = next((k for k, s in enumerate(sents) if s["start"] <= b["start"] + CARD_LEAD_S <= s["end"] + 0.05), None)
    if si is not None and any(sents[si]["start"] <= t <= sents[si]["end"] + 0.05 for t in split["said"]):
        return "its line says a number beat (the kinetic titles')"
    end = b["start"] + b["dur"]
    t = next((t for t in split["said"] if b["start"] < t < end), None)
    if t is not None:
        return f"it runs over a number said at {t:.2f} s (the kinetic titles')"
    k = next((x for x in split["kept"] if b["start"] < x[1] - 0.01 and x[0] < end - 0.01), None)
    if k:
        return f"up with the kinetic title at {k[0]:.2f}-{k[1]:.2f} s"
    return None


def word_ref(words, i):
    """{"word", "nth"} for words[i], as word_time finds it again."""
    return {"word": words[i]["text"], "nth": sum(clean(w["text"]) == clean(words[i]["text"]) for w in words[:i + 1])}


def fit_window(b, end, words, face, aspect):
    """Beat b ending at `end` instead: its WORDS and canvas for the shorter window."""
    dur = round(end - b["start"], 2)
    return {**b, "dur": dur, "size": card_size(face, b["start"], b["start"] + dur, aspect),
            "words": [{"w": w["text"], "t": round(w["start"] - b["start"], 2)} for w in words
                      if b["start"] <= w["start"] < b["start"] + dur]}


def split_beats(visuals, words, aspect="9:16", max_n=8, images=(), types=MOTION_TYPES, amount=1.0, face=None,
                split=None, style=None):
    """beats_for beside kinetic titles (split: kinetic_split). The number beats are the titles' (style-edit
    references/kinetic.md "Motion clips"): a beat whose line a number beat says a part of (kept or not) is no clip, and
    reaches beats_for as a time only (images), as does the first word of every such line and each kept beat's word, so
    a clip before one ends before it: its WORDS never hold a figure the titles own; types lose the counter and the
    logo cluster (split_types); a beat routed elsewhere on a line that only says a figure the titles would not draw
    ("twice") is a clip of the line's other kind; none is up with a kept beat (split_veto); one that would end under
    kinetic_beats.GAP_S before a kept beat ends that much before it when it still holds MIN_S, as plan.py space_kinetic
    would cut it; and only the clips the graphics budget keeps: budget.settle over the number beats, every card that is
    no candidate here (kinetic_beats.real_cards) and the candidates, a clip ranked as its template, as plan.py
    budget_cards keeps them: the user's real cards first, then the number beats (the hook always), then a moving
    template's clip in the room they leave. Returns (beats, {"room", "cands", "lines", "others"})."""
    sys.path[:0] = [str(SKILL.parent / "style-edit" / "scripts"), str(PLUGIN / "lib")]
    import kinetic_beats
    import route
    from ai_editor import budget
    types = split_types(types)
    sents = sentences(words)
    sent_of = lambda t: next((k for k, s in enumerate(sents) if s["start"] <= t <= s["end"] + 0.05), None)   # noqa: E731
    covered = {k for k, s in enumerate(sents) if any(s["start"] <= t <= s["end"] + 0.05 for t in split["said"])}
    times = list(images) + [{"word": w, "nth": n} for _, _, w, n in split["kept"] if w]
    firsts = {round(sents[k]["start"], 3) for k in covered}
    times += [word_ref(words, i) for i, w in enumerate(words) if round(w["start"], 3) in firsts]   # a number line's first word
    animated = {sent_of(t) for v in visuals if v.get("kind") == "anim" and v.get("word")
                for t in [word_time(words, v["word"], v.get("nth", 1))] if t is not None}
    view = []
    for v in visuals:
        t = word_time(words, v["word"], v.get("nth", 1)) if v.get("word") else None
        si = sent_of(t) if t is not None else None
        if si in covered:   # the titles' line: a time only
            times.append({"word": v["word"], "nth": v.get("nth")})
            v = {**v, "word": None}
        elif si is not None and v.get("kind") != "anim" and si not in animated and promote_type(sents[si]["text"]) == "likes":
            pt = promote_type(route.NUM.sub(" ", sents[si]["text"]))
            if pt in types:
                v = {**v, "kind": "anim", "type": pt, "props": {}, "promoted": v.get("kind")}
                animated.add(si)
        view.append(v)
    out = []
    for b in beats_for(view, words, aspect, max_n, times, types, amount, face):
        k0 = min((x[0] for x in split["kept"] if x[0] > b["start"] + 1e-6), default=None)
        if k0 is not None and b["start"] + b["dur"] > k0 - kinetic_beats.GAP_S and k0 - kinetic_beats.GAP_S - b["start"] >= MIN_S:
            b = fit_window(b, k0 - kinetic_beats.GAP_S, words, face, aspect)   # plain footage before the title
        if not split_veto(b, split, sents, types):
            out.append(b)
    cand = {b["i"] for b in out}
    take = kinetic_beats.Take(words)
    others = kinetic_beats.real_cards(take, [v for k, v in enumerate(visuals) if k not in cand], images, style or {},
                                      split.get("duration") or (take.w[-1]["end"] if take.w else 0))
    items = [dict(c) for c in split.get("cards", [])] + [{"start": s, "end": e, "type": kind} for s, e, kind, _ in others]
    items += [{"start": b["start"], "end": b["start"] + b["dur"], "type": "video_card", "_clip": b["id"],
               "_template": budget.kind(visuals[b["i"]]),   # ranked as the beat it replaces: a moving template comes after the numbers
               **({"strength": visuals[b["i"]]["strength"]} if visuals[b["i"]].get("strength") is not None else {})} for b in out]
    keep = {x.get("_clip") for x in budget.settle(items, split["allowance"] or 0)[0]}
    n = len(out)
    out = [b for b in out if b["id"] in keep]
    for b in out:
        b["beside_kinetic"] = True   # the brief: this edit's number beats are its kinetic titles
    return out, {"room": len(out), "cands": n, "lines": len(covered), "others": len(others)}


def card_size(face, start, end, aspect="9:16"):
    """The card canvas for a clip up from start to end: 1200 wide, as tall as the band above the head lets a
    800 px card be (plan.py: the band runs from the safe top, 13.1%, to 2% over the head, and a card may tuck its
    bottom fifth behind the hair). No head found or a wide frame: SIZE."""
    if aspect != "9:16" or not face or not face.get("heads"):
        return list(SIZE.get(aspect, SIZE["9:16"]))
    tops = [h["box"][1] for h in face["heads"] if h.get("box") and start - 0.5 <= h["t"] <= end]
    if not tops:
        return list(SIZE["9:16"])
    band = max(8.0, (min(tops) - 13.1 - 2.0) / 0.8) / 100 * 1920 * 0.92   # px the picture gets (FILL)
    ar = max(1.6, min(3.0, 0.74 * 1080 * 0.96 / band))
    return [1200, int(round(1200 / ar / 2)) * 2]


def panel_size(style):
    """The 50/50 (split layout) panel's art box as a clip canvas, or None for an overlay style. plan.py
    split_art_box: x 13-87%, y 13.1% to 2% above the seam. The clip fills it edge to edge on the panel's ground."""
    lay = (style or {}).get("layout") or {}
    if lay.get("mode") != "split":
        return None
    seam = float(lay.get("seam", 50))
    w_px, h_px = 0.74 * 1080, (seam - 2 - 13.1) / 100 * 1920
    return [1200, int(round(1200 * h_px / w_px / 2)) * 2]


def board_size(style):
    """A board-layout style (Motion design): the clip is an overlay beside the speaker, in plan.py BOARD_OVERLAY_BOX
    (42% x 60% of a 16:9 frame, 806 x 648 px), so its canvas is that shape. None for any other layout."""
    if ((style or {}).get("layout") or {}).get("mode") != "board":
        return None
    return [1200, int(round(1200 * 648 / 806 / 2)) * 2]


def fill_template(beat, look, gsap=None):
    w, h = beat["size"]
    html = (SKILL / "template" / "index.html").read_text(encoding="utf-8")
    for k, v in {"__ID__": beat["id"], "__W__": w, "__H__": h, "__CX__": w // 2, "__CY__": h // 2,
                 "__DUR__": f"{beat['dur']:.2f}", "__GROUND__": look["ground"], "__INK__": look["ink"],
                 "__WORDS__": json.dumps(beat["words"])}.items():
        html = html.replace(k, str(v))
    return html


BRIEF = """# Clip {id}

Read `{card}` first (every gate and approved value), then build this one clip. Do not read the check
scripts' source. First render within about 10 minutes, then iterate on `check` output.

- Folder (yours alone): `{dir}`. Edit `index.html` only, plus files you add under `assets/`.
- Canvas {w}x{h}, {dur} s, 30 fps. It plays as a card about {cw} px wide in the band above the speaker's head,
  {placement}
- The look: {look}
- The line: "{line}"
  Before it: "{before}"  After it: "{after}"
- When each word lands (clip seconds, already in `WORDS` in index.html): {words}
- What this beat was going to be (the template's content, use its real words and pictures): `{type}` {props}
- The edit's real pictures you may use (copy into `assets/`): {images}

{start}Build: `{env}python3 "{motion}" check "{dir}"` runs every gate and the render, writes `gates.json`, `renders/clip.mp4`,
`renders/sheet.png` (1 fps) and `renders/strip.png` (10 fps, first 1.2 s). Look at both sheets after every
render. At most {rounds} checks; then stop and report.
"""


def effective(edit):
    """style.json as plan.py uses it (the style page's settings and the user's corrections over it), else the raw file."""
    sp = Path(edit) / "style.json"
    try:
        sys.path[:0] = [str(SKILL.parent / "style-edit" / "scripts"), str(PLUGIN / "lib")]
        import contextlib
        import io
        import plan
        from ai_editor import profile as prof_mod
        with contextlib.redirect_stderr(io.StringIO()):
            return plan.effective_style(sp, prof_mod.load(), str(edit), count=False)
    except Exception:   # noqa: BLE001  outside the plugin's venv: the raw style.json
        return json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}


def pick(edit, max_n=8):
    edit = Path(edit)
    visuals = json.loads((edit / "visuals.json").read_text(encoding="utf-8"))
    words = [w for w in json.loads((edit / "captions.json").read_text(encoding="utf-8")) if w.get("type", "word") == "word"]
    style = effective(edit)
    images = json.loads((edit / "images.json").read_text(encoding="utf-8")) if (edit / "images.json").exists() else []
    try:
        sys.path.insert(0, str(PLUGIN / "lib"))
        from ai_editor import profile as prof_mod
        profile = prof_mod.load() if hasattr(prof_mod, "load") else {}
    except Exception:   # noqa: BLE001  a missing or broken profile means the default look
        profile = {}
    look = look_for(style, profile)
    aspect = style.get("aspect", "9:16")
    cfg = motion_cfg(style)
    face = json.loads((edit / "face.json").read_text(encoding="utf-8")) if (edit / "face.json").exists() else None
    types = allowed_types(cfg)
    if board_size(style):   # Motion design: logos and flows land as tiles on the canvas, never as clips
        types = tuple(t for t in types if t not in ("logo_cluster", "flow"))
    view = [v.get("fallback") or v for v in visuals]
    split = kinetic_split(style, words, view, images, cut_duration(edit, style))
    if split is None:   # upstream's picks, unchanged
        beats = beats_for(view, words, aspect, max_n, images, types, cfg["amount"], face)
    else:
        beats, how = split_beats(view, words, aspect, max_n, images, types, cfg["amount"], face, split, style)
        print(f"kinetic titles on: the numbers are theirs ({how['lines']} line(s) a number beat says, no clip there or "
              f"over it, never a counter); clips only for a list, a flow, a before and after or a mechanism, in the one "
              f"graphics budget: {split['allowance']} in all, {split['units']} number graphic(s) and {how['others']} other "
              f"card(s) of the edit; {how['room']} of {how['cands']} candidate clip(s) kept, ranked as their templates "
              "(plan.py keeps the same)" + ("" if how["room"] or not how["cands"] else ": the budget is full, no clip")
              + " (style-edit references/kinetic.md \"Motion clips\")")
    pj = edit / "plan.json"
    if pj.exists() and pj.stat().st_mtime >= (edit / "visuals.json").stat().st_mtime:   # the plan dropped some beats
        kept = {(c.get("trigger_word") or "").lower() for c in json.loads(pj.read_text(encoding="utf-8")).get("cards", [])}
        gone = [b for b in beats if b["word"].lower() not in kept]
        if gone:
            print("not in the plan, no clip: " + ", ".join(f"'{b['word']}'" for b in gone))
        beats = [b for b in beats if b["word"].lower() in kept]
    panel = panel_size(style)
    if panel:   # the 50/50 panel: every clip is the panel's own shape, on the panel's ground
        look = {**look, "ground": (style.get("layout") or {}).get("ground") or look["ground"]}
        for b in beats:
            b.update(size=panel, panel=True)
    if board_size(style):   # Motion design: an overlay on one side of the wide frame, the speaker moved to the other
        for b in beats:
            b.update(size=board_size(style), board=True)
    if cfg["engine"] != "clips":
        print("style.json motion.engine is \"templates\": no clips, the template formats stay")
    gsap = home() / "motion" / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    root = edit / "motion"
    root.mkdir(exist_ok=True)
    pics = sorted(p.name for p in (edit / "images").glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp")) \
        if (edit / "images").is_dir() else []
    for b in beats:
        d = root / b["id"]
        (d / "assets").mkdir(parents=True, exist_ok=True)
        if not (d / "index.html").exists():   # never clobber a clip being built
            (d / "index.html").write_text(fill_template(b, look), encoding="utf-8")
            sp = starting_point(b["type"])
            if sp and (library_dir() / sp["id"] / "index.html").exists():
                shutil.copy(library_dir() / sp["id"] / "index.html", d / "start.html")
                for a in (library_dir() / sp["id"] / "assets").glob("*"):
                    if not (d / "assets" / a.name).exists():
                        shutil.copy(a, d / "assets" / a.name)
                b["start_from"] = sp["id"]
                if sp.get("use_next"):
                    lib_set(sp["id"], use=False)
        shutil.copy(SKILL / "template" / "hyperframes.json", d / "hyperframes.json")
        if gsap.exists():
            shutil.copy(gsap, d / "assets" / "gsap.min.js")
        (d / "beat.json").write_text(json.dumps(b, indent=1), encoding="utf-8")
        w, h = b["size"]
        (d / "brief.md").write_text(BRIEF.format(
            id=b["id"], card=SKILL / "references" / "clip-brief-card.md", dir=d.resolve(), w=w, h=h, dur=b["dur"],
            cw=800 if aspect == "9:16" else 760, lead=CARD_LEAD_S,
            placement=("over the footage, popping in {lead} s before its word. Fill the card edge to edge: no inner margin of "
                       "ground.\n  Its bottom fifth may sit behind the speaker's hair: nothing that must be read goes there."
                       ).format(lead=CARD_LEAD_S) if not b.get("panel") and not b.get("board") else
                      ("beside the speaker, on one side of a 16:9 frame (the speaker is moved to the other side), popping in "
                       f"{CARD_LEAD_S} s before its word. Its ground is the canvas's own near-black ({look['ground']}): dark "
                       "silver-rimmed tiles, real logos, lowercase labels in the speaker's words, 2 px dashed connectors. "
                       "Fill it edge to edge.") if b.get("board") else
                      ("in the 50/50 panel: the top of the frame, above the speaker, the whole panel. Its ground is the panel's own "
                       f"({look['ground']}), so it has no edge: no card, border or shadow round the exhibit. Fill at least 55% of it."), look=json.dumps(look), line=b["line"],
            before=b["before"], after=b["after"], words=json.dumps(b["words"]), type=b["type"], props=json.dumps(b["props"]),
            images=", ".join(str((edit / "images" / p).resolve()) for p in pics) or "none", motion=Path(__file__).resolve(), rounds=ROUNDS,
            env=f'AI_EDITOR_HOME="{os.environ["AI_EDITOR_HOME"]}" ' if os.environ.get("AI_EDITOR_HOME") else "",
            start=("- This edit's number beats are its kinetic titles' (words over the footage, on other lines): no counter, "
                   "nothing counting up, and no figure but those said in `WORDS`, shown as said.\n" if b.get("beside_kinetic") else "") +
                  ("- A clip the user approved before is in `start.html` (same kind of beat). You may start from its design, "
                  "but re-time every part to this clip's `WORDS` and change it for this line: an unchanged copy fails "
                  "`check`.\n- Notes on this clip, if any: `notes.md` beside this brief. Do what they say.\n\n"
                  if b.get("start_from") else "- Notes on this clip, if any: `notes.md` beside this brief. Do what they say.\n\n")),
            encoding="utf-8")
    (root / "beats.json").write_text(json.dumps({"clock": "cut", "look": look, "beats": beats}, indent=1), encoding="utf-8")
    if not gsap.exists():
        print("note: the motion tools are not installed: python3 setup.py motion (setup skill), then pick again")
    for b in beats:
        print(f"{b['id']:<22} {b['type']:<13} {b['start']:6.2f}s +{b['dur']:.2f}s  \"{b['line'][:60]}\"")
    print(f"{len(beats)} clip(s) in {root}. One clip-builder agent per clip, all in one message, "
          f"each given {root}/<id>/brief.md.")
    return beats


def run(cmd, cwd=None, timeout=900):
    try:
        p = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def last(text, n=6):
    return "\n".join([ln for ln in text.strip().splitlines() if ln.strip() and not ln.startswith("[hyperframes]")][-n:])


def sheets(video, out_dir, dur):
    """renders/sheet.png: one frame a second; renders/strip.png: 10 fps over the first 1.2 s (motion, not stills)."""
    n = max(1, int(dur))
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", f"fps=1,scale=360:-1,tile={min(n, 6)}x{(n + 5) // 6}",
         "-frames:v", "1", out_dir / "sheet.png"])
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-t", "1.2", "-vf", "fps=10,scale=300:-1,tile=6x2",
         "-frames:v", "1", out_dir / "strip.png"])


def cream(rgb):
    """style-edit ai_tells.is_cream: a warm off-white ground, the banned "cream-paper-ground" tell in a card."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return 20 <= h * 360 <= 60 and 0.04 <= s <= 0.3 and v >= 0.78


def ground_of(video, w, h):
    """(rgb, share) of the dominant colour of the clip's frame at 3/4 of its length, quantised like ai_tells.cream_ground."""
    import numpy as np
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                               capture_output=True, text=True).stdout.strip() or 1)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * 0.75:.3f}", "-i", str(video), "-frames:v", "1", "-vf",
                          f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    q = (np.frombuffer(raw[:w * h * 3], np.uint8).reshape(-1, 3) >> 4).astype(np.int32)
    keys, counts = np.unique(q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2], return_counts=True)
    k = int(keys[counts.argmax()])
    return (((k >> 8) & 15) * 16 + 8, ((k >> 4) & 15) * 16 + 8, (k & 15) * 16 + 8), counts.max() / len(q)


def panel_fill(video, ground, tol=10, min_fill=0.55):
    """The 50/50 PANEL gate (the house check_clip_ground.py, panel mode): the corners are the panel's ground (no edge
    for a mismatch to draw) and the ink band covers at least min_fill of the panel, sampled at 3/4 of the clip."""
    import numpy as np
    w, h = 240, 200
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                               capture_output=True, text=True).stdout.strip() or 1)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * 0.75:.3f}", "-i", str(video), "-frames:v", "1", "-vf",
                          f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    f = np.frombuffer(raw[:w * h * 3], np.uint8).reshape(h, w, 3).astype(int)
    off = [tuple(int(v) for v in f[y, x]) for y, x in ((1, 1), (1, w - 2), (h - 2, 1), (h - 2, w - 2))
           if max(abs(int(a) - b) for a, b in zip(f[y, x], ground)) > tol]
    ink = np.abs(f - np.array(ground)).max(axis=2) > 24
    rows, cols = np.where(ink.any(axis=1))[0], np.where(ink.any(axis=0))[0]
    fill = ((rows[-1] - rows[0] + 1) * (cols[-1] - cols[0] + 1) / (w * h)) if len(rows) and len(cols) else 0.0
    cx = ((cols[0] + cols[-1]) / 2 / w) if len(cols) else 0.5
    msgs = ([f"the drawing's centre is {abs(cx - 0.5):.0%} of the width off the panel's centre (the render check fails 2%)"]
            if abs(cx - 0.5) > 0.02 else []) + ([f"{len(off)} corner(s) are not the panel's ground #{''.join(f'{c:02x}' for c in ground)}: the exhibit draws an edge"]
            if off else []) + ([f"the ink band fills {fill:.0%} of the panel (under {min_fill:.0%})"] if fill < min_fill else [])
    return not msgs, "; ".join(msgs) or f"corners on the ground, ink band {fill:.0%} of the panel"


def check(clip_dir):
    """Every gate on one clip, the render, the sheets. gates.json: {"pass", "round", "gates": {name: [ok, detail]}}."""
    d = Path(clip_dir).resolve()
    hf = hf_bin()
    if not hf:
        sys.exit("ERROR: the motion tools are not installed. Run the setup skill's motion step: python3 setup.py motion")
    prev = json.loads((d / "gates.json").read_text(encoding="utf-8")) if (d / "gates.json").exists() else {}
    beat = json.loads((d / "beat.json").read_text(encoding="utf-8")) if (d / "beat.json").exists() else {}
    g, render = {}, d / "renders" / "clip.mp4"
    import check_clip
    err, warn = check_clip.check((d / "index.html").read_text(encoding="utf-8"), clip_id=d.name)
    g["check_clip"] = [not err, "; ".join(m for _, m in err)[:600] or f"{len(warn)} warning(s)"]
    if same_as_start(d):
        g["reuse"] = [False, "index.html is the library clip in start.html unchanged: re-time it to WORDS and change it for this line"]
    if g["check_clip"][0]:
        rc, out = run([hf, "lint", str(d)])
        g["lint"] = [rc == 0, last(out, 4)]
        rc, out = run([hf, "check", str(d), "--at-transitions", "--samples", "24", "--no-contrast"])
        g["layout"] = [rc == 0, last(out, 6)]
        if g["lint"][0]:
            (d / "renders").mkdir(exist_ok=True)
            rc, out = run([hf, "render", str(d), "-o", str(render), "--quality", "looks", "--quiet"], timeout=1800)
            g["render"] = [rc == 0 and render.exists(), last(out, 3) if rc else str(render)]
    if g.get("render", [False])[0]:
        rc, out = run([sys.executable, HERE / "check_motion.py", render, d / "index.html"])
        g["motion"] = [rc == 0, last(out, 8)]
        rc, out = run([sys.executable, HERE / "check_composition.py", render, d / "index.html"])
        g["composition (advisory)"] = [True, last(out, 5)]
        rgb, share = ground_of(render, 120, 64)
        look = json.loads((d.parent / "beats.json").read_text(encoding="utf-8")).get("look", {}) if (d.parent / "beats.json").exists() else {}
        lg = (look.get("ground") or "#FFFFFF").lstrip("#")
        own = cream(tuple(int(lg[i:i + 2], 16) for i in (0, 2, 4))) if len(lg) == 6 else False
        bad = share > 0.5 and cream(rgb) and not own
        g["ground"] = [not bad, f"{share:.0%} of the frame at 3/4 is #{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}" +
                       (": a cream paper ground, banned in a card; use the look's ground or the real surface" if bad else "")]
        node = shutil.which("node")
        if node:   # the four proofs (verify.mjs): blocking in the 50/50 panel, advisory on a card (a 1 s card is not read whole)
            rc, out = run([node, HERE / "verify.mjs", d] + (["--rails"] if beat.get("size") == [1080, 1920] else []), timeout=600)
            try:
                pr = json.loads(out.strip().splitlines()[-1])
                detail = f"clipped {pr['clipped']}, rails {pr['rails']}, neighbour {pr['neighbour']}, reading {pr['reading']}" + \
                         (": " + "; ".join(pr["notes"][:3]) if pr["notes"] else "")
                g["proofs" if beat.get("panel") else "proofs (advisory)"] = [pr["pass"] or not beat.get("panel"), detail]
            except (ValueError, IndexError, KeyError):
                g["proofs (advisory)"] = [True, "not run: " + last(out, 1)]
        png = d / "renders" / "tells.png"   # the editor's generated-look tells on a settled frame (style-edit ai_tells.py)
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{beat.get('dur', 2) * 0.75:.2f}", "-i", render, "-frames:v", "1", png])
        allow = "cream-paper-ground" if own else ""
        rc, out = run([sys.executable, PLUGIN / "lib" / "ai_editor" / "run.py", SKILL.parent / "style-edit" / "scripts" / "ai_tells.py",
                       "still", png] + (["--allow", allow] if allow else []))
        if "No module named" in out or "cannot read" in out:
            g["tells (advisory)"] = [True, "not run: " + last(out, 1)]
        else:
            bans = [ln.split(None, 2)[1] for ln in out.splitlines() if ln.startswith("BAN")]
            g["tells"] = [not bans, ("banned look: " + ", ".join(bans) + " (style-edit references/ai-tells.md)") if bans else "none"]
        if beat.get("panel"):
            ok, msg = panel_fill(render, tuple(int(lg[i:i + 2], 16) for i in (0, 2, 4)) if len(lg) == 6 else (255, 255, 255))
            g["panel"] = [ok, msg]
        import measure_ink
        top, bot = measure_ink.ink_band(str(render))
        g["ink"] = [True, f"ink band {top:.2f}-{bot:.2f} of the height"]
        sheets(render, d / "renders", beat.get("dur", 3))
    ok = all(v[0] for v in g.values()) and "render" in g
    res = {"pass": ok, "round": prev.get("round", 0) + 1, "gates": g,
           "render": str(render) if render.exists() else "", "sheet": str(d / "renders" / "sheet.png"),
           "strip": str(d / "renders" / "strip.png")}
    (d / "gates.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for k, (o, detail) in g.items():
        print(f"{'ok  ' if o else 'FAIL'} {k}: {detail.splitlines()[-1] if detail else ''}")
    print(f"{'PASS' if ok else 'FAIL'} check {res['round']} ({ROUNDS} to build, 2 more per note). Look at {res['sheet']} and {res['strip']}.")
    return 0 if ok else 1


def motion_window(video):
    import clip_motion
    m = clip_motion.motion(video)
    return m or (0.0, 0.0, 0.0)


def placed_beat(orig, beat, src, first, last_):
    """The video_card beat for a passed clip: motion finishes FINISH_S before the card leaves (clip_motion.py)."""
    hold = beat["dur"]
    start_s = round(max(0.0, min(first, last_ + FINISH_S - hold)), 2) if last_ else 0.0
    return {"word": beat["word"], "nth": beat["nth"], "kind": "anim", "type": "video_card", "hold_s": hold,
            "props": {"src": src, "size": beat["size"], "start_s": start_s, "motion": beat["id"],
                      **({"bare": True} if beat.get("panel") else {})}, "motion": beat["id"],
            "fallback": orig}


def place(edit):
    edit = Path(edit)
    vf = edit / "visuals.json"
    visuals = json.loads(vf.read_text(encoding="utf-8"))
    doc = json.loads((edit / "motion" / "beats.json").read_text(encoding="utf-8"))
    by_id = {v.get("motion"): i for i, v in enumerate(visuals) if v.get("motion")}
    placed, back = [], []
    veto = place_veto(edit, visuals)
    for b in doc["beats"]:
        d = edit / "motion" / b["id"]
        gates = json.loads((d / "gates.json").read_text(encoding="utf-8")) if (d / "gates.json").exists() else {}
        i = by_id.get(b["id"])
        if i is None:   # still the template beat: find it by word and type
            i = next((k for k, v in enumerate(visuals) if v.get("word") == b["word"] and v.get("nth", 1) == b["nth"]
                      and v.get("type") == b["type"]), None)
        if i is None:
            continue
        orig = visuals[i].get("fallback") or visuals[i]
        render = d / "renders" / "clip.mp4"
        why = veto(b)
        if why:   # kinetic titles turned on, or their beats moved, since pick: the template stays
            visuals[i] = orig
            back.append(f"{b['id']} -> {b['type']} template ({why})")
        elif gates.get("pass") and render.exists() and not gates.get("rejected"):
            (edit / "images").mkdir(exist_ok=True)
            import hashlib   # the name changes with the render, so edit.py patch re-renders only this clip's span
            tag = hashlib.sha256(render.read_bytes()).hexdigest()[:8]
            for old in (edit / "images").glob(f"motion-{b['id']}-*.mp4"):
                old.unlink()
            dst = edit / "images" / f"motion-{b['id']}-{tag}.mp4"
            shutil.copy(render, dst)
            _, first, last_ = motion_window(dst)
            visuals[i] = placed_beat(orig, b, f"images/{dst.name}", first, last_)
            placed.append(f"{b['id']} (motion {first:.2f}-{last_:.2f} s, from {visuals[i]['props']['start_s']} s)")
        else:
            visuals[i] = orig
            back.append(f"{b['id']} -> {b['type']} template ({'not built' if not gates else 'did not pass'})")
    vf.write_text(json.dumps(visuals, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"placed {len(placed)}: " + "; ".join(placed))
    if back:
        print(f"template {len(back)}: " + "; ".join(back))
    return placed, back


def cut_duration(edit, style):
    """The cut's length plan.py counts the graphics budget over (style-edit kinetic_beats.video_duration), or None:
    kinetic titles off, or no cut.mp4 (the last word's end then)."""
    if not (((style or {}).get("graphics") or {}).get("kinetic")):
        return None
    sys.path[:0] = [str(SKILL.parent / "style-edit" / "scripts"), str(PLUGIN / "lib")]
    import kinetic_beats
    return kinetic_beats.video_duration(edit)


def place_veto(edit, visuals):
    """For place: beat -> why it stays its template beside kinetic titles (split_veto), else None. Kinetic titles off,
    or no captions.json and style.json to read them from: never."""
    edit = Path(edit)
    if not ((edit / "style.json").exists() and (edit / "captions.json").exists()):
        return lambda b: None
    style = effective(edit)
    words = [w for w in json.loads((edit / "captions.json").read_text(encoding="utf-8")) if w.get("type", "word") == "word"]
    images = json.loads((edit / "images.json").read_text(encoding="utf-8")) if (edit / "images.json").exists() else []
    split = kinetic_split(style, words, [v.get("fallback") or v for v in visuals], images, cut_duration(edit, style))
    if split is None:
        return lambda b: None
    sents, types = sentences(words), split_types(allowed_types(motion_cfg(style)))
    return lambda b: split_veto(b, split, sents, types)


def status(edit):
    root = Path(edit) / "motion"
    doc = json.loads((root / "beats.json").read_text(encoding="utf-8"))
    for b in doc["beats"]:
        g = root / b["id"] / "gates.json"
        s = json.loads(g.read_text(encoding="utf-8")) if g.exists() else {}
        st = "passed" if s.get("pass") else (f"failed round {s['round']}" if s else "building")
        print(f"{b['id']:<22} {st}")


def strips(video, times, out, before=0.4, after=1.1, fps=10, safe=False, width=240):
    """One row per time: consecutive frames at `fps` from t-before to t+after. With safe, the reels safe zone
    (x 60-940, y 250-1440 of 1080x1920) is drawn on every frame."""
    tmp = Path(tempfile.mkdtemp(prefix="strips-"))
    try:
        rows = []
        n = int(round((before + after) * fps)) + 1
        box = ",drawbox=x=iw*60/1080:y=ih*250/1920:w=iw*880/1080:h=ih*1190/1920:color=red@0.9:t=3" if safe else ""
        for k, t in enumerate(times):
            row = tmp / f"row{k}.png"
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t - before):.3f}", "-t", f"{before + after + 0.5 / fps:.3f}",
                 "-i", video, "-vf", f"fps={fps}{box},scale={width}:-2,tile={n}x1:padding=2", "-frames:v", "1", row])
            if row.exists():
                rows.append(row)
        if not rows:
            sys.exit("ERROR: no frames read from " + str(video))
        args = ["ffmpeg", "-v", "error", "-y"]
        for r in rows:
            args += ["-i", r]
        args += ["-filter_complex", f"vstack=inputs={len(rows)}" if len(rows) > 1 else "null", out]
        rc, msg = run(args)
        if rc:
            sys.exit("ERROR: " + last(msg, 2))
        print(f"wrote {out}: one row per time ({', '.join(f'{t:.2f}' for t in times)} s), {n} frames each at {fps} fps, "
              f"from {before} s before to {after} s after")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---- the motion library: clips the user approved, kept per user to start a matching beat from (never reused unchanged)
def library_dir():
    return home() / "motion-library"


def lib_entries():
    """Every saved clip's meta.json, newest first; archived ones included (flag "archived")."""
    out = []
    for m in library_dir().glob("*/meta.json"):
        try:
            out.append(json.loads(m.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda e: -e.get("made", 0))


def save(edit, clip=None):
    """Copy each placed clip (composition, brief, beat, small assets, a thumbnail) into the library. Run when the user
    approves the render. Returns the saved ids; a clip already saved (same composition) is skipped."""
    import hashlib
    import time
    edit = Path(edit)
    visuals = json.loads((edit / "visuals.json").read_text(encoding="utf-8"))
    style = json.loads((edit / "style.json").read_text(encoding="utf-8")) if (edit / "style.json").exists() else {}
    doc = json.loads((edit / "motion" / "beats.json").read_text(encoding="utf-8"))
    placed = {v.get("motion") for v in visuals if v.get("motion")}
    saved = []
    for b in doc["beats"]:
        d = edit / "motion" / b["id"]
        if b["id"] not in placed or (clip and clip != b["id"]) or not (d / "index.html").exists():
            continue
        html = (d / "index.html").read_text(encoding="utf-8")
        lid = f"{b['type']}-{hashlib.sha256(html.encode()).hexdigest()[:10]}"
        dst = library_dir() / lid
        if dst.exists():
            continue
        (dst / "assets").mkdir(parents=True)
        for f in ("index.html", "brief.md", "beat.json", "hyperframes.json"):
            if (d / f).exists():
                shutil.copy(d / f, dst / f)
        for a in (d / "assets").glob("*"):
            if a.is_file() and a.stat().st_size < 20e6:
                shutil.copy(a, dst / "assets" / a.name)
        render = d / "renders" / "clip.mp4"
        if render.exists():
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{b['dur'] * 0.6:.2f}", "-i", render, "-frames:v", "1",
                 "-vf", "scale=480:-2", dst / "thumb.jpg"])
        kind = next((k for k, ts in KINDS.items() if b["type"] in ts), b["type"])
        meta = {"id": lid, "type": b["type"], "kind": kind, "line": b["line"], "size": b["size"], "dur": b["dur"],
                "style": style.get("handle") or "", "look": doc.get("look", {}).get("name", "default"),
                "made": time.time(), "archived": False, "use_next": False}
        (dst / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        saved.append(lid)
    print(f"saved {len(saved)} clip(s) to {library_dir()}" + (": " + ", ".join(saved) if saved else ""))
    return saved


def lib_set(lid, archived=None, use=None):
    """Archive (never used again) or bring back; "use again" marks it the first starting point for its kind."""
    f = library_dir() / lid / "meta.json"
    if not re.fullmatch(r"[a-z_]+-[0-9a-f]{10}", lid or "") or not f.exists():
        raise KeyError(lid)
    m = json.loads(f.read_text(encoding="utf-8"))
    if archived is not None:
        m["archived"] = bool(archived)
        m["use_next"] = False if archived else m.get("use_next", False)
    if use is not None:
        m["use_next"] = bool(use) and not m.get("archived")
    f.write_text(json.dumps(m, indent=1), encoding="utf-8")
    return m


def starting_point(kind_type):
    """The library clip a new beat of this template type starts from: "use again" first, then the newest. Archived
    clips never."""
    c = [e for e in lib_entries() if e.get("type") == kind_type and not e.get("archived")]
    c.sort(key=lambda e: (not e.get("use_next"), -e.get("made", 0)))
    return c[0] if c else None


def same_as_start(d):
    """True when index.html is the library starting point with only its id swapped: a straight copy."""
    st, ix = d / "start.html", d / "index.html"
    if not (st.exists() and ix.exists()):
        return False
    a, b = st.read_text(encoding="utf-8"), ix.read_text(encoding="utf-8")
    old = re.search(r'data-composition-id="([^"]+)"', a)
    if old:
        a = a.replace(old[1], d.name)
    norm = lambda t: re.sub(r"\s+", "", t)
    return norm(a) == norm(b)


def note(edit, text, at=None, clip=None):
    """A note on one clip (the review page note's time, or the clip id): appended to that clip's notes.md, so only it
    is rebuilt. Prints what to run next and the span edit.py patch re-renders."""
    edit = Path(edit)
    doc = json.loads((edit / "motion" / "beats.json").read_text(encoding="utf-8"))
    b = next((x for x in doc["beats"] if x["id"] == clip or (at is not None and x["start"] <= at <= x["start"] + x["dur"])), None)
    if not b:
        sys.exit(f"no motion clip {'named ' + clip if clip else f'up at {at} s'}: a note for another card goes to the overlays skill")
    d = edit / "motion" / b["id"]
    with open(d / "notes.md", "a", encoding="utf-8") as fh:
        fh.write(f"- {text.strip()}" + (f" (said at {at:.2f} s)" if at is not None else "") + "\n")
    print(f"note on {b['id']}: give one clip-builder {d / 'brief.md'} and this note (up to 2 checks), then "
          f"motion.py place, plan.py, and edit.py patch (re-renders {b['start']:.2f}-{b['start'] + b['dur']:.2f} s only)")
    return b["id"]


def demo():
    words = [{"text": w, "start": i * 0.5, "end": i * 0.5 + 0.4, "type": "word"}
             for i, w in enumerate("over ten thousand people asked. it renders every frame. then it learns.".split())]
    visuals = [{"word": "over", "nth": 1, "kind": "anim", "type": "likes", "hold_s": 2.0, "props": {"counts": [{"n": 0}]}},
               {"word": "renders", "nth": 1, "kind": "anim", "type": "progress", "hold_s": 0.6},
               {"word": "every", "nth": 1, "kind": "logo", "brand": "x"},
               {"word": "learns", "nth": 1, "kind": "anim", "type": "notes", "hold_s": 3.0}]
    bs = beats_for(visuals, words)
    assert [b["type"] for b in bs] == ["likes", "notes"], bs   # progress: room for 0.6 s only, keeps its template
    assert bs[0]["start"] == 0.0 and bs[0]["dur"] == 2.0 and bs[0]["clock"] == "cut", bs[0]
    assert bs[0]["words"][0] == {"w": "over", "t": 0.0} and bs[0]["line"].startswith("over ten"), bs[0]
    assert bs[1]["start"] == 5.4 and bs[1]["dur"] == 1.0, bs[1]   # to the end of the take
    assert beats_for(visuals, words, max_n=1)[0]["type"] == "likes"   # the longest window wins
    cfg = motion_cfg({"motion": {"kinds": {"counter": False}}})
    assert [b["type"] for b in beats_for(visuals, words, types=allowed_types(cfg))] == ["notes"]
    assert beats_for(visuals, words, amount=0.5)[0]["type"] == "likes" and len(beats_for(visuals, words, amount=0.5)) == 1
    assert allowed_types(motion_cfg({"motion": {"engine": "templates"}})) == ()
    # promoted: a 4-item list visual-prep sent to a card becomes a notes clip; amount 0 or the kind off promotes nothing
    lw = [{"text": w, "start": i * 0.5, "end": i * 0.5 + 0.4, "type": "word"}
          for i, w in enumerate("you need captions, zooms, music and cards. it is red, blue and green. follow me now.".split())]
    lv = [{"word": "need", "nth": 1, "kind": "card", "text": "captions"}, {"word": "cards.", "nth": 1, "kind": "logo", "brand": "x"},
          {"word": "red,", "nth": 1, "kind": "card", "text": "red"}, {"word": "follow", "nth": 1, "kind": "card", "text": "follow"}]
    pb = beats_for(lv, lw)
    assert [(b["type"], b["word"], b.get("promoted")) for b in pb] == [("notes", "need", "card")], pb   # one per sentence, three items is no list
    assert beats_for(lv, lw, amount=0) == []
    assert beats_for(lv, lw, types=allowed_types(motion_cfg({"motion": {"kinds": {"list": False}}}))) == []
    assert promote_type("first cut it, then render it") == "flow" and promote_type("before it took a week") == "side_by_side"
    assert promote_type("it is red, blue and green") is None and promote_type("over 10,000 people") == "likes"
    assert [b["type"] for b in beats_for(visuals, words)] == ["likes", "notes"], "a sentence with an animation gets no second"
    assert card_size({"heads": [{"t": 1.0, "box": [30, 31, 40, 40]}]}, 0.5, 2) == [1200, 550], card_size(
        {"heads": [{"t": 1.0, "box": [30, 31, 40, 40]}]}, 0.5, 2)   # head top at 31%: a 2.2:1 card
    assert card_size(None, 0, 1) == [1200, 630] and card_size({"heads": [{"t": 1, "box": [0, 60, 9, 9]}]}, 0, 2)[1] == 750
    html = fill_template(bs[0], DEFAULT_LOOK)
    assert "__" not in re.sub(r"__timelines", "", html) and 'data-duration="2.00"' in html and "var DURATION = 2.00" in html
    import check_clip
    err, _ = check_clip.check(html, clip_id=bs[0]["id"])
    assert not err, err
    assert look_for({})["ground"] == "#FFFFFF" and look_for({"look": {"preset": "mono"}})["font"] == "IBM Plex Sans"
    assert look_for({}, {"brand": {"accent": "#FF0000"}})["accent"] == "#FF0000"
    p = placed_beat(visuals[0], bs[0], "images/motion-01-over.mp4", 0.1, 2.1)
    assert p["props"]["start_s"] == 0.1 and p["fallback"] is visuals[0] and p["type"] == "video_card", p   # skips to finish
    assert placed_beat(visuals[0], bs[0], "x", 0.2, 1.0)["props"]["start_s"] == 0.0
    with tempfile.TemporaryDirectory() as t:   # place: a passed clip in, a failed one back to its template
        e = Path(t)
        (e / "visuals.json").write_text(json.dumps(visuals), encoding="utf-8")
        (e / "motion").mkdir()
        (e / "motion" / "beats.json").write_text(json.dumps({"beats": bs}), encoding="utf-8")
        for b, ok in zip(bs, (True, False)):
            (e / "motion" / b["id"] / "renders").mkdir(parents=True)
            (e / "motion" / b["id"] / "gates.json").write_text(json.dumps({"pass": ok}), encoding="utf-8")
        clip = e / "motion" / bs[0]["id"] / "renders" / "clip.mp4"
        rc, _ = run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=120x64:r=30:d=2", "-pix_fmt", "yuv420p", clip])
        if rc == 0:
            placed, back = place(e)
            v = json.loads((e / "visuals.json").read_text(encoding="utf-8"))
            assert v[0]["type"] == "video_card" and v[0]["fallback"]["type"] == "likes" and list((e / "images").glob(f"motion-{bs[0]['id']}-*.mp4")), v[0]
            assert v[3]["type"] == "notes" and len(back) == 1, (v[3], back)
            (e / "motion" / bs[0]["id"] / "gates.json").write_text(json.dumps({"pass": False}), encoding="utf-8")
            place(e)
            assert json.loads((e / "visuals.json").read_text(encoding="utf-8"))[0]["type"] == "likes"   # failed later: the template again
            v = e / "frame.mp4"   # strips: 16 consecutive frames a row, the safe box drawn
            run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=108x192:r=30:d=3", "-pix_fmt", "yuv420p", v])
            strips(v, [1.0, 2.0], e / "s.png", width=60, safe=True)
            rc, wh = run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", e / "s.png"])
            assert wh.strip().split(",")[0] == str(16 * 60 + 15 * 2), wh
    assert cream((253, 248, 236)) and not cream((255, 255, 255)) and not cream((23, 22, 20))
    assert panel_size({}) is None and panel_size({"layout": {"mode": "split", "seam": 50}}) == [1200, 1006]
    assert board_size({}) is None and board_size({"layout": {"mode": "board"}}) == [1200, 964]
    assert look_for({"motion": {"look": "board"}})["ground"] == "#0B0B0D"
    with tempfile.TemporaryDirectory() as t:   # the panel gate: a full-bleed drawing passes, a small one on white fails
        for name, vf, want in (("ok", "drawbox=x=20:y=20:w=200:h=160:color=black:t=fill", True),
                               ("small", "drawbox=x=100:y=90:w=30:h=20:color=black:t=fill", False)):
            v = Path(t) / f"{name}.mp4"
            run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=0xFDF8EC:s=240x200:d=1:r=30", "-vf", vf, "-pix_fmt", "yuv444p", v])
            assert panel_fill(v, (0xFD, 0xF8, 0xEC))[0] is want, (name, panel_fill(v, (0xFD, 0xF8, 0xEC)))
    assert motion_cfg({"graphics": {"kinds": {"animation": 55}}})["amount"] == 0.55   # a measured style's share
    assert motion_cfg({"motion": {"amount": 0}, "graphics": {"kinds": {"animation": 55}}})["amount"] == 0.0
    assert look_for({"motion": {"look": "mono"}, "look": {"preset": "editorial"}})["name"] == "mono"
    with tempfile.TemporaryDirectory() as t:   # library: save, reuse as a starting point, archive, no straight copy
        keep = os.environ.get("AI_EDITOR_HOME")
        os.environ["AI_EDITOR_HOME"] = str(Path(t) / "home")
        try:
            e = Path(t) / "ed"
            b = dict(bs[0])
            (e / "motion" / b["id"] / "renders").mkdir(parents=True)
            (e / "motion" / b["id"] / "index.html").write_text(fill_template(b, DEFAULT_LOOK).replace("// 4.", "// built\n// 4."), encoding="utf-8")
            (e / "motion" / "beats.json").write_text(json.dumps({"look": DEFAULT_LOOK, "beats": [b]}), encoding="utf-8")
            (e / "visuals.json").write_text(json.dumps([placed_beat(visuals[0], b, "x", 0, 1)]), encoding="utf-8")
            lid = save(e)[0]
            assert save(e) == [] and lib_entries()[0]["kind"] == "counter" and starting_point("likes")["id"] == lid
            d = e / "motion" / "x-new"
            d.mkdir()
            shutil.copy(library_dir() / lid / "index.html", d / "start.html")
            (d / "index.html").write_text((d / "start.html").read_text(encoding="utf-8").replace(b["id"], "x-new"), encoding="utf-8")
            assert same_as_start(d)
            (d / "index.html").write_text((d / "index.html").read_text(encoding="utf-8").replace("// built", "// re-timed"), encoding="utf-8")
            assert not same_as_start(d)
            lib_set(lid, use=True)
            assert starting_point("likes")["use_next"]
            lib_set(lid, archived=True)
            assert starting_point("likes") is None   # archived: never used
            assert note(e, "make the counter bigger", at=b["start"] + 0.5) == b["id"]
            assert "bigger" in (e / "motion" / b["id"] / "notes.md").read_text(encoding="utf-8")
        finally:
            if keep is None:
                os.environ.pop("AI_EDITOR_HOME", None)
            else:
                os.environ["AI_EDITOR_HOME"] = keep
    demo_kinetic()
    print("demo ok")


def demo_kinetic():
    """Beside kinetic titles (the fork's split): a made-up take with a count, a list and a before and after."""
    import hashlib
    import inspect
    sys.path.insert(0, str(SKILL.parent / "style-edit" / "scripts"))
    import kinetic_beats
    # kinetic titles off: upstream's beats_for, byte for byte, and pick calls it as upstream does
    assert hashlib.sha256(inspect.getsource(beats_for).encode()).hexdigest() == BEATS_FOR_SHA, \
        "beats_for is no longer upstream 2.7.8's: check split_beats still wraps it, then update BEATS_FOR_SHA"
    words = kinetic_beats.timed("Our bakery sold 340 loaves in one week. It was a long and happy week for every one of us "
                                "at the shop. You need flour, water, salt and time. Before we kneaded every loaf by hand, "
                                "now the mixer does it.")
    lst = {"word": "need", "nth": 1, "kind": "card", "text": "flour"}   # visual-prep sent the list to a card
    ba = {"word": "Before", "nth": 1, "kind": "anim", "type": "side_by_side", "hold_s": 3.0, "props": {"a": "hand", "b": "mixer"}}
    stray = {"word": "sold", "nth": 1, "kind": "anim", "type": "likes", "hold_s": 2.5, "props": {"counts": [{"n": 340}]}}
    on = {"graphics": {"kinetic": True, "kinetic_per_min": 30}}

    def picked(visuals, style, images=()):
        sp = kinetic_split(style, words, visuals, images)
        if sp is None:
            return [(b["type"], b["word"]) for b in beats_for(visuals, words, images=images)]
        return [(b["type"], b["word"]) for b in split_beats(visuals, words, images=images, split=sp, style=style)[0]]
    # the count is the titles' (a hook here); the list and the before and after are the clips'
    sp = kinetic_split(on, words, [lst, ba])
    assert [k[2] for k in sp["kept"]] == ["340"] and sp["units"] == 1, sp
    assert picked([lst, ba], on) == [("notes", "need"), ("side_by_side", "Before")], picked([lst, ba], on)
    # a counter visual-prep put on the count line anyway (or a card there a figure promotes): never a clip beside them;
    # with kinetic titles off, upstream's counter clip
    assert picked([stray, lst, ba], on) == picked([{**stray, "kind": "card"}, lst, ba], on) == [("notes", "need"), ("side_by_side", "Before")]
    assert picked([stray, lst, ba], {}) == [("likes", "sold"), ("notes", "need"), ("side_by_side", "Before")]
    assert picked([{**stray, "kind": "card"}, lst, ba], {"graphics": {"kinetic": False}})[0] == ("likes", "sold")
    # a full budget: the number beat and two real screenshots fill 12 a minute over this take (3), so no clip (budget.pick
    # keeps the screenshots, each clear of the cards it keeps, over the templates the clips would replace)
    twelve = {"graphics": {"kinetic": True, "kinetic_per_min": 12}}
    shots = [{"src": "images/a.png", "word": "every", "nth": 1}, {"src": "images/b.png", "word": "salt", "nth": 1}]
    sp = kinetic_split(twelve, words, [lst, ba], shots)
    assert (sp["allowance"], sp["units"]) == (3, 1) and picked([lst, ba], twelve, shots) == [], sp
    # ... one screenshot leaves room for one: the one plan.py keeps, the before and after (the list's template would sit
    # right after the screenshot, so budget.pick spreads the picks out to the before and after)
    lta = {"word": "need", "nth": 1, "kind": "anim", "type": "notes", "hold_s": 2.5}
    assert picked([lta, ba], twelve, shots[:1]) == [("side_by_side", "Before")]
    # ... a list visual-prep routed to a card is ranked as that card, before the moving templates (budget.later)
    assert picked([lst, ba], twelve, shots[:1]) == [("notes", "need")]
    # a likes beat is never a clip beside the titles, even on a line whose only figure they would not draw ("twice")
    tw = kinetic_beats.timed("Our bakery sold 340 loaves in one week. It was a long and happy week for every one of us "
                             "at the shop. The new oven is twice as fast as the old one.")
    twice = {"word": "oven", "nth": 1, "kind": "anim", "type": "likes", "hold_s": 2.5, "props": {}}
    assert [b["type"] for b in split_beats([twice], tw, split=kinetic_split(on, tw, [twice]), style=on)[0]] == []
    assert [b["type"] for b in beats_for([twice], tw)] == ["likes"]   # kinetic titles off: upstream's counter clip
    # a placed clip counts as its template, so placing one never moves the number beats (kinetic_beats.refresh's
    # fingerprint and the beats found stay the same)
    wtk = kinetic_beats.Take(words)
    placed_ba = placed_beat(ba, {"word": "Before", "nth": 1, "dur": 3.0, "size": [1200, 630], "id": "02-before"}, "images/m.mp4", 0, 0)
    assert kinetic_beats.real_cards(wtk, [placed_ba], (), on, 15.0) == kinetic_beats.real_cards(wtk, [ba], (), on, 15.0)
    assert kinetic_beats.beats(words, on, [lst, placed_ba]) == kinetic_beats.beats(words, on, [lst, ba])
    demo_windows()
    demo_order()
    # a clip is never up with a number beat (one written by hand, held long); without the titles it is upstream's clip
    held = {"word": "340", "nth": 1, "kind": "anim", "type": "kinetic_number", "hold_s": 6.0, "props": {"num": "340", "word": "340"}}
    near = {"word": "It", "nth": 1, "kind": "anim", "type": "notes", "hold_s": 3.0}
    assert picked([held, near, lst], on) == [("notes", "need")], picked([held, near, lst], on)
    assert picked([near, lst], {})[0] == ("notes", "It")
    with tempfile.TemporaryDirectory() as t:   # pick and place on an edit folder, the test home's own taste
        keep = os.environ.get("AI_EDITOR_HOME")
        os.environ["AI_EDITOR_HOME"] = str(Path(t) / "home")
        try:
            e = Path(t) / "ed"
            e.mkdir()
            (e / "captions.json").write_text(json.dumps(words), encoding="utf-8")
            vis = [stray, lst, ba]
            (e / "visuals.json").write_text(json.dumps(vis), encoding="utf-8")
            (e / "style.json").write_text(json.dumps({"aspect": "9:16"}), encoding="utf-8")
            off = pick(e)   # kinetic titles off: exactly upstream's beats_for, as upstream's pick called it
            assert json.dumps(off) == json.dumps(beats_for(vis, words, "9:16", 8, [], MOTION_TYPES, 1.0, None)), off
            assert "kinetic titles" not in (e / "motion" / off[0]["id"] / "brief.md").read_text(encoding="utf-8")
            stale = json.loads((e / "motion" / "beats.json").read_text(encoding="utf-8"))
            (e / "style.json").write_text(json.dumps({"aspect": "9:16", **on}), encoding="utf-8")
            for b in off:   # every clip passed, but the style has since turned kinetic titles on
                (e / "motion" / b["id"] / "gates.json").write_text(json.dumps({"pass": True}), encoding="utf-8")
            _, back = place(e)
            assert any(x.startswith(off[0]["id"]) and "kinetic titles'" in x for x in back), back
            shutil.rmtree(e / "motion")
            got = pick(e)
            assert [(b["type"], b["word"]) for b in got] == [("notes", "need"), ("side_by_side", "Before")], got
            assert all(b["beside_kinetic"] for b in got) and len(stale["beats"]) == 3
            assert "no counter, nothing counting up" in (e / "motion" / got[0]["id"] / "brief.md").read_text(encoding="utf-8")
            # the budget is counted over the cut's length, as plan.py probes it: a 30 s cut.mp4 gives 15 at 30 a minute
            # where the last word's end (15 s) gives 8
            import contextlib
            import io
            run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=108x192:d=30:r=30", "-pix_fmt", "yuv420p", e / "cut.mp4"])
            said = io.StringIO()
            with contextlib.redirect_stdout(said):
                pick(e)
            assert "budget: 15 in all" in said.getvalue(), said.getvalue()
        finally:
            if keep is None:
                os.environ.pop("AI_EDITOR_HOME", None)
            else:
                os.environ["AI_EDITOR_HOME"] = keep


def demo_order():
    """The order the graphics budget fills in beside kinetic titles (made-up takes): the user's real cards first, then
    the number beats (the hook always, over the budget when the real cards fill it), then the moving templates the
    clips would replace, in what is left; kinetic_beats.find, split_beats and plan.py budget_cards agree."""
    sys.path[:0] = [str(SKILL.parent / "style-edit" / "scripts"), str(PLUGIN / "lib")]
    import contextlib
    import io
    import kinetic_beats
    import plan

    def run(text, visuals, style, images=(), duration=None):
        """(number beats found, clips split_beats keeps, plan cards as (kind, word), stderr), each clip placed."""
        words = kinetic_beats.timed(text)
        duration = duration or words[-1]["end"] + 0.5
        sp = kinetic_split(style, words, visuals, images, duration)
        out = beats_for(visuals, words, images=images) if sp is None else \
            split_beats(visuals, words, images=images, split=sp, style=style)[0]
        vis = list(visuals)
        for b in out:
            vis[b["i"]] = placed_beat(visuals[b["i"]], b, f"images/motion-{b['id']}.mp4", 0.2, b["dur"] - 0.6)
        found = kinetic_beats.find(words, style, vis, images, duration)[0] if sp is not None else []
        meta = {"video": "cut.mp4", "width": 1080, "height": 1920, "fps": 30, "duration": duration}
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            p = plan.build(style, words, meta, images=images, visuals=[c.beat() for c in found] + vis)
        return found, [(b["type"], b["word"]) for b in out], [(plan.kind_of(c), c["trigger_word"]) for c in p["cards"]], err.getvalue()
    on = {"graphics": {"kinetic": True}, "captions": {"words_per_caption": 3}}   # 8 a minute
    short = "Our shop made 300 dollars this week. You need wax, wicks, jars and labels."
    lst = {"word": "need", "nth": 1, "kind": "anim", "type": "notes", "hold_s": 2.5}
    # a 5.6 s cut has room for 1 graphic: the hook's figure, not the list's template (it would be a clip): no clip
    found, clips, cards, err = run(short, [lst], on, duration=5.6)
    assert [c.cls for c in found] == ["hook"] and clips == [] and cards == [("kinetic_number", "300")], (found, clips, cards)
    assert "need@" in err, err
    # ... with a real screenshot there too: the screenshot and the hook both kept, over the budget of 1, and said so
    shot = [{"src": "images/a.png", "word": "labels.", "nth": 1}]
    found, clips, cards, err = run(short, [lst], on, shot, duration=5.6)
    assert [c.cls for c in found] == ["hook"] and "kept over the budget" in found[0].note, found
    assert clips == [] and cards == [("kinetic_number", "300"), ("shot", "labels.")], (clips, cards)
    assert "over the budget of 1" in err and "always kept" in err, err
    # ... nor any other template made for the edit, one no clip replaces (an icon burst or an arrow callout on the next
    # line, a likes counter on the hook's own figure): the hook keeps its title, with room or without (budget.later)
    for t, w in (("icon_burst", "need"), ("arrow_callout", "You"), ("likes", "300")):
        made = [{"word": w, "nth": 1, "kind": "anim", "type": t, "hold_s": 2.5, "props": {}}]
        for pm in (8, 30):
            found, clips, cards, err = run(short, made, {**on, "graphics": {"kinetic": True, "kinetic_per_min": pm}}, duration=9.0)
            assert [c.cls for c in found] == ["hook"] and clips == [] and cards == [("kinetic_number", "300")], (t, pm, found, cards)
            assert f"{t} card on '{w}' dropped" in err if pm == 30 else f"{w}@" in err, (t, pm, err)
    # a take of normal length with room for all: the same number beats, clips and plan as before the order was set
    take = ("Our bakery sold 340 loaves in one week. It was a long and happy week for every one of us at the shop. You "
            "need flour, water, salt and time. Before we kneaded every loaf by hand, now the mixer does it. We sold 900 "
            "rolls. Then we rested and went home to sleep for a while.")
    ba = {"word": "Before", "nth": 1, "kind": "anim", "type": "side_by_side", "hold_s": 3.0, "props": {"a": "hand", "b": "mixer"}}
    twelve = {**on, "graphics": {"kinetic": True, "kinetic_per_min": 12}}
    found, clips, cards, err = run(take, [lst, ba], twelve)
    assert [(c.type, c.s, c.e) for c in found] == [("kinetic_number", 0.86, 4.24), ("kinetic_number", 16.03, 18.45)], found
    assert clips == [("notes", "need"), ("side_by_side", "Before")], clips
    assert cards == [("kinetic_number", "340"), ("video_card", "need"), ("video_card", "Before"), ("kinetic_number", "900")], cards
    assert "left out" not in err and "dropped" not in err, err
    # kinetic titles off: upstream's clips and plan, whatever the length
    for dur in (5.6, None):
        found, clips, cards, err = run(short if dur else take, [lst] if dur else [lst, ba], {"captions": {"words_per_caption": 3}}, duration=dur)
        assert clips == ([("notes", "need")] if dur else [("notes", "need"), ("side_by_side", "Before")]), clips
        assert cards == [("video_card", w) for _, w in clips] and not found, cards


def demo_windows():
    """Beside kinetic titles, a clip's window and its plan: it never runs over a number line (a count the budget left
    out included), it ends kinetic_beats.GAP_S before a kept number beat as plan.py would cut it, and plan.py keeps the
    very clip pick built when the candidates outnumber the room (a made-up take)."""
    sys.path[:0] = [str(SKILL.parent / "style-edit" / "scripts"), str(PLUGIN / "lib")]
    import contextlib
    import io
    import kinetic_beats
    import plan
    words = kinetic_beats.timed("Our bakery sold 340 loaves in one week. It was a long and happy week for every one of us "
                                "at the shop. We bake rye, spelt, oat and wheat. We sold 900 rolls. Then we rested and went "
                                "home to sleep for a while.")
    rolls = next(w["start"] for w in words if w["text"] == "900")
    line = next(w["start"] for w in words if w["text"] == "We" and w["start"] > 9)   # "We sold 900 rolls."
    bake = {"word": "bake", "nth": 1, "kind": "anim", "type": "notes", "hold_s": 4.0}

    def planned(style, visuals, images=()):
        """split_beats' clips, placed as motion.py place would, then plan.build: (clips, plan cards, stderr)."""
        sp = kinetic_split(style, words, visuals, images)
        out = split_beats(visuals, words, images=images, split=sp, style=style)[0]
        vis = list(visuals)
        for b in out:
            vis[b["i"]] = placed_beat(visuals[b["i"]], b, f"images/motion-{b['id']}.mp4", 0.2, b["dur"] - 0.6)
        meta = {"video": "cut.mp4", "width": 1080, "height": 1920, "fps": 30, "duration": words[-1]["end"]}
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            p = plan.build(style, words, meta, images=images, visuals=kinetic_beats.beats(words, style, vis, images) + vis)
        return out, p["cards"], err.getvalue()
    # 8 a minute (2 here): the hook and the 900 fill it, the number beats before the moving template, so no clip
    eight = {"graphics": {"kinetic": True, "kinetic_per_min": 8}, "captions": {"words_per_caption": 3}}
    assert [k[2] for k in kinetic_split(eight, words, [bake])["kept"]] == ["340", "900"]
    out, cards, _ = planned(eight, [bake])
    assert out == [] and [plan.kind_of(c) for c in cards] == ["kinetic_number", "kinetic_number"], cards
    # a screenshot just after the 900's line leaves that count out (too close to the real card), so 12 a minute (3
    # here) has room for the list's clip; it still ends before the line that says the 900, and none of its WORDS is it
    twelve = {**eight, "graphics": {"kinetic": True, "kinetic_per_min": 12}}
    shot = [{"src": "images/r.png", "word": "rested", "nth": 1}]
    sp = kinetic_split(twelve, words, [bake], shot)
    assert [k[2] for k in sp["kept"]] == ["340"] and rolls in sp["said"] and sp["allowance"] == 3, sp
    out, cards, _ = planned(twelve, [bake], shot)
    assert [b["word"] for b in out] == ["bake"] and out[0]["start"] + out[0]["dur"] <= line - CARD_LEAD_S + 1e-6, out
    assert not any(w["w"] in ("900", "rolls.") for w in out[0]["words"]), out[0]["words"]
    vc = next(c for c in cards if plan.motion_clip(c))
    assert vc["end"] < rolls, vc
    # ... a stale beats.json (picked before the titles took that line) runs over it: place keeps the template
    sents = sentences(words)
    stale = {**out[0], "dur": 4.0}
    assert "runs over a number" in (split_veto(stale, sp, sents, split_types(MOTION_TYPES)) or ""), stale
    # 10 a minute (3): the 900 is kept; the clip ends GAP_S before its title, so plan.py space_kinetic leaves it whole
    # and its motion finishes on screen
    ten = {**eight, "graphics": {"kinetic": True, "kinetic_per_min": 10}}
    out, cards, _ = planned(ten, [bake])
    k900 = next(c for c in cards if c.get("trigger_word") == "900")
    vc = next(c for c in cards if plan.motion_clip(c))
    assert abs(out[0]["start"] + out[0]["dur"] - (k900["start"] - kinetic_beats.GAP_S)) < 0.011, (out, k900)
    assert abs(vc["end"] - (out[0]["start"] + out[0]["dur"])) < 1e-6 and vc["end"] <= k900["start"] - kinetic_beats.GAP_S, (vc, k900)
    # candidates over the room: one screenshot, a list and a before and after at 10 a minute (3, the hook included):
    # pick builds one, and plan.py keeps that very clip (ranked as its template), the list's template left out
    tb = kinetic_beats.timed("Our bakery sold 340 loaves in one week. It was a long and happy week for every one of us "
                             "at the shop. You need flour, water, salt and time. Before we kneaded every loaf by hand, now "
                             "the mixer does it. We love what we do here every day.")
    lst = {"word": "need", "nth": 1, "kind": "anim", "type": "notes", "hold_s": 2.5}
    ba = {"word": "Before", "nth": 1, "kind": "anim", "type": "side_by_side", "hold_s": 3.0, "props": {"a": "hand", "b": "mixer"}}
    shot = [{"src": "images/a.png", "word": "every", "nth": 1}]
    words = tb
    out, cards, err = planned(ten, [lst, ba], shot)
    assert [b["word"] for b in out] == ["Before"], out
    assert [plan.motion_clip(c) for c in cards if plan.motion_clip(c)] == [out[0]["id"]] and "motion clip" not in err, (cards, err)
    assert [plan.kind_of(c) for c in cards] == ["kinetic_number", "shot", "video_card"], [plan.kind_of(c) for c in cards]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("edit")
    p.add_argument("--max", type=int, default=8)
    sub.add_parser("check").add_argument("clip")
    sub.add_parser("place").add_argument("edit")
    sub.add_parser("status").add_argument("edit")
    s = sub.add_parser("strips")
    s.add_argument("video")
    s.add_argument("--at", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--fps", type=float, default=10)
    s.add_argument("--before", type=float, default=0.4)
    s.add_argument("--after", type=float, default=1.1)
    s.add_argument("--safe", action="store_true")
    n = sub.add_parser("note")
    n.add_argument("edit")
    n.add_argument("text")
    n.add_argument("--at", type=float)
    n.add_argument("--clip")
    sv = sub.add_parser("save")
    sv.add_argument("edit")
    sv.add_argument("--clip")
    lb = sub.add_parser("library")
    lb.add_argument("action", nargs="?", default="list", choices=["list", "archive", "unarchive", "use"])
    lb.add_argument("id", nargs="?")
    sub.add_parser("demo")
    a = ap.parse_args()
    if a.cmd == "pick":
        pick(a.edit, a.max)
    elif a.cmd == "check":
        sys.exit(check(a.clip))
    elif a.cmd == "place":
        place(a.edit)
    elif a.cmd == "status":
        status(a.edit)
    elif a.cmd == "note":
        note(a.edit, a.text, a.at, a.clip)
    elif a.cmd == "save":
        save(a.edit, a.clip)
    elif a.cmd == "library":
        if a.action == "list":
            for e in lib_entries():
                print(f"{e['id']:<26} {e['kind']:<12} {'archived' if e.get('archived') else 'use again' if e.get('use_next') else '':<9} \"{e['line'][:60]}\"")
        else:
            lib_set(a.id, archived={"archive": True, "unarchive": False}.get(a.action), use=True if a.action == "use" else None)
    elif a.cmd == "strips":
        strips(a.video, [float(x) for x in a.at.split(",")], a.out, a.before, a.after, a.fps, a.safe)
    else:
        demo()


if __name__ == "__main__":
    main()
