# This fork

This repo is a fork of NextWork's ai-video-editor (remote `upstream`). The fork keeps upstream's
layout, conventions and tests, and adds its own changes on top. The goal: graphics through the whole
video, made automatically, with free tools only, rendered at the best quality the renderer gives.

Fork base: upstream commit `4d48b2e` (ai-editor 2.4.0, creator-teardown 2.6.0).
Upstream merged since: ai-editor 2.7.8 (upstream `871cabe`), on branch `p3-base`.
Fork work so far: Phase 1, merged on branch `phase1` from four branches (`p1-numbers`, `p1-render`,
`p1-lottie`, `p1-determinism`), Phase 2 (kinetic titles), merged on branch `phase2`, and Phase 3 (the kinetic
titles placed automatically), merged on branch `phase3` from `p3-beats`, `p3-place` and `p3-rules`, with the review's
fixes on top (section 9). Each change has
its own entry under "## Unreleased" in CHANGELOG.md.

## What the fork changes, and why

### 1. Spoken numbers (`p1-numbers`)

Why: the plan check failed real cards. "three hundred and forty" was read as 3, 100 and 40, so a card
showing "340" counted as a number nobody says; "4.5K" on a card never matched a spoken "four point
five k"; an ease name such as "power2.out" or "back.out(2.5)" in a card's props counted as a number
on screen.

- `plugins/ai-editor/lib/ai_editor/numbers.py` (new): one shared parser for spoken numbers (standard
  library only). `spans()` gives each number in a run of words with its value, its kind (count,
  percent, money, duration) and its first and last word, so later steps can land a graphic on it.
  `written()` reads the card side ("€4.5K", "20K", "50%"). The file is named like Python's own
  `numbers` module; an 8-line guard at its top hands back the real module when Python loads it by
  that name (several shared scripts put `lib/ai_editor` first on the import path).
- `plugins/ai-editor/skills/style-edit/scripts/check.py`: `said_numbers` and `unsaid_numbers` use
  the parser, on the cut's punctuated transcript (`cut.transcript.json`) and the caption chunks, each
  chunk's end ending a number. A card's K/M/B must be the one said: a different one FAILs (it passed
  before), one added to a bare spoken number, or a % to a number not said as one, WARNs; every other
  number that passed before still passes. A Lottie card's `props.texts` are checked. A card's motion
  props (`MOTION_KEYS`: enter, exit, ease, ambient, word_at, accent ...) are not scanned unless they
  hold words (`shown_texts`).
- `docs/feedback-matrix.md`, `skills/style-edit/references/visuals.md`: the rule, as it now reads.
- `tests/demos.sh`: runs `numbers.py demo`.

### 2. Final render quality (`p1-render`)

Why: finals came out of Chrome as JPEG at quality 80 (soft caption and card edges), were tagged
full-range BT.601 while the cut is BT.709 limited range, used x264 medium at CRF 18, and laptop
renders carried 192k sound with no peak limit.

- `plugins/ai-editor/remotion/render.mjs`: one `FINAL` setting for every final (laptop, chunk,
  Lambda and the bench): PNG frames, BT.709, x264 preset slow, CRF 16. One `AUDIO` setting: AAC
  320k through a true-peak limiter (-1.5 dBFS ceiling read at 4x the sample rate, so the file lands
  at or under -1 dBTP; look-ahead compensated with apad/atrim, so FFmpeg 4.4 runs it, no make-up
  gain). Lambda's download gets one more
  sound pass with the picture copied. Drafts keep their picture settings and get the new sound.
- `plugins/ai-editor/skills/style-edit/scripts/edit.py`: the same limiter for the GitHub join and
  the patch splice (its demo checks render.mjs and edit.py agree); the patch splice re-encodes with
  the final x264 and colour tags and refuses to patch a render made before this change; the cut at
  output size is made with preset medium (was veryfast); a saved laptop speed from before these
  settings is benchmarked again (`laptop.json` "final" key); the cloud speeds measured before are
  scaled by `FINAL_SLOWER` (1.6) and a saved `modal.json` from before keeps only its upload speed;
  Lambda's timeout is 900 s (`render.mjs` `LAMBDA_TIMEOUT_S`, was 240).
- `skills/style-edit/references/render.md`: a "Final quality" section with the measurements.

Cost of it: about 1.6x the render time on a laptop, and cloud renders slower by about as much.

### 3. Lottie cards (`p1-lottie`)

Why: a Lottie exported at 60 fps played at half speed in a 30 fps edit, a font's weight written only
in its style name ("ExtraBold") drew at 400, its font family never loaded (a serif fallback), and a
broken file left an empty card.

- `plugins/ai-editor/remotion/src/StyleEdit.tsx` (`LottieCard`): plays at the file's own frame
  rate, reads the weight from the style name, loads each font through the same Google Fonts loader
  as the rest of the editor (Inter when the family is not there), takes `props.texts` to replace a
  text layer's words, and stops the render with the file's name when it fails to load. Its box only
  fades and wipes (no scale or slide), so its text lays out the same in every tab.
- `skills/style-edit/scripts/check.py` (`lottie_findings`) and `edit.py` (`lottie_warnings`): a
  warning before stills and renders on an odd frame rate, no frames, an unknown font or a style that
  names no weight.
- `plugins/ai-editor/remotion/test/lottie.mjs`, `test/public/lottie/title-60fps.json` (new), plus
  a `lottie-v` case in `test/cases.json` and `test/templates.mjs` serving `test/public`.
- `skills/style-edit/references/contracts.md`: the Lottie bullet in the plan.json card section.

### 4. Same frames in every tab (`p1-determinism`)

Why: a render split across Chrome tabs gave different pixels from a render in one tab (up to
240/255 on card edges), so pieces of one video could flicker against each other.

- `plugins/ai-editor/remotion/src/motion.ts`: `gsap.config({ force3D: false })`, so GSAP writes 2D
  transforms and no element moves to its own GPU layer mid-tween; an `EASES` list of every
  registered ease.
- `plugins/ai-editor/remotion/src/product/ProductVideo.tsx`: no `will-change` on the zooming page.
- `plugins/ai-editor/remotion/src/Root.tsx`: the Proof composition gains an "eases" mode and runs
  90 frames.
- `plugins/ai-editor/remotion/test/determinism.mjs`: renders every frame of each case in 6 tabs and
  in one tab and compares them pixel for pixel; a Lottie card with text is one case.
- `skills/style-edit/references/motion.md`: the one-line rule.

### 5. Kinetic titles (Phase 2: `p2-foundation`, `p2-number`, `p2-goal`, `p2-step`, `p2-title`, merged on `phase2`)

Why: the fork's goal is graphics through the whole video, and a talking head's own results (a count, a goal, a
chain of figures) have no page to capture. The kinetic family sets them over the footage, opt-in per style.

- `plugins/ai-editor/remotion/src/kinetic/` (new): the design system (`tokens.ts`, `type.ts`, `time.ts`, `fit.ts`,
  `primitives.tsx`), `NumberChain.tsx` (the reference format), one file per format,
  `Kit.tsx` (every primitive on one frame, a `KineticKit` composition in `Root.tsx`).
- `Templates.tsx` registers them as floating templates; `StyleEdit.tsx` fades the word captions out while one is up.
- `skills/style-edit/scripts/plan.py` (`KINETIC`, `kinetic_on`, `hides_captions`), `check.py`, `ai_tells.py`,
  `quality.py`: the opt-in (`graphics.kinetic`), the kinetic lane and whole-frame box, part words to times, number
  grounding on every figure, not a text card once opted in.
- `references/kinetic.md` (new), pointers in `motion.md` and `contracts.md`; tests in `remotion/test/kinetic/` and
  `test/determinism.mjs`.
- `KineticNumber.tsx` (`p2-number`): `kinetic_number`, one figure with a sub-line; variants hook, counter, tally and
  stamp. Cases in `remotion/test/kinetic/kinetic_number.json`.
- `GoalBar.tsx` (`p2-goal`): `goal_bar`, the goal layout without a panel. `quality.py` reads no panel edge on a
  kinetic card.
- `step_build` and `stat_stack` (`p2-step`): `kinetic/StepBuild.tsx` (a tracker across beats, joined by plan.py
  `kinetic_links` when two beats of one tracker are under 1 s apart) and `kinetic/StatStack.tsx` (stats beside a
  capture, its box passed as `beside` by `kinetic_links`). `StyleEdit.tsx`: a kinetic card gets no lane swap and
  leaves the frame to the next card in its lane at its start; `primitives.tsx` `Lockup` takes `out = Infinity` and
  `joined`.
- `KineticTitle.tsx` and `CtaFollow.tsx` (`p2-title`): `kinetic_title` (plan.py `title_times` times each word in
  reading order) and `cta_follow`. `quality.py` judges a title's landing on the last word it shows in its first
  0.6 s and reads no outline jitter on a kinetic card.
- Integration (`phase2`): a kinetic card draws over a full-frame scene it shares the frame with (`StyleEdit.tsx`), the
  scene on the dark ground, a stat_stack beside the scene's picture (plan.py `scene_capture`, `kinetic_links`), and
  check.py render skips a kinetic card's measures while a scene is up.
- Review fixes (`phase2`): the counter never reads past its final value, the scrim fades in and out, a stamp keeps to
  its figure's foot, tiles fill after their figure, readable labels with a chain or tracker that cannot fit stopping
  the render (and check.py plan catching it first), stat_stack columns; plan.py `bridge_kinetic` (no caption flashes
  between cards) and pushes instead of cuts under a kinetic card's hold; `beside` for every kinetic card over a scene.
  Each format exports a `probe` (`kinetic/probe.ts`) that `test/templates.mjs` checks on every kinetic case.

- Placement and timing (Phase 3, `p3-place`): plan.py `face_band` and `kinetic_bands` set each card's band from
  face.json over its own time (check.py `kinetic_eyes` checks it); captions hide only under number cards (plan.py
  `HIDES_CAPTIONS`, `kinetic/index.ts`); `punch_between` keeps punches on the plain footage between cards; one graphics
  budget (`lib/ai_editor/budget.py`, `graphics.kinetic_per_min`) that the beat finder and plan.py `budget_cards` share;
  style_check.py and quality.py compare with it.

Fork-only: a look this fork chose (words over the footage, a house key colour), against upstream's rule that a
number is shown inside the page that published it. Off unless a style opts in.

### 6. Automatic number beats (Phase 3: `p3-beats`)

Why: the kinetic beats of Phase 2 were written by hand for each video; the goal is graphics placed with no one
writing them, at a set density, only where a number is said.

- `plugins/ai-editor/skills/style-edit/scripts/kinetic_beats.py` (new, standard library only): candidates from
  numbers.py spans by sentence and clause (hook, chain, goal, stat run, counter with stamp, tally, money, lone figure,
  step tracker), labels from the transcript's own words, ranked and kept to `graphics.kinetic_per_min` (default 8)
  graphics a minute with the edit's real cards counted first, 1 s of footage between cards, written into visuals.json
  as `"auto": "kinetic"` beats with a fingerprint in `kinetic.auto.json` (`refresh()`). CLI: `find`, `write`,
  `words`, `demo`.
- `plan.py` main: calls `kinetic_beats.refresh()` when `kinetic_on(style)`, before it reads visuals.json.
- `route.py`: `mark_kinetic()` marks the sentences that get a number beat (`"kinetic"` in beats.json, `[kinetic]`).
- `style_check.py`: a style's own kinetic cards are no alien kind, and sit at the top of the frame.
- `agents/visual-prep.md`, `agents/template-filler.md`: write no kinetic beat; `references/kinetic.md` "Automatic
  beats", `references/contracts.md` (the `auto` mark); `tests/demos.sh` runs its demo.

### 7. Rules to settings and emphasis captions (Phase 3: `p3-rules`)

Why: the user's saved feedback ("add motion graphics", "kinetic number titles", "key words in yellow, slightly
bigger") was a line in a skill that no script read, so every video needed beats written by hand; and upstream marks
a caption word only in pages of 3+ words and never draws it bigger, so the numbers on 2-word pages went unmarked.

- `plugins/ai-editor/lib/ai_editor/taste.py`: `settings_for(text, section)` reads a rule's words as the fork's settings
  (`graphics.kinetic`, `graphics.kinetic_per_min`, `captions.emphasis_color`, `captions.emphasis_scale`); `load_json`
  lays each scope's word-rule settings under that scope's saved ones and counts them; `replan(keys)` and `REPLAN` say
  what to run again; `taste.py map`. `review.py learn` (notes and the Teach panel) prints the REPLAN line;
  `styleskill.py` shows "Sets:" on a rule; `presets.py` lets a caption preset carry `emphasis_scale`.
- `skills/style-edit/scripts/plan.py`: `emph_on`, `key_words`, `mark_emph(chunks, cap, words)`: with
  `captions.emphasis_scale` set, every spoken number (numbers.py) and the key words, on pages of any length.
- `remotion/src/Captions.tsx`: `emphasis_scale` (opt-in) scales a stressed word through a transform; the line is fitted
  with room for it; with it set, the stressed word keeps its colour while said. Test cases in `test/cases.json` and
  `test/determinism.mjs`.
- Guidance: `references/kinetic.md` "From the user's rules" and "For the AI steps", rows in `references/review.md`,
  the taste SKILL.md table, `agents/visual-prep.md`, `agents/template-filler.md`, overlays `references/changes.md`.

Fork-only: upstream chose one type size per page ("never bigger") and reads no settings from a rule's words. Both are
off unless a rule or a setting asks for them.

### 8. The automatic path, end to end (Phase 3 integration: `phase3`)

Why: the three Phase 3 parts each worked alone; together the beat finder, plan.py and the visuals step counted the
graphics three ways, and a real edit lost every kinetic card to the split panel.

- One count: `kinetic_beats.py` takes its rate and count from `lib/ai_editor/budget.py` (`count`, `per_min`; the style
  page's `cards.per_min` no longer caps it) and gives each beat its `strength` and the hook `"hook": true`, so plan.py
  `budget_cards` keeps the same beats; a tracker's beats share one strength and `budget.pick` never spaces them apart
  (`group`). `taste.KINETIC_RATE` is budget's default.
- `route.py`: with kinetic titles on, `want` marks only the budget's room left after the number beats and the edit's
  own cards (`mark_kinetic` now sees images.json and visuals.json), never a `[kinetic]` line, and no title hint for the
  hook. `taste.REPLAN_STEPS["beats"]` names plan.py, whose beat finder places the beats again.
- `plan.py`: with kinetic titles on, a picture asking for the split panel is a full-frame scene (only a split layout
  set by hand opens the panel, where kinetic cards cannot go); two punches on plain footage join only up to
  `PUNCH_JOIN_MAX_S`; a caption figure keeps its decimal point (`cased`: "3.5k" was drawn "35k").
- `cta_follow` keeps the word captions like `kinetic_title` (plan.py `HIDES_CAPTIONS`, `kinetic/index.ts`): only number
  cards hide them. `StyleEdit.tsx`: over a dark scene ground the emphasis captions keep their colour.
- `style_check.py`: with kinetic titles on, a kinetic card counts as the creator's text cards in her mix.

### 9. Review fixes (Phase 3, on `phase3`)

Why: a review of the automatic path found a caption that read a number the speaker did not say (a card's end hid "a
hundred and" of "a hundred and sixty-four"), first-come picks instead of the strongest, a tracker the user asked for
that could never fit, rules in words that read "do not add motion graphics" as a yes, and a beat finder that made
cards of clock times, years, dates, prices and ranges.

- `lib/ai_editor/numbers.py`: "half a million" is 500000 (was 1000000), "minus five" is -5 (the span starts on its
  sign); `written()` reads a minus sign straight before digits. The demo's take is made up (an ice cream van).
  `check.py` `said_numbers` no longer reads those words alone as other numbers, so a "1M" or "5" card for them FAILs.
- `skills/style-edit/scripts/kinetic_beats.py`: only counts of things are figures (`figures()`: no sign, year, date,
  clock time, address, phone number, name's number, measure, back-to-back pair, range or ratio, "a hundred percent
  sure", pronoun "one"); the hook needs money or a count or percent of a plural thing, from the first sentence that is
  more than filler, never past 6 s; a chain across sentences needs a funnel cue (`funnel()`), ends on "one" only after
  its verb and draws it bare; labels are never number words or dates; "2,345", never "2.345K"; a goal comes up on its
  first word; tracker items with no noun take their verb, "now for step two" is a cue; a tracker of sources, steps or
  ways ranks with a stat run (`ENUM_BONUS`). `select()`: a tracker is one graphic, holds cut to 1.3 s for the gap, 1 s
  beside real cards too (they end sooner: plan.py `space_kinetic`), a strong beat bridges from the one before it, and
  no card ends on the first words of the next number (`whole()`). `refresh()` keeps what review notes did to its beats
  through a re-find (`"removed"`, `"edits"`, `beat_key()`); `clear()` takes them out when the style turns them off
  (plan.py now calls one or the other on every plan). Fixtures reshaped, a 28-sentence negative table.
- `lib/ai_editor/budget.py` `pick`: a tracker's beats are one graphic, kept or left out together (route.py,
  style_check.py count them so too).
- `skills/style-edit/scripts/plan.py`: `space_kinetic`, `whole_numbers` and `split_numbers` (check.py plan FAILs a card
  that hides the start of a number whose rest shows); `clear_entrances` joins punches on plain footage (and splits
  them past 5 s) only with kinetic cards in the plan, so upstream styles zoom as upstream's do, and moves an edge in the
  gap between a scene and the kinetic card after it under the scene; emphasis marks a number's own words only (not
  "and a"), a two-word name whole, and no key word in a sentence that says a number.
- `skills/style-edit/scripts/check.py` render: a kinetic card's type is measured as what is brighter than the footage
  (its scrim is not its ink) and WARNs off centre (3%) or past the side margin. `remotion/src/kinetic/NumberChain.tsx`
  centres the row on its ink (a long last label pulled it right) and `tokens.ts` `LABEL.over` (36 -> 12 px) keeps an
  outer label 60 px from the edge, the safe zone's side; `test/templates.mjs` checks the centring.
- `lib/ai_editor/taste.py` `settings_for`: a no anywhere in the clause is a no, two or one in a note about placement
  is unclear (nothing set); "no more than N a minute" is a rate, "not only photos" a contrast; a no to emphasis sets
  `emphasis_scale` null.
- Privacy: the fork owner's figures are gone from check.py's and numbers.py's docs, FORK.md, the CHANGELOG and the
  feedback matrix (made-up figures instead); they stay in the public history of `main`.
- Migration: upstream once documented `captions.emphasis_scale` and retired it in 2.7.8; the fork reads it as the
  opt-in, so an older style.json that still holds it gets the fork's emphasis captions. Remove the key to keep
  upstream's.

## What to offer upstream, and what stays here

Neutral fixes, worth a pull request to upstream (each a real bug any user hits):

- Spoken numbers (1), with "half a million" and "minus five" read right (9). Its demo's take is made up since (9); the
  earlier one, reworded from one of the fork owner's own videos, is still in this repo's history. Consider renaming the
  file to avoid the `numbers` clash with Python's own module (for example `spoken.py`), which removes the guard.
- Lottie cards (3), as they are.
- A caption figure's decimal point (8, plan.py `cased`): "3.5k" was drawn "35k", a number nobody said.
- Same frames in every tab (4), as it is.
- From the render change (2), the parts that are fixes rather than taste: tagging finals BT.709
  limited range like the cut, the same 320k sound on laptop renders as on GitHub, and the
  true-peak limiter.

Fork-only, a choice of this fork rather than a fix:

- PNG frames, x264 slow at CRF 16 and the proxy at preset medium (2): better pictures for about
  1.6x the render time and cloud cost. Upstream may well prefer speed.
- This file.

## Merge routine for each upstream release

Run from the repo root, on a clean tree. Do the merge on a branch, never straight on `main`.

Upstream ships a helper for exactly this (`plugins/ai-editor/skills/update`; say "update the editor" in
Claude Code from this folder, or run it by hand): `update.py check` lists upstream's new commits and the
files both sides changed, `update.py merge` makes a backup branch and merges `upstream/main` (it stops
on conflicts and lists them), `update.py verify` runs the fast checks, and `update.py rollback` returns
to the backup. It never pushes. Use it for steps 1-3, then run the full gates below, which are wider
than `verify` (the renderer tests, golden and smoke).

1. Get the release:

   ```bash
   git fetch upstream
   git switch main && git switch -c merge-upstream-<version>
   git merge upstream/main
   ```

2. Resolve conflicts. The places the fork touches most: `CHANGELOG.md` "## Unreleased" (keep every
   entry from both sides; upstream's release heading moves the fork's entries under the new
   heading only once they are released), `check.py`, `edit.py`, `render.mjs`, `StyleEdit.tsx`,
   `motion.ts`, `test/determinism.mjs`, `tests/demos.sh` (keep both lists). For code, read both
   sides and keep both intents; run the gates before deciding a conflict is done.

3. Run the gates. Use a test home so nothing touches the real editor home (`~/.ai-video-editor`,
   and its `laptop.json`):

   ```bash
   export AI_EDITOR_HOME=<a scratch folder with a venv and the renderer, set up by setup.py>
   PY=$AI_EDITOR_HOME/venv/bin/python
   python3 tests/check_plugins.py
   for p in . plugins/ai-editor plugins/creator-teardown; do claude plugin validate --strict "$p"; done
   NODE_OPTIONS=--experimental-strip-types PY=$PY bash tests/demos.sh
   # the renderer tests need node_modules beside the source:
   ln -sfn $AI_EDITOR_HOME/remotion/node_modules plugins/ai-editor/remotion/node_modules
   (cd plugins/ai-editor/remotion && npx tsc --noEmit && node test/determinism.mjs /tmp/det \
     && node test/lottie.mjs /tmp/lottie && node test/templates.mjs <public dir> test/cases.json /tmp/tpl)
   $PY tests/golden.py
   python3 tests/smoke.py
   ```

   Notes. `NODE_OPTIONS=--experimental-strip-types` is needed on Node 22 for `tests/test_record.mjs`.
   With a test home under the system temp folder, `styleskill.py demo` fails one assert (it treats a
   temp home as a scratch home on purpose); run it once with the real home, or read the assert.
   `templates.mjs` needs the card images its cases name (`images/...`); placeholders work.
   `golden.py` compares four stills with `tests/golden/darwin/` on a Mac: refresh them
   (`$PY tests/golden.py --update`) only when a change is meant to alter the look, and say why in the
   commit. `tests/golden/linux/` can only be refreshed on Linux (CI's `golden-out` artifact).

4. Bump the version. Upstream's version plus a fork suffix, in all four places RELEASING.md lists
   for ai-editor (`plugins/ai-editor/.claude-plugin/plugin.json`, its entry in
   `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`):
   for example upstream 2.5.0 becomes `2.5.0-cooked.1`, and the next fork-only release on that base
   `2.5.0-cooked.2`. Leave creator-teardown at upstream's version while the fork does not change it
   (ai-editor depends on `creator-teardown ^2.0.0`, which a `-cooked` version would not match).
   Add a CHANGELOG heading for the release. Run `python3 tests/check_plugins.py` and the validate
   line again.

5. Merge the branch into `main` and push to `origin` (the fork), never to `upstream`.

6. Update the installed plugin. The marketplace in this repo is also named `nextwork`, the same as
   upstream's, so the fork's copy replaces upstream's rather than sitting beside it. Once:

   ```bash
   claude plugin marketplace remove nextwork
   claude plugin marketplace add <the fork on GitHub, or this folder's path>
   claude plugin install ai-editor@nextwork --scope local   # from the folder you edit in; or --scope user
   ```

   Also point the marketplace entry in `~/.claude/settings.json` at the fork, or a later session can
   add upstream's `nextwork` back:
   `"extraKnownMarketplaces": {"nextwork": {"source": {"source": "github", "repo": "<you>/ai-video-editor-cooked"}}}`.
   Reinstall creator-teardown from the same marketplace (`claude plugin install creator-teardown@nextwork`,
   same scope), and check both with `claude plugin list`.

   After every release:

   ```bash
   claude plugin marketplace update nextwork
   claude plugin update ai-editor@nextwork
   ```

   Restart Claude Code.

7. Check `claude plugin list`: `ai-editor@nextwork` shows the new version (for example
   `2.5.0-cooked.1`) and is enabled, and `creator-teardown@nextwork` is enabled. If the version did
   not move, uninstall and install it again.
