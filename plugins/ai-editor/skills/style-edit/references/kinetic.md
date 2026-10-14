# Kinetic titles (opt-in)

Key figures and key words set over the footage on their spoken words: a figure pulled on by a highlighter
marker, chains of figures, a goal bar, a step tracker, a short key-word title, a follow card. They are words over
the footage, so the default style never draws them (PRINCIPLES.md "Looking real"): a style opts in with
`"graphics": {"kinetic": true}` in style.json or the user's taste, or a rule in words that asks for them ("From the
user's rules" below). Without it plan.py skips these beats with a warning, and check.py and ai_tells.py treat a
kinetic card in a plan as a text card (FAIL / type-card).

When one fits: a number or a short claim the speaker says and no page shows (their own results, a count, a goal,
where they are in a plan). When a real page, post or product shows it, show that instead (visuals.md). The number
beats are placed automatically ("Automatic beats" below).

Renderer: `remotion/src/kinetic/` (one file per format, the shared design system in `tokens.ts`, `type.ts`,
`time.ts`, `fit.ts`, `primitives.tsx`). Each format is a floating template (Templates.tsx): no card under it.

## Automatic beats (kinetic_beats.py)

With the opt-in on, nobody writes the number beats: plan.py runs `scripts/kinetic_beats.py` before it reads
visuals.json, and it adds them there from the cut's words (`"auto": "kinetic"` on each). Only number beats:
`kinetic_title` and `cta_follow` are never placed automatically, and the word captions carry every other line.

- **Candidates**, from numbers.py spans over the punctuated words, by sentence and clause: the **hook** (the first
  figure in the first sentence that is more than filler, or in its first 3 s, never past 6 s: money, or a count or a
  percent of a plural thing said after it, "fifty loaves", "forty percent of buyers"; its sub-line a duration said
  there, "in 3.5 weeks"); a **chain** (2-4 counts, each in its own clause and smaller than the last, within 8 s: a
  funnel; a count in a sentence of its own needs a funnel cue, a verb like got, sent, booked, signed, or "to get
  there", "out of", "of those": "We have 80 members. We also have 12 coaches." is a list); a **goal** (a percent with
  "goal", "target" or "of the way" and a scaled figure in its sentence, up on the first of its words); a **stat run**
  (2-4 labelled figures in one sentence that count different things, a `stat_stack`); a **counter** (a count of 50 or
  more, with a stamp when rejected, ignored, failed, ghosted, lost ... follows in the sentence); a **tally** (5-30 of a
  plural thing); a lone **money** figure; a lone percent or a count of 31-49; a **step tracker** ("two main kinds of
  bread", "three layers", then "one is", "the other is", "layer two is", "now for step three," ...; or "step one, step
  two" with no count), one beat for the count, one per item filled on its label, and a "?" slot on "another <the same
  noun>".
  Left out, as no count of things: a duration (only a sub-line), a sign or a part said with it ("minus five"; "half a
  million" is 500K), a year ("2019", "back in twenty nineteen"), a name's number ("Planner 3", "GPT-4", "page 42", "day
  30"), an ordinal ("step one"), a date ("June 21"), a clock time or an address ("at five", "at 221"), a phone number
  or an ID (a leading 0, 7+ digits), two numbers said back to back ("twenty twenty-three", "three ninety-nine"), a range
  or a ratio ("fifty to sixty", "between fifty and sixty", "one in ten"; of "from 200 to 12K" only the result), a
  measure ("220 degrees", "500 grams", "fifty times"), "a hundred percent sure", and a lone "one" ("the best one",
  "one of"), which only ends a chain after its verb ("and signed one."). A tracker item with no plain noun takes the
  verb said for it ("step one is quick: you weigh the flour" is WEIGH; "Planner Pro, Oven Mate and Timer Box mix it"
  is MIX); one with neither is left out with its tracker.
- **Words**: each label is 1-2 of the speaker's own words next to the number (the noun after it, its currency word and
  an "of" passed over; else the verb before it), as said, set in capitals by the renderer; never a number word or a
  date. A chain's figure with only a verb before it is drawn bare ("1", not "1 SIGN"). A figure is written from what
  was said: "4.5k dollars" -> "$4.5K", "three hundred and forty" -> "340", K/M/B only when one was said and it reads as
  said ("two thousand three hundred and forty-five" is "2,345", never "2.345K").
  A chain or tracker whose labels would not fit (check.py `kinetic_fit`) keeps one word each, else it is left out.
- **Ranking**: hook > chain = goal > stat run > counter > money > lone figure = tally > tracker beats (an item's
  fill before the count's empty wells, which are kept only with a fill), plus clarity (labels, a stamp, more items). A
  tracker of sources, steps, ways, stages, phases, layers ... (the speech enumerating what the video is about) ranks
  with a stat run.
- **Density** (`graphics.kinetic_per_min`, default 8; the count is `budget.py`'s, "How many" below): at most rate x
  minutes graphics in all, a tracker's beats one graphic; the real cards already there (images.json, visuals.json
  captures, posts, logos, titles, ctas, kinetic beats written by hand) count first, the strongest candidates take the
  rest, and the hook is kept even past it. Each beat carries its `strength` (its score, a tracker's beats sharing their
  best) and the hook `"hook": true`, so plan.py `budget_cards` keeps the same ones. The style page's `cards.per_min`
  does not cap it; `cards.on` false places none. 1 s of plain footage between any two cards, kinetic or real (the next
  beat of the same tracker joins instead); a kinetic card never covers a real one, except a `stat_stack` beside the
  capture of its figures. Each card holds 2 s after its last word, cut to leave the gap, never under 1.3 s; a real card
  before one ends 1 s before it when it still holds 2 s (plan.py `space_kinetic`). A strong beat (a counter, stat run,
  chain or goal) blocked only by the hold of the kinetic card before it, said 1 s or more after that card's last word,
  bridges from it (that card holds until it starts, plan.py `bridge_kinetic`), two cards and 12 s at the most: the
  strongest beats win, not the first come. No card ends on the first words of a number said after it: it ends as that
  number's caption page starts (else plan.py holds it over the whole number).
- **Kept until something changes**: `kinetic.auto.json` holds a fingerprint of the cut's words, the real cards and the
  rate. While it matches, plan.py keeps the beats as they are, so a review note's change to one (`plan.py beat`)
  survives the next plan; when any changes they are found again, and what the notes did to them is laid on again: a
  beat a note removed stays out, a field a note changed (a hold, a label) keeps its value (`"removed"` and `"edits"`
  there, matched by the beat's type, word and figures; delete the file to start over). A beat with its `"auto"` mark
  taken off is hand-written from then on. `graphics.kinetic_auto: false` (hand-written beats only) or
  `graphics.kinetic` off: plan.py takes the automatic beats out of visuals.json (`kinetic_beats.clear`).
- **By hand**: `kinetic_beats.py find edits/NAME` lists every candidate, kept or why not; `write edits/NAME [--force]`
  writes them now; `words FILE.json [--per-min N] [--json]` reads any word-timed transcript (words.json, a
  transcriber's `{"words": [...]}`). `route.py beats` marks the sentences that get one `[kinetic]`: give those lines
  no other card unless a real page shows the figure.

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
  share the frame with a capture). The format fits itself to `band` ([top, bottom] % of the frame height), which
  plan.py sets from face.json over the card's own time (`face_band`): from 8.6% (under the Reels header) down to 3%
  above the highest brow line while the card is up (0.37 down face.py's head box, the head as the zooms draw it), at
  most 24% tall (a head low in a wide shot takes the band down with it), never past 50%. No head while it is up: the
  take's median head; none at all: [8.6, 26.2]. Under 7% of room above the brows (a head high in the frame), the card
  is dropped with a warning rather than set on the eyes. A `band` on the beat wins. check.py plan FAILs a band that
  reaches the eyes and WARNs one past the brows. A band that is not [top, bottom] with top under bottom, inside 0-50%,
  stops the render. Over a full-frame scene plan.py passes the scene's picture as `beside` and the band stops 24 px above it
  (when that leaves 7% of the frame; else check.py plan WARNs that the card covers the picture).
- **Captions**: the word captions fade out only while a number card is up (every format but `kinetic_title` and
  `cta_follow`) and back right after it (`hide_captions`, default true for those, false for the two; a card's own
  value wins). Two
  cards under 0.6 s apart keep them hidden in between. Everywhere else the word captions carry the line. Never half a
  number: a card whose end would hide the first page of a number said after it ("a hundred and" hidden, "sixty-four"
  shown reads 64) ends as that page starts, when it still holds 1.3 s after its last part, else holds over the whole
  number (plan.py `whole_numbers`); check.py plan FAILs a plan that still splits one.
- **Hold**: a lockup holds at least 1.2 s after its last landing and leaves in time to be gone when the card ends
  (`hold_s`, or the next speech, wins over the hold). `out_at` (optional) asks it to stay until then. A kinetic card
  that ends under 1 s before the next kinetic card or scene holds until it (plan.py `bridge_kinetic`), so the captions
  never flash back for a word. A card whose first landing comes after it has gone stops the render (raise `hold_s`).
- **Zooms**: punches happen on the plain footage between cards. A punch with an edge under a card is cut back to end
  before the card comes in, or to start once it has gone (plan.py `punch_between`), when 0.8 s of it is left there;
  else it eases under the card as a soft push (0.8 s each way), and a punch beside such a push gives way to it rather
  than joining it. An edge that would land in the second of footage between a scene and the kinetic card after it
  goes under the scene instead (one move there, not two). Two punches on plain footage join into one hold up to 5 s
  (only with kinetic cards in the plan; every other style keeps upstream's rule). No zoom cuts under a kinetic card's hold. A zoom up with one grows from the head's top, never from
  the chin (plan.py `clear_chin`), so the head holds its place.
- **Labels** land no earlier than their figure + 0.15 s. Keep them to one or two short words: they stay phone-readable
  (48 px, 44 at the least), wrapping onto two lines before they shrink, never closer than 40 px to the next. A
  number_chain whose labels or figures cannot fit so across the grid stops the render; check.py plan FAILs it first
  (an estimate, WARN near the limit): make it a `stat_stack` (`columns`), or shorten the labels.
- Not with the split or board layout (plan.py drops them there: they float over the full-frame speaker). With
  them on, a picture asking for the split panel (`"layout": "split"`) is a full-frame scene instead, unless the split
  layout was set by hand (`--layout split` or style.json `layout.mode`). A style whose
  creator is off screen (her pictures become scenes) keeps them over the footage. A visuals.json `title` or `cta` owns
  the band: a kinetic card up when one lands ends there, and one that would start under it is dropped (plan.py
  `under_titles`).

## How many (the graphics budget)

One count for every graphic a viewer sees, kinetic and real-source together (captures, posts, logos):
`graphics.kinetic_per_min` a minute (default 8; it wins over the style page's `cards.per_min`, and `cards.on` false
still means none). `lib/ai_editor/budget.py` holds it, so the beat finder and plan.py pick against the same number:
`allowance(style, duration_s)`, `remaining(style, duration_s, taken)`, `pick(items, n)`. plan.py `budget_cards` keeps
the strongest: the hook always (a beat with `"hook": true`, else the first graphic in the opening 3 s), then by each
beat's `strength` (0-1; a real source with none counts 0.75, a kinetic beat 0.5), a beat that would leave under 1 s
of plain footage beside one already kept counting 0.2 less, so the picks spread out (the beats of one tracker
are one graphic coming back: counted once, kept or left out together, never penalised beside each other). Each card
left out is named on
stderr. plan.json records `graphics_budget`; style_check.py and quality.py compare the cards a minute with it, and do
not flag a kinetic kind the copied creator hardly uses, or a soft push under a kinetic card, as hers to match.

## From the user's rules (settings)

- `graphics.kinetic` (true: the style opts in) and `graphics.kinetic_per_min` (default 8: graphics a minute in total,
  captures and screenshots included). Taste settings like any other: taste.json, a style's `style.overrides.json`,
  or this video's own.
- A rule in words sets them, at its own scope (`taste.py` `settings_for`, laid in by `load_json`): "add motion
  graphics", "kinetic number titles", "the hook's number gets a graphic", "a progress bar for the goal" turn
  `graphics.kinetic` on; a no on either side of the words turns it off ("no motion graphics", "do not add motion
  graphics", "never use kinetic titles", "skip the progress bars", "motion graphics: none", "I hate kinetic text");
  "fewer / more motion graphics" ("too many", "tone them down") sets `kinetic_per_min` 6 / 10, "N graphics a minute"
  and "no more than N a minute" set N. A note that is unclear (two negations, "don't let the motion graphics cover my
  face") sets nothing and stays a rule in words. A value saved in the same scope wins over the words. `taste.py map "<note>"`
  prints what a note sets; `taste.py report` and the style's skill show it on the rule ("from its words", "Sets:").
- Emphasis captions (fork, opt-in): `captions.emphasis_scale` (about 1.1; 1 marks in colour only) turns them on.
  plan.py `mark_emph` then marks every spoken number, all of its words (numbers.py on the punctuated words, so a
  number split over two pages is marked on both; a lone "one" is not a figure), and the take's key words
  (`key_words`: a name, else the word held longest for its length; one a sentence, 2.5 s apart; none on a page that
  has a number), on pages of any length, two words included. Captions.tsx draws them in `captions.emphasis_color`
  (#FFD400 for this look), one weight heavier, `emphasis_scale` bigger through a transform: the page keeps its size
  and its line breaks (the fit leaves the room), and a stressed word keeps its colour while it is said. "Key words in
  yellow, slightly bigger" sets #FFD400 and 1.1; "never highlight key words in the captions" sets `emphasis_scale`
  null (off). Only a number's own words are marked ("three and a half": THREE, HALF), a two-word name whole ("Market
  Hall,"), and no key word in a sentence that says a number (its number is marked). An older style.json that still
  holds upstream's retired `emphasis_scale` turns these on: remove it to keep upstream's emphasis.
- When a learned rule changes one of these, `review.py learn` and `taste.py add` print `REPLAN:`: run what it names
  (plan.py, whose beat finder places the kinetic beats again, and which marks the emphasis), then the stills and the
  render, so the note shows on this video too.

## For the AI steps (visual-prep, template-filler, overlays)

- The beat finder places the kinetic beats, on number beats only: the hook figure, stats, a chain, a counter, tally
  or stamp, a goal, a money figure, and a step tracker where the speech counts sources or steps. Keep them as written:
  never drop, retime or reword one to fit another card; place the other cards around them.
- Never a figure or a label the speaker did not say: figures are the spoken numbers (numbers.py), labels the
  transcript's own words. check.py plan FAILs an unsaid number.
- Never add a `kinetic_title` (or any kinetic card) on your own: a line with no number keeps the word captions, which
  hide only while a number card is up. A kinetic card the user asks for in a note is the exception.
- Count every card you add against `graphics.kinetic_per_min`: the kinetic beats, route.py's `want` lines and your
  captures together stay at about that many a minute, with at least 1 s of plain footage between two cards (punch
  zooms land there). Over it, leave out your weakest card, never the hook's figure.
- Not opted in (`graphics.kinetic` unset or false): no kinetic beat at all.

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
| `kinetic_number` | yes | one figure, centred on the grid, with an optional sub-line of words under it, each on its word (key words in foil); variants `hook` (default: the figure on its marker), `counter` (counts from 40% to land on `land_at`), `tally` (a counter beside 1-30 tiles that fill as the count passes each one's share, once the figure has landed), `stamp` (a word like SOLD OUT stamps across the figure's foot on its word, covering at most its bottom fifth, which hands the figure to the foil); any variant may carry a `stamp`; a long sub-line wraps onto two lines | `num`, `at`, `variant?`, `land_at?` (counter, tally; else `at` + 0.35 s), `sub?: [{text, at, key?}]`, `stamp?: {text, at}`, `tiles?` (tally, 1-30; else the value with its K/M counted, capped at 30), `out_at?`, `band?`, `hide_captions?` |
| `goal_bar` | yes | where the speaker is on the way to a goal, without a panel: the % on the left as the key figure on its marker, counting from 40% to land on its count word (its % at 0.56x, cap-aligned); the target in foil on the same baseline at the grid's right edge under a small GOAL label (the label's cap top on the figure's); under both a pill track the width of the grid whose remainder always shows, its fill running with the count, a glow band and a 6-frame flare on the landing; a target marker on the track's end pops on the target's word and sends two rings on "goal"; on a wide frame the module keeps the vertical grid's width, centred | `pct` ("50%" or 50), `target` ("20K", "€20K"), `at_pct` (or `at`), `count_at?` (when the count reads final; default `at_pct` + 0.3), `at_target`, `at_goal?`, `label?` ("GOAL"), `out_at?`, `band?`, `hide_captions?` |
| `step_build` | yes | a tracker of 2-4 slots in fixed columns that returns at several beats with the same slots and identity: an empty slot is a smoked glass well with its number, a filled one gets its label pulled on by the marker and handed to the foil (gold edge), a question slot is a dashed well with a "?"; a slot popping in makes room first; every label inside its well (wrapped and smaller for four long ones; a word too wide for its well stops the render, check.py plan FAILs it first) | `slots: [{label?, state: "empty" \| "filled" \| "question" \| "off", at?}]` (2-4), `id?`, `join_in?`, `join_out?`, `out_at?`, `band?`, `hide_captions?` |
| `stat_stack` | yes | 2-4 stats landing one by one (figure on the marker, then foil) in a compact row or stack (label beside it, on its baseline, wrapping onto two lines that span the figure's caps) or in columns (label under it, at a readable size), in the part of the band a capture beside it leaves free; the layout with the biggest figures wins | `stats: [{num, label?, at, label_at?}]` (2-4), `layout?: "row" \| "stack" \| "columns"`, `beside?: [x, y, w, h]`, `out_at?`, `band?`, `hide_captions?` |
| `kinetic_title` | yes | a key-word title for a beat with no number: 1-3 lines, each word on its time; a line with a key word is set in Anton, its key words pulled on by the marker (a run of key words shares one marker) and handed to the foil when the next run comes; a line with none is a supporting line in Oswald at 0.4x; centred on the grid | `lines: [{words: [{text, at, key?}]}]` (1-3 lines, one word per entry), `out_at?`, `band?`, `hide_captions?` |
| `cta_follow` | yes | a handle over a follow button, beside an optional avatar circle with a key-colour ring; the handle rises just before its word and the button wipes in as an empty well; on "follow" it presses, the marker pulled across it turns it to FOLLOWING with a check, and two rings leave it | `handle` (no spaces; an "@" is added), `at`, `follow_at`, `avatar?` (an image file, "images/..."), `button?` ("Follow"), `pressed?` ("Following"), `out_at?`, `band?`, `hide_captions?` |

A goal beat in visuals.json: `{"word": "forty", "kind": "anim", "type": "goal_bar", "hold_s": 5, "props": {"pct": "40%",
"word_pct": "forty", "count_word": "percent", "target": "20K", "word_target": "20k", "word_goal": "goal"}}` (plan.py
turns `word_pct`, `count_word`, `word_target` and `word_goal` into `at_pct`, `count_at`, `at_target` and `at_goal`).

A `kinetic_number` beat, the spoken words filled in by plan.py (`word` -> `at`, `land_word` -> `land_at`; the
sub-line's and the stamp's `word` -> `at`):

```json
{"word": "two", "kind": "anim", "type": "kinetic_number", "hold_s": 4,
 "props": {"num": "200", "variant": "counter", "word": "two", "land_word": "hundred",
           "sub": [{"text": "croissants", "word": "croissants"}], "stamp": {"text": "sold out", "word": "sold"}}}
```

Keep the sub-line to a few words (a long one wraps onto two lines under the figure); the stamp's word is said, never added.

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
biggest unless `layout` says (row, stack, or columns with each label under its figure).

In the overlay layout a capture with `"layout": "split"` (or `"scene"`) is a full-frame scene. A kinetic card up with
a scene draws over it, and the scene takes the dark ground (`"ground": "ink"`) so the white and gold type reads. For a
stat_stack, `beside` is then where the scene's picture draws: give the capture its pixel `size` in images.json
(capture.mjs writes it; add it to a picture added by hand) so plan.py knows its shape. The split layout drops kinetic
cards.

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
inside `<Lockup>` (scrim fading in from the card's start, push, sweep) built from the primitives: `MarkerReveal` + `pullOn` / `pullOff` + `Behind`
(the marker and its hand-off to the foil), `FigureGlyphs` (paint `ink`, `white` or `gold`, with `FoilDefs`),
`Run` + `LineMask` + `stagger` (a line's reveal), `Odometer` + `counter` (a count from 40%), `Arrow`,
`settleAt` + `Scaled`, `exitAt` and `labelStart` (the hold and label rules). `Lockup` takes `out = Infinity` (it never
leaves: the next beat takes over) and `joined` (the scrim is already up) for a lockup that spans beats. No GSAP timeline state, no
Math.random, no clock; no blurred box-shadow on a moving layer, no transform once settled, no opacity on a scaled
layer. Export a `probe` (kinetic/probe.ts: what it draws as rectangles, its counts frame by frame) and register it in
`kinetic/index.ts` PROBES. Add made-up cases to `test/kinetic/<type>.json` (one with `"determinism": true`; edge cases
with `"probe_only"`, and `"expect_error"` for one that must throw), run `node test/templates.mjs <public> test/kinetic
<out>` (it checks every probe first: nothing past the frame or on top of anything else, labels 40 px apart,
connectors at their length, a count never past its final value) and `node test/determinism.mjs <out> --only kinetic`,
and look at the stills. Budget: about +0.05 s a frame per card up at 1080x1920 (number_chain measured +0.03, stat_stack +0.01,
step_build under +0.01).
