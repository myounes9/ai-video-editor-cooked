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
| `step_build` | yes | a tracker of 2-4 slots in fixed columns that returns at several beats with the same slots and identity: an empty slot is a smoked glass well with its number, a filled one gets its label pulled on by the marker and handed to the foil (gold edge), a question slot is a dashed well with a "?"; a slot popping in makes room first | `slots: [{label?, state: "empty" \| "filled" \| "question" \| "off", at?}]` (2-4), `id?`, `join_in?`, `join_out?`, `out_at?`, `band?`, `hide_captions?` |
| `stat_stack` | yes | 2-4 stats landing one by one in a compact row or stack (figure on the marker, then foil; label beside it, on its baseline, wrapping onto two lines that span the figure's caps), in the part of the band a capture beside it leaves free | `stats: [{num, label?, at, label_at?}]` (2-4), `layout?: "row" \| "stack"`, `beside?: [x, y, w, h]`, `out_at?`, `band?`, `hide_captions?` |
| `kinetic_title` | planned | a key-word title for a beat with no number: 1-3 lines, each word on its time, key words in the key colour | `lines: [{words: [{text, at, key?}]}]` |
| `cta_follow` | planned | a handle and a follow button that presses on "follow", an optional avatar circle | `handle`, `at`, `follow_at`, `avatar?` (an image file) |

A planned format is registered but stops the render with its name until its branch builds it.

### A tracker over several beats (`step_build`)

One visuals.json beat per moment, every beat with the same `id` and the same slots (labels included); only the states
and words change. A slot with a word changes on it: an `empty` or `question` slot pops in there, a `filled` one fills
there. A slot with no word is already so when the beat comes up; `off` is not up yet (a later beat adds it) but keeps
its column, so every beat lays out the same.

```json
{"word": "two", "kind": "anim", "type": "step_build", "props": {"id": "shops", "slots": [
  {"label": "bakery", "state": "empty", "word": "two"}, {"label": "catering", "state": "empty", "word": "two"}, {"state": "off"}]}},
{"word": "first", "kind": "anim", "type": "step_build", "props": {"id": "shops", "slots": [
  {"label": "bakery", "state": "filled", "word": "bakery"}, {"label": "catering", "state": "empty"}, {"state": "off"}]}},
{"word": "next", "kind": "anim", "type": "step_build", "props": {"id": "shops", "slots": [
  {"label": "bakery", "state": "filled"}, {"label": "catering", "state": "filled"}, {"state": "question", "word": "next"}]}}
```

A beat that comes back sweeps in left to right with its earlier fills already in foil. When the next beat of the same
tracker follows within 1 s, plan.py joins them: the first holds until the second starts (`join_out`: no sweep out, no
push; a fill still on its marker hands it to the foil just before) and the second carries on from it (`join_in`), so
one tracker stays on screen.

### Beside a capture (`stat_stack`)

A stat_stack may share its beat with a real capture of the same numbers (a dashboard screenshot). plan.py gives it
that card's box as `beside` (the card up with it longest; a `beside` in props wins) and the stats keep 24 px clear of
it, in the biggest part of the band it leaves free (above, below, left or right), as a row or a stack, whichever fits
biggest unless `layout` says.

## Building a format (for the renderer)

Copy `NumberChain.tsx`: `useFaces()` (fonts, null until loaded), `useClock()` (the card's seconds), a `solve()` in
`useMemo` that fits the type once with `fitDown` against `layoutBox(w, h, p.band)`, then a pure function of `t`
inside `<Lockup>` (scrim, push, sweep) built from the primitives: `MarkerReveal` + `pullOn` / `pullOff` + `Behind`
(the marker and its hand-off to the foil), `FigureGlyphs` (paint `ink`, `white` or `gold`, with `FoilDefs`),
`Run` + `LineMask` + `stagger` (a line's reveal), `Odometer` + `counter` (a count from 40%), `Arrow`,
`settleAt` + `Scaled`, `exitAt` and `labelStart` (the hold and label rules). `Lockup` takes `out = Infinity` (it never
leaves: the next beat takes over) and `joined` (the scrim is already up) for a lockup that spans beats. No GSAP timeline state, no
Math.random, no clock; no blurred box-shadow on a moving layer, no transform once settled, no opacity on a scaled
layer. Add made-up cases to `test/kinetic/<type>.json` (one with `"determinism": true`), run
`node test/templates.mjs <public> test/kinetic <out>` and `node test/determinism.mjs <out> --only kinetic`, and look
at the stills. Budget: about +0.05 s a frame per card up at 1080x1920 (number_chain measured +0.03, stat_stack +0.01,
step_build under +0.01).
