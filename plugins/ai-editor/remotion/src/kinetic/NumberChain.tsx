// number_chain: 2-4 figures that lead one to the next ("340 flyers -> 6 tastings -> 1 cafe"), each landing on its
// spoken word. The reference template of the kinetic family: the other formats copy its shape (props, clock, fit,
// lockup, paint). references/kinetic.md has the props; tokens.ts every size, colour and time.
//   - fixed columns solved once for the whole chain and centred on the grid: nothing moves when a figure lands;
//     every connector has the same length, never shorter than its minimum; a label may overhang its column, never
//     closer than 40 px to the next; labels stay at a phone-readable size (they wrap before they shrink); the row is
//     centred on its ink, figures and labels. A chain that cannot fit so at the smallest figure size throws (check.py
//     plan flags it first: use a stat_stack);
//   - each figure is pulled on as ink on a highlighter marker on its word (1.06 -> 1 settle); the connector to the
//     next draws just before the next lands; when the next is coming the marker is pulled off its figure and hands it
//     to the foil (a stacked layer, never a colour blend), so every figure stays key-coloured; the last keeps its marker;
//   - labels rise through their mask no earlier than their figure + 0.15 s;
//   - the lockup holds at least 1.2 s after its last landing (unless the card ends sooner), pushes 1.5 %, and leaves
//     in one feathered sweep.
// props: items: [{num, label?, at, label_at?}] (2-4; times in seconds after the card starts), out_at?, band?
//        ([top, bottom] % of the frame height, from face.json), hide_captions? (default true: StyleEdit.tsx).
import React, { useMemo } from "react";
import { prog } from "../motion";
import type { TP } from "../Templates";
import { layoutBox, fitDown } from "./fit";
import { Arrow, Behind, FigureGlyphs, FoilDefs, LineMask, MarkerReveal, Lockup, Run, Scaled, figureSizes, landedAt, pullOff, pullOn, settleAt,
  stagger } from "./primitives";
import { exitAt, firstLanding, labelStart, useClock } from "./time";
import { Part, Prober, capsRect } from "./probe";
import { EASE, LABEL, TIME, TRACK } from "./tokens";
import { Faces, figureParts, runW, splitFigure, useFaces } from "./type";

type Item = { num: string; label?: string; at: number; label_at?: number };

/** The items as drawn: 2-4, each with a figure and a time (a missing time is spread 0.8 s apart, never random). */
export const chainItems = (p: Record<string, any>): Item[] => {
  const items = Array.isArray(p.items) ? p.items : [];
  if (items.length < 2 || items.length > 4) throw new Error(`number_chain needs 2-4 items, got ${items.length}`);
  return items.map((it: any, i: number) => {
    if (it?.num === undefined || it?.num === null || String(it.num).trim() === "") throw new Error(`number_chain item ${i} has no num`);
    return { num: String(it.num), label: it.label ? String(it.label) : undefined, at: typeof it.at === "number" ? it.at : 0.1 + i * 0.8,
      label_at: typeof it.label_at === "number" ? it.label_at : undefined };
  });
};

/** A label on two lines, split at the space nearest its middle (one word stays whole). */
export const wrap2 = (l: string) => {
  const sp = [...l.matchAll(/ /g)].map((m) => m.index!);
  if (!sp.length) return [l];
  const at = sp.reduce((a, b) => (Math.abs(b - l.length / 2) < Math.abs(a - l.length / 2) ? b : a));
  return [l.slice(0, at), l.slice(at + 1)];
};
/** Label lines sit this many label sizes apart when a label wraps. */
const LEAD = 1.1;

/** The smallest figure size a chain is drawn at (px at 1080): below it the figures stop reading as the hero. */
const MIN_S = 64;

const solve = (F: Faces, items: Item[], w: number, h: number, band: unknown, beside: unknown) => {
  const D = F.display, O = F.text, box = layoutBox(w, h, band, beside), k = box.k, n = items.length;
  // an outer label may reach this far past the grid, less what the slow push adds at the grid's edge
  const over = LABEL.over * k - TIME.push * (box.width / 2 + LABEL.over * k);
  const figs = items.map((it) => splitFigure(it.num));
  const labels = items.map((it) => (it.label ?? "").toUpperCase());
  const clear = 24 * k, labGap = 40 * k;
  // the chain at figure size S: its labels as big as fit between k x S (at least LABEL.size) and kMin x S (at least
  // `floor`), each on one line or wrapped onto two
  const at = (S: number, floor: number, wrap: boolean) => {
    const padX = S * 0.1, padY = S * 0.1;
    const parts = figs.map((f) => figureParts(D, S, TRACK.figure, f));
    const lines = labels.map((l) => (!l ? [] : wrap ? wrap2(l) : [l]));
    const mW = parts.map((g) => g.ir - g.il + 2 * padX);   // the marker hugs the ink, not the advance
    const span = items.slice(1).map((_, j) => mW[j] / 2 + mW[j + 1] / 2 + 2 * clear);   // centre to centre, less the connector
    const minA = Math.max(64 * k, S * 0.3);
    // one connector length for the whole chain: what the labels need, at least minA, ideally S/2, at most what fits
    const layoutAt = (Ls: number) => {
      const labW = lines.map((ls) => Math.max(0, ...ls.map((x) => runW(O, Ls, TRACK.label, x))));
      // an outer label may reach LABEL.over past the grid; a figure never does
      const ext = items.map((_, i) => Math.max(mW[i] / 2, labW[i] / 2 - (i === 0 || i === n - 1 ? over : 0)));
      const need = Math.max(0, ...items.slice(1).map((_, j) => labW[j] / 2 + labGap + labW[j + 1] / 2 - span[j]));
      const free = (box.width - ext[0] - ext[n - 1] - span.reduce((a, b) => a + b, 0)) / (n - 1);
      const A = Math.min(free, Math.max(need, minA, S * 0.5));
      const rows = Math.max(0, ...lines.map((x) => x.length));
      const mH = D.cap * S + 2 * padY, gapL = S * 0.11;
      const totalH = mH + (rows ? gapL + O.cap * Ls + (rows - 1) * Ls * LEAD : 0);
      return { ok: free >= Math.max(need, minA) && totalH <= box.height, Ls, labW, ext, A, mH, gapL, minA, need, free };
    };
    const hi = Math.max(LABEL.size * k, S * LABEL.k), lo = Math.min(hi, Math.max(floor * k, S * LABEL.kMin));
    let g = layoutAt(hi);
    for (let Ls = hi - 2 * k; Ls >= lo - 1e-6 && !g.ok; Ls -= 2 * k) g = layoutAt(Ls);
    return { ...g, padX, padY, parts, lines, mW, span };
  };
  // labels at LABEL.soft or more before LABEL.floor (legibility first); at each, the biggest figures with the labels on
  // one line, or wrapped onto two when that makes the figures clearly bigger. Never two labels closer than labGap,
  // never a connector under its minimum, never a figure past the grid: a chain that fits none of these at MIN_S throws
  // rather than draw figures into each other.
  const words = labels.some((l) => l.includes(" "));
  const fits = [LABEL.soft, LABEL.floor].map((floor) => (words ? [false, true] : [false])
    .map((wrap) => fitDown(320 * k, MIN_S * k, 2 * k, (S) => at(S, floor, wrap))).filter((f) => f.ok)
    .reduce<ReturnType<typeof at> & { size: number } | undefined>((best, f) => (!best || f.size > best.size * 1.15 ? f : best), undefined));
  const fit = fits[0] ?? fits[1];
  if (!fit) {
    const g = at(MIN_S * k, LABEL.floor, words);
    throw new Error(`number_chain: ${items.map((it) => `${it.num}${it.label ? ` ${it.label}` : ""}`).join(" -> ")} does not fit across the ` +
      `grid with equal connectors and readable labels (figures at ${MIN_S} px or more; ${Math.round((n - 1) * (Math.max(g.need, g.minA) - g.free))} px ` +
      "short): use a stat_stack, shorter labels or fewer items");
  }
  const S = fit.size;
  const d = fit.span.map((b) => b + fit.A);
  const total = fit.ext[0] + d.reduce((a, b) => a + b, 0) + fit.ext[n - 1];
  const centres = [box.left + (box.width - total) / 2 + fit.ext[0]];
  d.forEach((dj) => centres.push(centres[centres.length - 1] + dj));
  // centred on what it draws: a long outer label on one side only ("1 ... WHOLESALER") pulled the row off centre and past
  // the side margin; the row slides to centre its ink, a figure never past the grid and a label never past LABEL.over
  const half = items.map((_, i) => Math.max(fit.mW[i] / 2, fit.labW[i] / 2));
  const inkL = Math.min(...centres.map((c, i) => c - half[i])), inkR = Math.max(...centres.map((c, i) => c + half[i]));
  const lo = Math.max(box.left - centres[0] + fit.mW[0] / 2, box.left - over - inkL);
  const hi = Math.min(box.left + box.width - centres[n - 1] - fit.mW[n - 1] / 2, box.left + box.width + over - inkR);
  const shift = Math.min(hi, Math.max(lo, box.left + box.width / 2 - (inkL + inkR) / 2));
  if (lo <= hi) centres.forEach((_, i) => { centres[i] += shift; });
  const mTop = box.top, capTop = mTop + fit.padY, base = capTop + D.cap * S, mBot = base + fit.padY;
  const lBase = mBot + fit.gapL + O.cap * fit.Ls;
  return { ...fit, S, box, k, figs, labels, clear, centres, mTop, capTop, base, mBot, lBase,
    mk: items.map((_, i) => ({ a: centres[i] - fit.mW[i] / 2, b: centres[i] + fit.mW[i] / 2 })) };
};

/** The connector's stroke and head (px): heavy enough to read on a phone. */
const arrowSize = (S: number, k: number) => ({ sw: Math.max(10 * k, S * 0.052), hl: Math.max(22 * k, S * 0.115) });

/** The layout as rectangles (kinetic/probe.ts). */
export const probe: Prober = (F, p, w, h, dur) => {
  const items = chainItems(p), L = solve(F, items, w, h, p.band, p.beside), D = F.display, O = F.text;
  firstLanding("number_chain", items[0].at, dur);
  const parts: Part[] = [];
  const { sw } = arrowSize(L.S, L.k), midY = L.capTop + D.cap * L.S * 0.5;
  items.forEach((it, i) => {
    const fx = L.centres[i] - (L.parts[i].il + L.parts[i].ir) / 2;
    parts.push({ kind: "figure", r: [fx + L.parts[i].il, L.capTop, fx + L.parts[i].ir, L.base] });
    L.lines[i].forEach((line, li) => {
      const lw = runW(O, L.Ls, TRACK.label, line);
      parts.push({ kind: "label", r: capsRect(L.centres[i] - lw / 2, lw, L.lBase + li * L.Ls * LEAD, O.cap * L.Ls) });
    });
    if (i) parts.push({ kind: "arrow", r: [L.mk[i - 1].b + L.clear, midY - sw / 2, L.mk[i].a - L.clear, midY + sw / 2], min: L.minA });
  });
  return { k: L.k, parts, sizes: { figure: L.S, label: L.Ls } };
};

const Chain: React.FC<TP & { F: Faces }> = ({ p, w, h, dur, id, F }) => {
  const { t, dt, fps } = useClock();
  const items = useMemo(() => chainItems(p), [JSON.stringify(p.items)]);
  const L = useMemo(() => solve(F, items, w, h, p.band, p.beside), [F, items, w, h, JSON.stringify(p.band), JSON.stringify(p.beside)]);
  const D = F.display, O = F.text, S = L.S, k = L.k, n = items.length;
  // labels: each rises through its own mask, no earlier than its figure + TIME.labelAfter
  const labT = items.map((it) => labelStart(it.at, it.label_at));
  const labDist = O.cap * L.Ls * 1.3;
  const labLanded = items.map((it, i) => landedAt(labT[i], L.lines[i].join("").length));
  const last = Math.max(...items.map((it, i) => Math.max(it.at, L.lines[i].length ? labLanded[i] : 0)));
  const out = exitAt(dur, last, p.out_at);
  const t0 = items[0].at - TIME.lead;
  const midY = L.capTop + D.cap * S * 0.5;
  const { sw, hl } = arrowSize(S, k);
  useMemo(() => firstLanding("number_chain", items[0].at, dur), [items, dur]);
  return (
    <Lockup t={t} t0={t0} out={out} box={L.box} oy={L.mTop} w={w} h={h} bridge={p}>
      <FoilDefs id={id} sizes={L.figs.flatMap((f) => figureSizes(f, S))} />
      {/* connectors: each drawn from figure to figure just before the next one lands */}
      <svg width={w} height={h} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        {items.slice(1).map((it, j) => (
          <Arrow key={j} x0={L.mk[j].b + L.clear} x1={L.mk[j + 1].a - L.clear} y={midY} sw={sw} hl={hl} k={k}
            p={prog(t, it.at - TIME.connectorLead, TIME.connectorDur, EASE.draw)} />
        ))}
      </svg>
      {items.map((it, i) => {
        const fx = L.centres[i] - (L.parts[i].il + L.parts[i].ir) / 2;   // the ink centred in its column
        const on = pullOn(t, L.mk[i].a, L.mk[i].b, L.mH, it.at - TIME.lead);
        // the marker leaves as the next figure comes; the last one keeps it
        const hand = i < n - 1 ? items[i + 1].at - TIME.handoffLead : Infinity;
        const m = pullOff(on, L.mk[i].b, t, hand);
        const sc = settleAt(t, it.at - TIME.lead, fps);
        const sheen = i < n - 1 ? prog(t, hand + TIME.handoff + 0.04, TIME.sheenDur, EASE.sheen) : -1;
        return (
          <React.Fragment key={i}>
            <Behind a={m.a} off={m.off} h={h}>
              <FigureGlyphs fig={L.figs[i]} face={D} size={S} track={TRACK.figure} x={fx} base={L.base} paint="gold" id={id} sheen={sheen} />
            </Behind>
            <MarkerReveal m={m} y0={L.mTop} y1={L.mBot} id={`${id}-m${i}`} w={w} h={h}>
              <Scaled s={sc} ox={fx} oy={L.base}>
                <FigureGlyphs fig={L.figs[i]} face={D} size={S} track={TRACK.figure} x={fx} base={L.base} paint="ink" />
              </Scaled>
            </MarkerReveal>
          </React.Fragment>
        );
      })}
      {items.map((it, i) => L.lines[i].length ? (
        <LineMask key={i} on={t < labLanded[i]} y0={L.lBase - O.cap * L.Ls - 10 * k} y1={L.lBase + (L.lines[i].length - 1) * L.Ls * LEAD + 10 * k}>
          {L.lines[i].map((line, li) => {
            const before = L.lines[i].slice(0, li).join("").length;   // the stagger runs on across the lines
            return (
              <Run key={li} text={line} face={O} size={L.Ls} track={TRACK.label} x={L.centres[i] - runW(O, L.Ls, TRACK.label, line) / 2}
                base={L.lBase + li * L.Ls * LEAD} paint="white" rise={stagger(labT[i] + before * TIME.stagger, TIME.stagger, TIME.rise, labDist)}
                t={t} dt={dt} id={`${id}-l${i}-${li}`} k={k} />
            );
          })}
        </LineMask>
      ) : null)}
    </Lockup>
  );
};

export const NumberChain: React.FC<TP> = (props) => {
  const F = useFaces();
  return F ? <Chain {...props} F={F} /> : null;
};
