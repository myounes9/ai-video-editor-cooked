// stat_stack: 2-4 stats ("12 regulars, €860 this week, 4.8 rating") landing one by one, each on its word, in a
// compact row or stack; it may sit beside a real capture of the same numbers (a dashboard screenshot card in the plan at
// that beat), in whatever part of the face band that card leaves free.
//   - each stat is one unit: its figure pulled on as ink on the marker (1.06 -> 1 settle), its label beside it in
//     tracked caps, the label's last line on the figure's baseline (a two-word label may stand on two lines that span
//     the figure's cap height);
//   - a row runs the units left to right, a stack puts them under each other with the figures right-aligned so the
//     labels share one left edge, columns set each label under its figure (centred, readable size: the chain's columns
//     without connectors); the one that fits the biggest figures wins unless props.layout says;
//   - the earlier figures hand their marker to the foil as the next lands (never to white), the last keeps it; labels
//     rise through their mask no earlier than their figure + 0.15 s; the lockup holds 1.2 s after its last landing.
// props: stats: [{num, label?, at, label_at?}] (2-4), layout?: "row" | "stack" | "columns", beside?: [x, y, w, h] (% of the frame:
//        the box of the capture card it sits beside; plan.py kinetic_links fills it), out_at?, band?, hide_captions?
import React, { useMemo } from "react";
import { prog } from "../motion";
import type { TP } from "../Templates";
import { Box, fitDown, layoutBox } from "./fit";
import { wrap2 } from "./NumberChain";
import { Behind, FigureGlyphs, FoilDefs, LineMask, Lockup, MarkerReveal, Run, Scaled, figureSizes, landedAt, pullOff, pullOn, settleAt,
  stagger } from "./primitives";
import { exitAt, firstLanding, labelStart, useClock } from "./time";
import { Part, Prober, capsRect } from "./probe";
import { BESIDE_GAP, EASE, LABEL, TIME, TRACK } from "./tokens";
import { Faces, figureParts, runW, splitFigure, useFaces } from "./type";

type Stat = { num: string; label?: string; at: number; label_at?: number };
type Layout = "row" | "stack" | "columns";
const LAYOUTS: Layout[] = ["row", "stack", "columns"];
type Rect = { x: number; y: number; w: number; h: number };

/** The stats as drawn: 2-4, each with a figure and a time (a missing time is spread 0.8 s apart, never random). */
export const statItems = (p: Record<string, any>): Stat[] => {
  const stats = Array.isArray(p.stats) ? p.stats : [];
  if (stats.length < 2 || stats.length > 4) throw new Error(`stat_stack needs 2-4 stats, got ${stats.length}`);
  if (p.layout !== undefined && !LAYOUTS.includes(p.layout)) throw new Error(`stat_stack layout "${p.layout}" (${LAYOUTS.join(", ")})`);
  return stats.map((s: any, i: number) => {
    if (s?.num === undefined || s?.num === null || String(s.num).trim() === "") throw new Error(`stat_stack stat ${i} has no num`);
    return { num: String(s.num), label: s.label ? String(s.label) : undefined, at: typeof s.at === "number" ? s.at : 0.1 + i * 0.8,
      label_at: typeof s.label_at === "number" ? s.label_at : undefined };
  });
};

/** Where the stats may go: the face band on the grid, less the capture they sit beside (and a gap round it): the band
 *  above it, below it, left and right of it. The whole band when there is none, it is clear of the band, or it covers
 *  all of it (drawn rather than dropped). */
export const freeRegions = (box: Box, beside: unknown, w: number, h: number): Rect[] => {
  const band = { x: box.left, y: box.top, w: box.width, h: box.height };
  if (!Array.isArray(beside) || beside.length !== 4 || !beside.every((v) => typeof v === "number")) return [band];
  const g = BESIDE_GAP * box.k, [bx, by, bw, bh] = beside as number[];
  const X0 = (bx / 100) * w - g, X1 = ((bx + bw) / 100) * w + g, Y0 = (by / 100) * h - g, Y1 = ((by + bh) / 100) * h + g;
  if (X1 <= box.left || X0 >= box.right || Y1 <= box.top || Y0 >= box.bottom) return [band];
  const free = [
    { x: box.left, y: box.top, w: box.width, h: Math.min(Y0, box.bottom) - box.top },
    { x: box.left, y: Math.max(Y1, box.top), w: box.width, h: box.bottom - Math.max(Y1, box.top) },
    { x: box.left, y: box.top, w: Math.min(X0, box.right) - box.left, h: box.height },
    { x: Math.max(X1, box.left), y: box.top, w: box.right - Math.max(X1, box.left), h: box.height },
  ].filter((r) => r.w > 0 && r.h > 0);
  return free.length ? free : [band];
};

/** A two-line label's lines sit this many label sizes apart; its last line is on the figure's baseline. */
const LEAD = 1.1;

const solve = (F: Faces, stats: Stat[], w: number, h: number, band: unknown, beside: unknown, want?: Layout) => {
  const D = F.display, O = F.text, box = layoutBox(w, h, band), k = box.k, n = stats.length;
  const figs = stats.map((s) => splitFigure(s.num));
  const labels = stats.map((s) => (s.label ?? "").toUpperCase());
  const regions = freeRegions(box, beside, w, h);
  // the stats at figure size S: beside its figure a label as tall as two of its lines spanning the figure's cap
  // height; under it (columns) a label at the chain's readable size
  const units = (S: number, wrap: boolean, under: boolean) => {
    const pad = S * 0.1, gapL = S * (under ? 0.11 : 0.14);
    const Ls = under ? Math.max(LABEL.soft * k, S * LABEL.kMin) : (D.cap * S) / (O.cap + LEAD);
    const parts = figs.map((f) => figureParts(D, S, TRACK.figure, f));
    const lines = labels.map((l) => (!l ? [] : wrap ? wrap2(l) : [l]));
    const mW = parts.map((g) => g.ir - g.il + 2 * pad);
    const labW = lines.map((ls) => Math.max(0, ...ls.map((x) => runW(O, Ls, TRACK.label, x))));
    const uW = mW.map((m, i) => (under ? Math.max(m, labW[i]) : m + (labW[i] ? gapL + labW[i] : 0)));
    const rows = Math.max(0, ...lines.map((x) => x.length));
    return { pad, Ls, gapL, parts, lines, mW, labW, mH: D.cap * S + 2 * pad, uW, labH: rows ? gapL + O.cap * Ls + (rows - 1) * Ls * LEAD : 0 };
  };
  const at = (S: number, wrap: boolean, lay: Layout, R: Rect) => {
    const u = units(S, wrap, lay === "columns");
    const colGap = Math.max(44 * k, S * 0.34), rowGap = S * 0.14;
    const W = lay === "stack" ? Math.max(...u.mW) + u.gapL + Math.max(...u.labW) : u.uW.reduce((a, b) => a + b, 0) + (n - 1) * colGap;
    const H = lay === "row" ? u.mH : lay === "columns" ? u.mH + u.labH : n * u.mH + (n - 1) * rowGap;
    return { ok: W <= R.w && H <= R.h, ...u, colGap, rowGap, W, H, lay, R };
  };
  // the biggest figures over every free region, layout and label wrap (a row before a stack, one line before two)
  let best: ReturnType<typeof at> & { size: number } | null = null;
  for (const R of regions) {
    for (const lay of want ? [want] : LAYOUTS) {
      for (const wrap of labels.some((l) => l.includes(" ")) ? [false, true] : [false]) {
        const f = fitDown(240 * k, 56 * k, 2 * k, (S) => at(S, wrap, lay, R));
        if (f.ok && (!best || !best.ok || f.size > best.size)) best = f;
        else if (!best) best = f;
      }
    }
  }
  const L = best!, S = L.size;
  // placed centred across its region, hanging from its top (as close to the header and as far from the eyes as it goes)
  const x0 = L.R.x + (L.R.w - L.W) / 2, y0 = L.R.y;
  const colR = x0 + Math.max(...L.mW);
  let cx = x0;
  const mk = stats.map((_, i) => {
    let a: number, top: number, lc = 0;
    if (L.lay === "row") { a = cx; top = y0; cx += L.uW[i] + L.colGap; }
    else if (L.lay === "columns") { lc = cx + L.uW[i] / 2; a = lc - L.mW[i] / 2; top = y0; cx += L.uW[i] + L.colGap; }
    else { a = colR - L.mW[i]; top = y0 + i * (L.mH + L.rowGap); }
    const base = top + L.pad + D.cap * S;
    // lb: a label's first baseline (under its figure in columns, else its last line on the figure's baseline); lc: the
    // centre each of its lines is set on in columns
    const lb = L.lay === "columns" ? top + L.mH + L.gapL + O.cap * L.Ls : base - (L.lines[i].length - 1) * L.Ls * LEAD;
    return { a, b: a + L.mW[i], top, bot: top + L.mH, base, fx: a + L.pad - L.parts[i].il, lx: a + L.mW[i] + L.gapL, lb, lc };
  });
  return { ...L, S, box, k, figs, mk, x0, y0 };
};

/** The layout as rectangles (kinetic/probe.ts). */
export const probe: Prober = (F, p, w, h, dur) => {
  const stats = statItems(p), L = solve(F, stats, w, h, p.band, p.beside, p.layout), O = F.text, D = F.display;
  firstLanding("stat_stack", stats[0].at, dur);
  const parts: Part[] = [];
  stats.forEach((_, i) => {
    const M = L.mk[i];
    parts.push({ kind: "figure", r: [M.fx + L.parts[i].il, M.base - D.cap * L.S, M.fx + L.parts[i].ir, M.base] });
    L.lines[i].forEach((line, li) => {
      const lw = runW(O, L.Ls, TRACK.label, line);
      parts.push({ kind: "label", r: capsRect(L.lay === "columns" ? M.lc - lw / 2 : M.lx, lw, M.lb + li * L.Ls * LEAD, O.cap * L.Ls) });
    });
  });
  return { k: L.k, parts, sizes: { figure: L.S, label: L.Ls } };
};

const Stack: React.FC<TP & { F: Faces }> = ({ p, w, h, dur, id, F }) => {
  const { t, dt, fps } = useClock();
  const stats = useMemo(() => statItems(p), [JSON.stringify(p.stats), p.layout]);
  const L = useMemo(() => solve(F, stats, w, h, p.band, p.beside, p.layout), [F, stats, w, h, JSON.stringify(p.band), JSON.stringify(p.beside), p.layout]);
  const D = F.display, O = F.text, S = L.S, k = L.k, n = stats.length;
  useMemo(() => firstLanding("stat_stack", stats[0].at, dur), [stats, dur]);
  const labT = stats.map((s) => labelStart(s.at, s.label_at));
  const labDist = O.cap * L.Ls * 1.3;
  const labLanded = stats.map((_, i) => landedAt(labT[i], L.lines[i].join("").length));
  const last = Math.max(...stats.map((s, i) => Math.max(s.at, L.lines[i].length ? labLanded[i] : 0)));
  const out = exitAt(dur, last, p.out_at);
  return (
    <Lockup t={t} t0={stats[0].at - TIME.lead} out={out} box={L.box} oy={L.y0} ox={L.x0 + L.W / 2} w={w} h={h} bridge={p}>
      <FoilDefs id={id} sizes={L.figs.flatMap((f) => figureSizes(f, S))} />
      {stats.map((s, i) => {
        const M = L.mk[i];
        const on = pullOn(t, M.a, M.b, L.mH, s.at - TIME.lead);
        // the marker leaves as the next stat comes; the last one keeps it
        const hand = i < n - 1 ? stats[i + 1].at - TIME.handoffLead : Infinity;
        const m = pullOff(on, M.b, t, hand);
        const sheen = i < n - 1 ? prog(t, hand + TIME.handoff + 0.04, TIME.sheenDur, EASE.sheen) : -1;
        return (
          <React.Fragment key={i}>
            <Behind a={m.a} off={m.off} h={h}>
              <FigureGlyphs fig={L.figs[i]} face={D} size={S} track={TRACK.figure} x={M.fx} base={M.base} paint="gold" id={id} sheen={sheen} />
            </Behind>
            <MarkerReveal m={m} y0={M.top} y1={M.bot} id={`${id}-m${i}`} w={w} h={h}>
              <Scaled s={settleAt(t, s.at - TIME.lead, fps)} ox={M.fx} oy={M.base}>
                <FigureGlyphs fig={L.figs[i]} face={D} size={S} track={TRACK.figure} x={M.fx} base={M.base} paint="ink" />
              </Scaled>
            </MarkerReveal>
          </React.Fragment>
        );
      })}
      {stats.map((_, i) => {
        const M = L.mk[i], ls = L.lines[i];
        if (!ls.length) return null;
        const cols = L.lay === "columns";
        return (
          <LineMask key={i} on={t < labLanded[i]} y0={M.lb - O.cap * L.Ls - 10 * k} y1={M.lb + (ls.length - 1) * L.Ls * LEAD + 10 * k}>
            {ls.map((line, li) => {
              const before = ls.slice(0, li).join("").length;   // the stagger runs on across the lines
              return (
                <Run key={li} text={line} face={O} size={L.Ls} track={TRACK.label} x={cols ? M.lc - runW(O, L.Ls, TRACK.label, line) / 2 : M.lx}
                  base={M.lb + li * L.Ls * LEAD} paint="white"
                  rise={stagger(labT[i] + before * TIME.stagger, TIME.stagger, TIME.rise, labDist)} t={t} dt={dt} id={`${id}-l${i}-${li}`} k={k} />
              );
            })}
          </LineMask>
        );
      })}
    </Lockup>
  );
};

export const StatStack: React.FC<TP> = (props) => {
  const F = useFaces();
  return F ? <Stack {...props} F={F} /> : null;
};
