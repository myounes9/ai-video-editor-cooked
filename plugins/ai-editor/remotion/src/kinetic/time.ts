// Time for kinetic cards. Every time in a card's props is seconds after the card starts (plan.py turns each spoken
// "word" into its "at"); the card's Sequence starts with the card, so its own frame is the card's clock. These
// helpers keep the props in seconds and do the frame maths in one place.
import { useCurrentFrame, useVideoConfig } from "remotion";
import { prog } from "../motion";
import { COUNT_FROM, EASE, TIME } from "./tokens";

/** The card's clock: t (seconds since the card started), dt (one frame), fps, and f(s): a props time as the frame
 *  it falls on (rounded down: a landing at 0.51 s at 30 fps is frame 15, the first frame at or after 0.5 s). */
export const useClock = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return { t: frame / fps, dt: 1 / fps, fps, frame, f: (s: number) => toFrame(s, fps) };
};
export const toFrame = (s: number, fps: number) => Math.floor(s * fps + 1e-6);
/** A props time snapped onto the frame grid (the time of the frame it falls on). */
export const onGrid = (s: number, fps: number) => toFrame(s, fps) / fps;

/** A label's start: its own word, never before its figure + TIME.labelAfter. No label_at: figure + labelAfter. */
export const labelStart = (at: number, labelAt?: number) => Math.max(typeof labelAt === "number" ? labelAt - 0.04 : -Infinity, at + TIME.labelAfter);

/** When the lockup leaves (the exit sweep starts). It holds at least TIME.hold after its last landing; props.out_at
 *  (the planner's hint) may keep it longer; it always leaves in time to be gone when the card ends (dur), which wins
 *  over the hold (the next speech forced it). */
export const exitAt = (dur: number, lastLanding: number, outAt?: number) => {
  const latest = dur - TIME.exit;
  const want = typeof outAt === "number" ? Math.max(outAt, lastLanding + TIME.hold) : latest;
  return Math.max(0, Math.min(latest, want));
};

/** A counter from COUNT_FROM x `to` up to `to` over [c0, c0 + cd] on EASE.count. land: the first frame whose shown
 *  value reads final (the landing hit fires there, never on a frame still short of it). */
export const counter = (t: number, to: number, decimals: number, c0: number, cd: number, fps: number) => {
  const from = to * COUNT_FROM;
  const val = (u: number) => from + (to - from) * prog(u, c0, cd, EASE.count);
  const fin = to.toFixed(decimals);
  let land = c0 + cd;
  for (let i = toFrame(c0, fps); i <= toFrame(c0 + cd, fps) + 1; i++) {
    if (val(i / fps).toFixed(decimals) === fin) { land = i / fps; break; }
  }
  return { value: val(t), val, land, from };
};
