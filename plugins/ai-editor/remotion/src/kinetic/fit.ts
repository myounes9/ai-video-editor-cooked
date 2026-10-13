// Where a kinetic lockup may sit and how big it may be. Every format fits its type with measured widths (type.ts)
// against two things only: the grid (one left and right text edge for every beat) and the face band, the strip over
// the hair and forehead the planner passes as props.band ([top, bottom], % of the frame height, from face.json:
// under the Reels header, above the eyes). The largest size that fits wins; nothing is placed by eye.
import { BAND, GRID, HEADER } from "./tokens";

export type Box = { k: number; left: number; right: number; width: number; top: number; bottom: number; height: number };

/** The grid and the band in px for a w x h card (a kinetic card's box is the whole frame). k: the short side / 1080,
 *  the scale every px token is multiplied by (type reads the same on a vertical and a wide frame). band: props.band,
 *  else BAND; its top never above HEADER. */
export const layoutBox = (w: number, h: number, band?: unknown): Box => {
  const b = Array.isArray(band) && band.length === 2 && band.every((x) => typeof x === "number") ? (band as [number, number]) : BAND;
  const top = (Math.max(HEADER, b[0]) / 100) * h, bottom = (Math.max(b[0] + 4, b[1]) / 100) * h;
  const left = w * GRID.left, right = w * GRID.right;
  return { k: Math.min(w, h) / 1080, left, right, width: right - left, top, bottom, height: bottom - top };
};

/** The layout at the largest size from `max` down to `min` (in `step`s) whose `ok` holds; at `min` when none does
 *  (drawn small rather than dropped). Solved once per card (useMemo), never per frame. */
export const fitDown = <T extends { ok: boolean }>(max: number, min: number, step: number, solve: (size: number) => T): T & { size: number } => {
  for (let s = max; s > min; s -= step) {
    const g = solve(s);
    if (g.ok) return { ...g, size: s };
  }
  return { ...solve(min), size: min };
};
