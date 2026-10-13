// The kinetic family's type: Anton and Oswald loaded through look.tsx (Google Fonts, the render waits on them and
// stops with the font's name if one fails), measured on a canvas with the browser's own layout (letter-spacing
// included), so fits and per-character offsets match what is drawn.
import { useEffect, useState } from "react";
import { continueRender, delayRender } from "remotion";
import { loadFamily } from "../look";
import { DISPLAY, PERCENT_K, PREFIX_K, TEXT } from "./tokens";

/** A loaded face: its CSS family and its vertical metrics as shares of the font size. */
export type Face = { fam: string; weight: number; asc: number; desc: number; cap: number };
export type Faces = { display: Face; text: Face };

let CTX: CanvasRenderingContext2D | null = null;
const ctx = () => (CTX ??= document.createElement("canvas").getContext("2d")!);
const font = (f: Pick<Face, "fam" | "weight">, size: number, track: number) => {
  const c = ctx();
  c.font = `${f.weight} ${size}px ${f.fam}`;
  (c as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = `${(track * size).toFixed(3)}px`;
  return c;
};
/** Advance of `s` at `size` px with `track` em letter-spacing (spacing after every character, as laid out). */
export const adv = (f: Face, size: number, track: number, s: string) => font(f, size, track).measureText(s).width;
/** Ink width of a run: its advance less the trailing letter-spacing. */
export const runW = (f: Face, size: number, track: number, s: string) => adv(f, size, track, s) - track * size;
/** The ink of a run, from its origin: il (the left edge of the drawn glyphs, may be past 0 either way) and ir. */
export const ink = (f: Face, size: number, track: number, s: string) => {
  const m = font(f, size, track).measureText(s);
  return { il: -m.actualBoundingBoxLeft, ir: m.actualBoundingBoxRight };
};
/** x of each character: the advance of everything before it, so kerning pairs survive a per-character split. */
export const offsets = (f: Face, size: number, track: number, s: string) => {
  const cs = [...s];
  return cs.map((_, j) => (j ? adv(f, size, track, cs.slice(0, j).join("")) : 0));
};
const metrics = (fam: string, weight: number): Face => {
  const m = font({ fam, weight }, 100, 0).measureText("H0");
  return { fam, weight, asc: m.fontBoundingBoxAscent / 100, desc: m.fontBoundingBoxDescent / 100, cap: m.actualBoundingBoxAscent / 100 };
};
/** The baseline's offset from the top of a line box whose line-height equals the font size. */
export const baseOff = (f: Face, size: number) => (size - (f.asc + f.desc) * size) / 2 + f.asc * size;

/** Anton and Oswald, loaded and measured. null until both are in (the frame waits: delayRender). A family that
 *  falls back to another face stops the render: a title in the wrong face would pass unseen. */
export const useFaces = (): Faces | null => {
  const [faces, setFaces] = useState<Faces | null>(null);
  const [handle] = useState(() => delayRender("kinetic fonts"));
  useEffect(() => {
    let live = true;
    Promise.all([loadFamily(DISPLAY.family, [DISPLAY.weight]), loadFamily(TEXT.family, [TEXT.weight])])
      .then(async ([d, t]) => {
        await document.fonts.ready;
        if (!d.includes(DISPLAY.family) || !t.includes(TEXT.family)) throw new Error(`kinetic fonts fell back: ${d} / ${t}`);
        if (live) setFaces({ display: metrics(d, DISPLAY.weight), text: metrics(t, TEXT.weight) });
      })
      .finally(() => continueRender(handle));
    return () => { live = false; };
  }, [handle]);
  return faces;
};

/** A figure as shown: a currency sign before, the body ("340", "4.5K"), a % after. K, M and B stay in the body at
 *  full size; € $ £ and % are set smaller, cap-aligned (PREFIX_K, PERCENT_K). */
export type Figure = { prefix: string; body: string; suffix: string };
export const splitFigure = (s: string): Figure => {
  const m = String(s).trim().match(/^([€$£¥]?)\s*(.*?)\s*(%?)$/u)!;
  return { prefix: m[1], body: m[2], suffix: m[3] };
};
/** The parts of a figure at `size`: each part's size, its x from the figure's left and its width; total width w, and
 *  the ink's left and right edges (il, ir) from the figure's left, to centre it or fit a marker round what is drawn. */
export const figureParts = (f: Face, size: number, track: number, fig: Figure) => {
  const ps = size * PREFIX_K, ss = size * PERCENT_K, gap = size * 0.035;
  const pw = fig.prefix ? runW(f, ps, 0, fig.prefix) : 0, bw = runW(f, size, track, fig.body), sw = fig.suffix ? runW(f, ss, 0, fig.suffix) : 0;
  const bx = pw ? pw + gap : 0, sx = bx + bw + (sw ? gap : 0);
  const first = fig.prefix ? ink(f, ps, 0, fig.prefix) : ink(f, size, track, fig.body);
  const lastInk = fig.suffix ? ink(f, ss, 0, fig.suffix) : ink(f, size, track, fig.body);
  return { ps, ss, px: 0, bx, sx, pw, bw, sw, w: sx + sw, il: first.il, ir: (fig.suffix ? sx : bx) + lastInk.ir };
};
/** The number inside a figure's body, for counters: "4.5K" -> 4.5 with 1 decimal and "K" after it, "1,200" -> 1200
 *  grouped. null when the body holds no number. */
export type Value = { value: number; decimals: number; grouped: boolean; lead: string; tail: string };
export const figureValue = (body: string): Value | null => {
  const m = body.match(/\d[\d,]*(\.\d+)?/);
  if (!m) return null;
  return { value: Number(m[0].replace(/,/g, "")), decimals: m[1] ? m[1].length - 1 : 0, grouped: m[0].includes(","),
    lead: body.slice(0, m.index), tail: body.slice(m.index! + m[0].length) };
};
/** `n` written as `v` writes its number: same decimals, thousands grouped when it was. */
export const writeValue = (n: number, v: Value) => {
  const s = n.toFixed(v.decimals);
  if (!v.grouped) return s;
  const [i, d] = s.split(".");
  return i.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (d ? `.${d}` : "");
};
