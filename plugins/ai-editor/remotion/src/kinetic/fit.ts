// Where a kinetic lockup may sit and how big it may be. Every format fits its type with measured widths (type.ts)
// against two things only: the grid (one left and right text edge for every beat) and the face band, the strip over
// the hair and forehead the planner passes as props.band ([top, bottom], % of the frame height, from face.json:
// under the Reels header, above the eyes). The largest size that fits wins; nothing is placed by eye.
import { BAND, BAND_MAX, BESIDE_GAP, BESIDE_MIN, GRID, HEADER } from "./tokens";

export type Box = { k: number; left: number; right: number; width: number; top: number; bottom: number; height: number };

const nums = (x: unknown, n: number): x is number[] => Array.isArray(x) && x.length === n && x.every((v) => typeof v === "number" && Number.isFinite(v));

/** The grid and the band in px for a w x h card (a kinetic card's box is the whole frame). k: the short side / 1080,
 *  the scale every px token is multiplied by (type reads the same on a vertical and a wide frame). band: props.band,
 *  else BAND; its top never above HEADER. A band that is not [top, bottom] with top under bottom inside 0-BAND_MAX %
 *  throws (a reversed band once drew the figure towards the eyes, a low one over the captions). beside: props.beside,
 *  the picture of a capture or scene up with the card ([x, y, w, h] % of the frame, plan.py kinetic_links): the band
 *  stops BESIDE_GAP above it when that leaves BESIDE_MIN % of the frame or more (else check.py plan flags it). */
export const layoutBox = (w: number, h: number, band?: unknown, beside?: unknown): Box => {
  let b = BAND;
  if (band !== undefined && band !== null) {
    if (!nums(band, 2) || !(band[0] < band[1]) || band[0] < 0 || band[1] > BAND_MAX)
      throw new Error(`kinetic band ${JSON.stringify(band)}: give [top, bottom], % of the frame height, top under bottom, inside 0-${BAND_MAX} ` +
        "(over the hair and forehead, above the eyes)");
    b = band as [number, number];
  }
  const top = (Math.max(HEADER, b[0]) / 100) * h;
  let bottom = (Math.max(b[0] + 4, b[1]) / 100) * h;
  const left = w * GRID.left, right = w * GRID.right, k = Math.min(w, h) / 1080;
  if (nums(beside, 4)) {
    const [bx, by, bw] = beside, y0 = (by / 100) * h - BESIDE_GAP * k;
    if ((bx + bw) / 100 * w > left && (bx / 100) * w < right && y0 < bottom && y0 - top >= (BESIDE_MIN / 100) * h) bottom = y0;
  }
  return { k, left, right, width: right - left, top, bottom, height: bottom - top };
};

/** The layout at the largest size from `max` down to `min` (in `step`s) whose `ok` holds; at `min` when none does
 *  (ok false: the format then tries its next layout, or throws). Solved once per card (useMemo), never per frame. */
export const fitDown = <T extends { ok: boolean }>(max: number, min: number, step: number, solve: (size: number) => T): T & { size: number } => {
  for (let s = max; s > min; s -= step) {
    const g = solve(s);
    if (g.ok) return { ...g, size: s };
  }
  return { ...solve(min), size: min };
};
