// The kinetic family's layouts as numbers, for test/templates.mjs: each format's `probe` returns what it draws as
// rectangles (its figures, labels, connectors, stamp, tiles, wells) and its counts frame by frame, solved by the same
// code the format draws with. The KineticProbe composition (Root.tsx) runs them in the renderer's own Chrome (real
// fonts, real measures) inside calculateMetadata and hands the results back as its props; templates.mjs checks them:
// nothing past the frame, nothing on top of anything else, labels 40 px apart, connectors at their length, a stamp off
// most of its figure, a count never past its final value, tiles never before their figure.
import type { CalculateMetadataFunction } from "remotion";
import { odometerShown } from "./primitives";
import { toFrame } from "./time";
import { Faces, Value, loadFaces } from "./type";

/** [x0, y0, x1, y1] px. in: the rectangle a part must stay inside (a step slot's label: its well). min: a connector's
 *  least length. */
export type R = [number, number, number, number];
export type Part = { kind: string; r: R; in?: R; min?: number };
/** final: the count's last value (in units of its last decimal); shown: what is drawn on every frame from the pull to
 *  the card's end; land: the frame the landing hit fires on. */
export type Count = { final: number; shown: number[]; land: number };
export type Probe = { k: number; parts: Part[]; counts?: Count[]; fills?: { first: number; marker: number }; sizes?: Record<string, number> };
export type Prober = (F: Faces, p: Record<string, any>, w: number, h: number, dur: number, fps: number) => Probe;

/** A counter's frames, as the Odometer draws them. */
export const countProbe = (val: (u: number) => number, v: Value, t0: number, land: number, dur: number, fps: number): Count => {
  const shown: number[] = [];
  for (let f = toFrame(t0, fps); f < Math.round(dur * fps); f++) shown.push(odometerShown(val, v, f / fps));
  return { final: Math.round(v.value * 10 ** v.decimals), shown, land: toFrame(land, fps) - toFrame(t0, fps) };
};

/** A run of caps type set on a baseline: its box from x over w, cap top to baseline. */
export const capsRect = (x: number, w: number, base: number, cap: number): R => [x, base - cap, x + w, base];

export type ProbeCase = { name: string; type: string; props: Record<string, any>; width: number; height: number; dur: number };
export type ProbeResult = { name: string; error?: string } & Partial<Probe>;

/** KineticProbe's calculateMetadata: every case through its format's probe; a case that throws reports its error. */
export type ProbeProps = { cases: ProbeCase[]; results?: ProbeResult[] };
export const probeMeta = (probers: Record<string, Prober>): CalculateMetadataFunction<ProbeProps> =>
  async ({ props }) => {
    const F = await loadFaces();
    const results = (props.cases ?? []).map((c): ProbeResult => {
      try {
        const pr = probers[c.type];
        if (!pr) throw new Error(`no probe for ${c.type}`);
        return { name: c.name, ...pr(F, c.props, c.width, c.height, c.dur, 30) };
      } catch (e) {
        return { name: c.name, error: String((e as Error)?.message ?? e) };
      }
    });
    return { props: { ...props, results }, width: 16, height: 16, fps: 30, durationInFrames: 1 };
  };
