# This fork

This repo is a fork of NextWork's ai-video-editor (remote `upstream`). The fork keeps upstream's
layout, conventions and tests, and adds its own changes on top. The goal: graphics through the whole
video, made automatically, with free tools only, rendered at the best quality the renderer gives.

Fork base: upstream commit `4d48b2e` (ai-editor 2.4.0, creator-teardown 2.6.0).
Fork work so far: Phase 1, merged on branch `phase1` from four branches (`p1-numbers`, `p1-render`,
`p1-lottie`, `p1-determinism`). Each change has its own entry under "## Unreleased" in CHANGELOG.md.

## What the fork changes, and why

### 1. Spoken numbers (`p1-numbers`)

Why: the plan check failed real cards. "two hundred and fifty" was read as 2, 100 and 50, so a card
showing "250" counted as a number nobody says; "7.5K" on a card never matched a spoken "seven point
five k"; an ease name such as "power2.out" or "back.out(2.5)" in a card's props counted as a number
on screen.

- `plugins/ai-editor/lib/ai_editor/numbers.py` (new): one shared parser for spoken numbers (standard
  library only). `spans()` gives each number in a run of words with its value, its kind (count,
  percent, money, duration) and its first and last word, so later steps can land a graphic on it.
  `written()` reads the card side ("€7.5K", "100K", "50%"). The file is named like Python's own
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

## What to offer upstream, and what stays here

Neutral fixes, worth a pull request to upstream (each a real bug any user hits):

- Spoken numbers (1). Before offering it: replace the demo's fixture in `numbers.py` (it holds the
  transcript of one of the fork owner's own videos, with real income figures; upstream's rule is
  that nothing personal ships) with a made-up take, and consider renaming the file to avoid the
  `numbers` clash with Python's own module (for example `spoken.py`), which removes the guard.
- Lottie cards (3), as they are.
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

   After every release:

   ```bash
   claude plugin marketplace update nextwork
   claude plugin update ai-editor@nextwork
   ```

   Restart Claude Code.

7. Check `claude plugin list`: `ai-editor@nextwork` shows the new version (for example
   `2.5.0-cooked.1`) and is enabled, and `creator-teardown@nextwork` is enabled. If the version did
   not move, uninstall and install it again.
