// The kinetic family's design tokens (references/kinetic.md): one type system, one key colour, one grid and one
// set of timings for every format (number_chain, kinetic_number, goal_bar, step_build, stat_stack, kinetic_title,
// cta_follow). A format reads these and never sets its own colour, face or timing. Sizes are px on a frame whose short
// side is 1080; multiply by k = short side / 1080 (fit.ts layoutBox).

// ---------- colour ----------
/** The key colour: a figure's highlighter marker, and the face of the foil. */
export const KEY = "#FFD400";
/** Ink on the marker. */
export const INK = "#0B0B0B";
export const WHITE = "#FFFFFF";
/** The restrained foil: [colour, position] with positions as shares of the cap height from the cap top (0) to the
 *  baseline (1). Pale just above the caps, #FFD400 across the face, never darker than #E0A300 at the foot. */
export const FOIL: [string, number][] = [["#FFF3B8", -0.083], ["#FFE36A", 0.083], ["#FFD400", 0.333], ["#FFCC00", 0.611],
  ["#F2B800", 0.889], ["#E0A300", 1.083]];
/** The foil's hairline outline and the shade under its upward edges. */
export const BRONZE = "#5A3700";
/** The one warm sheen that crosses foil text as it lands (its peak; never white, so it never bleaches). */
export const SHEEN = "rgba(255,244,200,0.6)";
/** One soft shadow for white type over footage: lifts it off a bright wall without an outline. */
export const SOFT = "0 2px 24px rgba(0,0,0,0.38), 0 1px 3px rgba(0,0,0,0.22)";
/** The connector's underlay: a crisp offset stroke under the white one (no blur: a blurred shadow on a moving
 *  layer is the least stable thing to draw across render tabs). */
export const UNDER = "rgba(0,0,0,0.28)";

// ---------- type ----------
/** Figures: Anton, a tall condensed display face. Supporting lines and labels: Oswald 500 (its sibling). */
export const DISPLAY = { family: "Anton", weight: 400 };
export const TEXT = { family: "Oswald", weight: 500 };
/** Letter-spacing in em: figures run a hair tight, labels are tracked caps, lines a little open. */
export const TRACK = { figure: -0.005, label: 0.12, line: 0.02 };
/** A currency sign before a figure and a % after it are set smaller, their cap tops on the figure's cap top. */
export const PREFIX_K = 0.6;
export const PERCENT_K = 0.56;
/** A label's size: k x its figure's size, never under `size` px; to let the figures grow it may step down to kMin x the
 *  figure and `soft` px (a two-word label wraps onto two lines before it goes smaller), and only when nothing else fits
 *  to `floor` px (caps about 40 px tall at 1080: still read at phone size).
 *  over: how far an outer label may reach past the grid into the side margin, px on a 1080 short side: to 60 px from
 *  the edge, the reels safe zone's side (plan.py SAFE, which check.py render measures the drawn type against). */
export const LABEL = { k: 0.2, kMin: 0.16, size: 48, soft: 48, floor: 44, over: 12 };

// ---------- grid and placement ----------
/** Every lockup hangs from one left text edge and stops at one right edge: 72 and 1008 px of 1080. */
export const GRID = { left: 72 / 1080, right: 1008 / 1080 };
/** Where a title may sit when the planner passes no `band`: % of the frame height, over the hair and forehead,
 *  under the Reels header and above the eyes on a close talking head. */
export const BAND: [number, number] = [8.6, 26.2];
/** The Reels header: no title ever starts above this, % of the frame height. */
export const HEADER = 8;
/** A band from the planner never reaches below this, % of the frame height (the eyes and the captions are lower). */
export const BAND_MAX = 50;

// ---------- timing (seconds unless named in frames) ----------
export const TIME = {
  /** A figure is pulled on (the marker's leading edge runs across) from at - lead over pull. */
  lead: 0.1, pull: 0.17,
  /** The marker's leading edge leans this many degrees while it runs, and straightens as it lands. */
  lean: 10,
  /** The figure's cut-in settle: from this scale to 1 over settleFrames, expo.out. */
  settleFrom: 1.06, settleFrames: 6,
  /** A label lands no earlier than its figure + this. */
  labelAfter: 0.15,
  /** A title holds at least this long after its last landing, unless the card ends sooner (the next speech). */
  hold: 1.2,
  /** The exit: one feathered sweep, left to right. */
  exit: 0.23,
  /** The held lockup's slow push: this much scale over its life. */
  push: 0.015,
  /** Line reveal: each character starts this long after the one before and rises over rise. */
  stagger: 0.018, rise: 0.3,
  /** A connector draws from the next figure's at - connectorLead over connectorDur: done before it lands. */
  connectorLead: 0.22, connectorDur: 0.16,
  /** A marker hands its figure to the foil (pulled off) from the next figure's at - handoffLead over handoff. */
  handoffLead: 0.3, handoff: 0.15,
  /** The sheen starts this long after a landing and crosses in sheenDur. */
  sheenDelay: 0.24, sheenDur: 0.8,
  /** The top scrim fades in over this before the first landing, and out with the exit. */
  scrim: 0.35,
};
/** Counters start at this share of their value on their first visible frame: no "0" is ever shown. */
export const COUNT_FROM = 0.4;

// ---------- motion blur ----------
/** A moving glyph's vertical blur from its travel across one frame: none under minPx, k per px, capped at maxPx
 *  (px on a 1080 short side). */
export const BLUR = { k: 0.15, minPx: 6, maxPx: 7 };

// ---------- eases ----------
export const EASE = { pull: "power3.out", settle: "expo.out", rise: "expo.out", exit: "power2.in", draw: "power3.out",
  handoff: "power3.in", count: "expo.out", sheen: "power1.inOut", scrimIn: "sine.out", scrimOut: "sine.in" };

// ---------- goal_bar ----------
/** The goal track (no panel): a pill well with its remainder showing (a 1 px edge in alpha, a gradient shade under its
 *  top lip, never a blurred inset shadow), a key-colour fill lit from the top, a glow band behind it (a gradient, never
 *  a box-shadow) and the target marker at its end: a smoked disc, a white rim and a dot that turns key on "goal".
 *  Sizes are shares of the figure size S; times in seconds unless named in frames. */
export const GOAL = {
  well: "rgba(255,255,255,0.14)", edge: "rgba(255,255,255,0.22)", shade: "rgba(0,0,0,0.38)", fillTop: "#FFE14D",
  /** Under the well with no panel behind it: a dark tint, so the remainder still reads over a bright wall. */
  under: "rgba(0,0,0,0.2)",
  /** The glow band's colour as r,g,b (its alpha moves: rest, while the fill runs, the landing flare's peak). */
  glow: "255,212,0", glowRest: 0.32, glowRun: 0.5, glowFlare: 0.85,
  discFill: "rgba(20,20,24,0.55)", rim: WHITE,
  /** Track height (at least `minH` px at 1080), the gap above it, the disc's diameter on the track height. */
  h: 0.15, minH: 22, gap: 0.17, discK: 1.35,
  /** The module's widest, in px at 1080 (the vertical grid's width): a wide frame centres it rather than stretch it. */
  maxW: 936,
  /** The well draws along its length from the figure's pull over draw; the disc pops (back.out, sized, never scaled) on
   *  the target's word; two rings leave it on "goal", ringGap frames apart, each growing to ringOut x its radius. */
  draw: 0.38, pop: 0.34, popEase: "back.out(2.2)", ring: 0.7, ringGap: 5, ringOut: 2.1, flareFrames: 6,
  /** A count with no word for its end reads final this long after its figure's word ("forty percent"). */
  countAfter: 0.3,
};

// ---------- step_build and stat_stack ----------
/** A tracker slot (step_build): a smoked glass well with a light edge (alpha in the colour, never opacity), so an empty
 *  slot reads on a bright wall as well as on a dark one; the gold edge a filled slot keeps once its marker has handed it
 *  to the foil, a question slot's dashed edge, an empty slot's numeral. radius, gap and line: px on a 1080 short side. */
export const SLOT = { well: "rgba(12,12,12,0.3)", edge: "rgba(255,255,255,0.55)", done: "#E8B400", ask: "rgba(255,255,255,0.85)",
  numeral: "rgba(255,255,255,0.86)", radius: 14, gap: 28, line: 1.5 };
/** A slot pops in on its word: popFrom -> 1 over popFrames on popEase (slots on one word popStagger apart); the slots
 *  already up slide aside over reflow first, so it lands in its own place. A returning tracker sweeps in left to right
 *  over TIME.exit on enterEase. */
export const STEP = { popFrom: 0.84, popFrames: 9, popEase: "back.out(2.2)", popStagger: 0.08, reflow: 0.3, reflowEase: "power3.inOut",
  enterEase: "power2.out" };
/** stat_stack (and any format over a scene): how far it keeps from the capture it sits beside (px on a 1080 short
 *  side), and the least room above that capture worth fitting into (% of the frame height). */
export const BESIDE_GAP = 24;
export const BESIDE_MIN = 7;
