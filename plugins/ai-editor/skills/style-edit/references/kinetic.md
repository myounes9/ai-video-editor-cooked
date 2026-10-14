# Kinetic titles (opt-in)

Key figures and key words set over the footage on their spoken words: a figure pulled on by a highlighter
marker, chains of figures, a goal bar, a step tracker, a short key-word title, a follow card. They are words over
the footage, so the default style never draws them (PRINCIPLES.md "Looking real"): a style opts in with
`"graphics": {"kinetic": true}` in style.json or the user's taste. Without it plan.py skips these beats with a
warning, and check.py and ai_tells.py treat a kinetic card in a plan as a text card (FAIL / type-card).

When one fits: a number or a short claim the speaker says and no page shows (their own results, a count, a goal,
where they are in a plan). When a real page, post or product shows it, show that instead (visuals.md).

Renderer: `remotion/src/kinetic/` (one file per format, the shared design system in `tokens.ts`, `type.ts`,
`time.ts`, `fit.ts`, `primitives.tsx`). Each format is a floating template (Templates.tsx): no card under it.

## Every kinetic beat

```json
{"word": "three", "kind": "anim", "type": "number_chain", "hold_s": 7,
 "props": {"items": [{"num": "340", "word": "three", "label": "flyers", "label_word": "flyers"},
                     {"num": "6", "word": "six", "label": "tastings", "label_word": "tastings"},
                     {"num": "1", "word": "one", "label": "cafe", "label_word": "cafe"}]}}
```

- **Times**: every time in props is seconds after the card starts. Give spoken words and plan.py fills the times:
  `word` -> `at`, and for a kinetic card any `<part>_word` -> `<part>_at` and `word_<part>` -> `at_<part>`
  (`label_word` -> `label_at`, `word_goal` -> `at_goal`), each the first time it is said once the card is up
  (`nth` picks a later one). The card starts 0.1 s before its own `word`.
- **Figures** are strings exactly as drawn: `"340"`, `"€4.5K"`, `"40%"`, `"1,200"`. A currency sign is set at
  0.6x and a % at 0.56x, cap-aligned; K, M and B stay full size. A bare number is read too, but `"40%"` keeps the
  check of the %. check.py plan reads every figure against what the speaker says (numbers.py), `target` included.
- **Placement**: plan.py gives the card the whole frame (`box` [0, 0, 100, 100]) and its own lane `kinetic` (it may
  share the frame with a capture). The format fits itself to `band` ([top, bottom] % of the frame height): over the
  hair and forehead, under the Reels header (never above 8%), above the eyes. Unset: [8.6, 26.2], a close talking
  head. Phase 3 fills it from face.json.
- **Captions**: the word captions fade out while a kinetic card is up and back right after it
  (`hide_captions`, default true; false keeps them).
- **Hold**: a lockup holds at least 1.2 s after its last landing and leaves in time to be gone when the card ends
  (`hold_s`, or the next speech, wins over the hold). `out_at` (optional) asks it to stay until then.
- **Labels** land no earlier than their figure + 0.15 s. Keep them to one or two words; a long one steps down in
  size, then wraps onto two lines, never closer than 40 px to the next.
- Not with the split layout (plan.py drops them there: they float over the full-frame speaker).

## The look (tokens.ts)

Anton for figures, Oswald 500 for lines and labels, on one grid (72 px side margins at 1080, scaled). The key
figure lands as ink on a flat #FFD400 marker pulled on like a highlighter (its leading edge leans 10° and
straightens) with a 1.06 -> 1 settle over 6 frames. Every key figure stays key-coloured after its moment: it hands
off to the foil (a restrained gold gradient on the glyphs' own caps, a quiet bevel, a bronze hairline, one warm
sheen as it lands), never to white. Lines rise through a mask per character with a short vertical blur trail. A
held lockup pushes 1.5%; it leaves in one feathered sweep, left to right. Counters start at 40% of their value
(never a 0) and their landing hit fires on the first frame the value reads final.

## Formats

| type | built | shows | props |
|---|---|---|---|
| `number_chain` | yes | 2-4 figures that lead one to the next, each on its word; a connector draws just before the next lands; earlier figures stay, in foil; fixed columns, equal connectors | `items: [{num, label?, at, label_at?}]`, `out_at?`, `band?`, `hide_captions?` |
| `kinetic_number` | planned | one figure with a sub-line of words; variants `hook` (default), `counter` (counts from 40% on its word), `tally` (up to ~30 tiles fill while it counts), `stamp` (a word like SOLD OUT stamps in) | `num`, `at`, `variant?`, `sub?: [{text, at, key?}]`, `stamp?: {text, at}` |
| `goal_bar` | planned | the goal layout without a panel: the % on the left with a small cap-aligned %, the target on the same baseline under a small GOAL label; a pill track with its remainder, a fill with a glow band and a landing flare, a target marker that pops on the target and rings on "goal" | `pct`, `target`, `at_pct`, `at_target`, `at_goal?` |
| `step_build` | planned | a tracker of 2-4 slots (`empty`, `filled`, `question`) that returns at several beats with the same slots and identity | `slots: [{label, at, state}]`, `id?` |
| `stat_stack` | planned | 2-4 stats landing one by one in a compact stack or row, beside a real screenshot card | `stats: [{num, label, at}]`, `layout?: "stack" \| "row"` |
| `kinetic_title` | yes | a key-word title for a beat with no number: 1-3 lines, each word on its time; a line with a key word is set in Anton, its key words pulled on by the marker (a run of key words shares one marker) and handed to the foil when the next run comes; a line with none is a supporting line in Oswald at 0.4x; centred on the grid | `lines: [{words: [{text, at, key?}]}]` (1-3 lines, one word per entry), `out_at?`, `band?`, `hide_captions?` |
| `cta_follow` | yes | a handle over a follow button, beside an optional avatar circle with a key-colour ring; the button wipes in as an empty well and on "follow" presses, the marker pulled across it turns it to FOLLOWING with a check, and two rings leave it | `handle` (no spaces; an "@" is added), `at`, `follow_at`, `avatar?` (an image file, "images/..."), `button?` ("Follow"), `pressed?` ("Following"), `out_at?`, `band?`, `hide_captions?` |

A planned format is registered but stops the render with its name until its branch builds it.

**kinetic_title**: give each title word as its own entry and let plan.py time it. A word's `word` (else its own
`text`) is matched in reading order from the card's start, so a repeated word lands on its own later saying; a
word given an `at` and no `word` keeps it. Mark the one to three words that carry the beat `"key": true`; keep the
other lines short (they set small). Not for a number: use `kinetic_number` or `number_chain`.

```json
{"word": "this", "kind": "anim", "type": "kinetic_title", "hold_s": 3,
 "props": {"lines": [{"words": [{"text": "this"}, {"text": "is"}, {"text": "how"}]}, {"words": [{"text": "sourdough", "key": true}]},
                     {"words": [{"text": "we"}, {"text": "bake"}, {"text": "by"}, {"text": "hand"}]}]}}
```

**cta_follow**: on the spoken ask ("give me a follow"). `follow_word` gives `follow_at`. Use the creator's real
handle and, when they have one, their profile picture as `avatar`; never a made-up account.

```json
{"word": "give", "kind": "anim", "type": "cta_follow", "hold_s": 4,
 "props": {"handle": "@yourhandle", "follow_word": "follow", "avatar": "images/avatar.jpg"}}
```

## Building a format (for the renderer)

Copy `NumberChain.tsx`: `useFaces()` (fonts, null until loaded), `useClock()` (the card's seconds), a `solve()` in
`useMemo` that fits the type once with `fitDown` against `layoutBox(w, h, p.band)`, then a pure function of `t`
inside `<Lockup>` (scrim, push, sweep) built from the primitives: `MarkerReveal` + `pullOn` / `pullOff` + `Behind`
(the marker and its hand-off to the foil), `FigureGlyphs` (paint `ink`, `white` or `gold`, with `FoilDefs`),
`Run` + `LineMask` + `stagger` (a line's reveal), `Odometer` + `counter` (a count from 40%), `Arrow`,
`settleAt` + `Scaled`, `exitAt` and `labelStart` (the hold and label rules). No GSAP timeline state, no
Math.random, no clock; no blurred box-shadow on a moving layer, no transform once settled, no opacity on a scaled
layer. Add made-up cases to `test/kinetic/<type>.json` (one with `"determinism": true`), run
`node test/templates.mjs <public> test/kinetic <out>` and `node test/determinism.mjs <out> --only kinetic`, and look
at the stills. Budget: about +0.05 s a frame per card up at 1080x1920 (number_chain measured +0.03).
