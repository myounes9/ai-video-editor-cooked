// goal_bar: where the speaker is on the way to a goal ("40% of a 20K goal"), the goal layout without a panel
// (references/kinetic.md; tokens.ts GOAL). Shape copied from NumberChain.tsx.
//   - the % on the left is the key figure: pulled on as ink on its highlighter marker on its word (1.06 -> 1 settle),
//     counting from 40 % of its value (never a 0) to land on its count word; its % at 0.56x, cap-aligned;
//   - the target sits on the same baseline at the right edge of the grid, in foil, under a small GOAL label, sized so
//     the label's cap top meets the figure's: the right column is exactly as tall as the figure;
//   - under both, a pill track the width of the grid: its well (the remainder) draws along its length with the pull,
//     its fill runs with the count (the same window, so digits and bar arrive together) and flares for 6 frames on the
//     first frame the count reads final; a target marker at its end pops on the target's word and sends two rings
//     out on "goal";
//   - the label rises no earlier than the target + 0.15 s; the lockup holds 1.2 s after its last landing (unless the
//     card ends sooner), pushes 1.5 % and leaves in one feathered sweep.
// props: pct ("50%", or 50), target ("20K", "€20K"), at_pct (or at), count_at?, at_target, at_goal?, label? ("GOAL"),
//        out_at?, band? ([top, bottom] % of the frame height), hide_captions? (default true). Times: seconds after the
//        card starts.
import React, { useMemo } from "react";
import { prog } from "../motion";
import type { TP } from "../Templates";
import { layoutBox, fitDown } from "./fit";
import { BlurDefs, FigureGlyphs, FoilDefs, Glyphs, LineMask, Lockup, MarkerReveal, Odometer, Run, Scaled, f2, figureSizes, landedAt, lerp,
  moving, odometerLayout, pullOn, settleAt, sid, stagger } from "./primitives";
import { counter, exitAt, firstLanding, labelStart, useClock } from "./time";
import { Prober, capsRect, countProbe } from "./probe";
import { EASE, GOAL, KEY, LABEL, PERCENT_K, TIME, TRACK } from "./tokens";
import { Faces, Value, adv, figureParts, figureValue, ink, runW, signBase, splitFigure, useFaces } from "./type";

type Goal = { pct: string; v: Value; target: string; label: string; at: number; count_at: number; at_target: number; at_goal?: number };

/** A length for a style prop, to 0.01 px (a number: React adds the px). */
const px = (n: number) => Math.round(n * 100) / 100;
const num = (x: unknown) => (typeof x === "number" && Number.isFinite(x) ? x : undefined);
/** The props as drawn. pct: a percentage ("50%", "12.5%", or a bare 50); target: the goal as shown ("20K", "€20K").
 *  Missing times follow the figure (target 1 s after it, never random). */
export const goalProps = (p: Record<string, any>): Goal => {
  const raw = p.pct;
  if (raw === undefined || raw === null || String(raw).trim() === "") throw new Error('goal_bar needs pct (a percentage like "50%")');
  const fig = splitFigure(`${String(raw).trim().replace(/\s*%$/, "")}%`);
  if (fig.prefix || !/^\d[\d,]*(\.\d+)?$/.test(fig.body)) throw new Error(`goal_bar pct must be a percentage like "50%", got ${JSON.stringify(raw)}`);
  if (p.target === undefined || p.target === null || String(p.target).trim() === "") throw new Error('goal_bar needs target (the goal as shown, like "20K")');
  const at = num(p.at_pct) ?? num(p.at) ?? 0.1;
  return { pct: `${fig.body}%`, v: figureValue(fig.body)!, target: String(p.target).trim(), label: String(p.label ?? "GOAL"), at,
    count_at: Math.max(at, num(p.count_at) ?? at + GOAL.countAfter), at_target: num(p.at_target) ?? at + 1, at_goal: num(p.at_goal) };
};

const solve = (F: Faces, g: Goal, w: number, h: number, band: unknown, beside: unknown) => {
  // one module, never wider than the grid of a vertical frame: on a wide frame (where the band, not the width, sets
  // the size) it keeps its vertical proportions, centred on the grid, rather than a hairline track across the frame
  const g0 = layoutBox(w, h, band, beside), k = g0.k, gw = Math.min(g0.width, GOAL.maxW * k), gl = g0.left + (g0.width - gw) / 2;
  const D = F.display, O = F.text, box = { ...g0, left: gl, right: gl + gw, width: gw };
  const tgt = splitFigure(g.target), label = g.label.toUpperCase();
  // the lockup at figure size S: the % figure on its marker at the grid's left, the target and its label at the right,
  // the track under both across the grid
  const at = (S: number) => {
    const padX = S * 0.1, padY = S * 0.1;
    const ol = odometerLayout(D, S, g.v), ss = S * PERCENT_K, sx = ol.w + S * 0.035;
    const c0 = ol.cells[0], d0 = c0.ch;   // the first digit sits centred in its tabular cell
    const il = c0.x + (c0.w - adv(D, S, 0, d0)) / 2 + ink(D, S, 0, d0).il, ir = sx + ink(D, ss, 0, "%").ir;
    const mW = ir - il + 2 * padX, mH = D.cap * S + 2 * padY;   // the marker hugs the ink
    const Ls = Math.max(LABEL.floor * k, Math.min(LABEL.size * k, S * LABEL.k)), gapL = Ls * 0.5;
    const T = (D.cap * S - gapL - O.cap * Ls) / D.cap;   // label cap top on the figure's cap top
    const tp = figureParts(D, T, TRACK.figure, tgt), tW = tp.ir - tp.il, lW = runW(O, Ls, TRACK.label, label);
    const TH = Math.max(GOAL.minH * k, S * GOAL.h), MD = TH * GOAL.discK, trackTop = box.top + mH + S * GOAL.gap;
    const ok = T > 0 && mW + Math.max(40 * k, S * 0.22) + Math.max(tW, lW) <= box.width && trackTop + TH / 2 + MD / 2 <= box.bottom;
    return { ok, padX, padY, ol, ss, sx, il, mW, mH, Ls, gapL, T, tp, lW, TH, MD, trackTop };
  };
  const fit = fitDown(320 * k, 90 * k, 2 * k, at);
  const S = fit.size, mTop = box.top, capTop = mTop + fit.padY, base = capTop + D.cap * S;
  return { ...fit, S, box, k, tgt, label, mTop, capTop, base, mBot: base + fit.padY,
    fx: box.left + fit.padX - fit.il,                    // the figure's origin: its ink padX inside the marker
    tx: box.right - fit.tp.ir,                           // the target's ink ends on the grid's right edge
    lBase: base - D.cap * fit.T - fit.gapL, lx: box.right - fit.lW,
    dcx: box.right - fit.TH / 2, dcy: fit.trackTop + fit.TH / 2 };   // the marker on the track's end cap
};

/** The count runs from the pull and first reads final on its count word: its window is stretched so it does. */
const countDur = (g: Goal) => Math.max(0.2, (g.count_at - (g.at - TIME.lead)) / Math.max(0.05, counter(0, g.v.value, g.v.decimals, 0, 1, 1000).land));

/** The layout as rectangles and the count frame by frame (kinetic/probe.ts). */
export const probe: Prober = (F, p, w, h, dur, fps) => {
  const g = goalProps(p), L = solve(F, g, w, h, p.band, p.beside), D = F.display, O = F.text, t0 = g.at - TIME.lead;
  firstLanding("goal_bar", g.at, dur);
  const c = counter(0, g.v.value, g.v.decimals, t0, countDur(g), fps);
  const tg = L.tp;
  return { k: L.k, sizes: { figure: L.S, label: L.Ls }, counts: [countProbe(c.val, g.v, t0, c.land, dur, fps)], parts: [
    { kind: "figure", r: [L.box.left + L.padX, L.capTop, L.box.left + L.mW - L.padX, L.base] },
    { kind: "figure", r: [L.tx + tg.il, L.base - D.cap * L.T, L.tx + tg.ir, L.base] },
    { kind: "label", r: capsRect(L.lx, L.lW, L.lBase, O.cap * L.Ls) },
    { kind: "track", r: [L.box.left, L.trackTop, L.box.right, L.trackTop + L.TH] },
  ] };
};

const Bar: React.FC<TP & { F: Faces }> = ({ p, w, h, dur, id, F }) => {
  const { t, dt, fps } = useClock();
  const g = useMemo(() => goalProps(p), [p.pct, p.target, p.label, p.at_pct, p.at, p.count_at, p.at_target, p.at_goal]);
  const L = useMemo(() => solve(F, g, w, h, p.band, p.beside), [F, g, w, h, JSON.stringify(p.band), JSON.stringify(p.beside)]);
  useMemo(() => firstLanding("goal_bar", g.at, dur), [g, dur]);
  const D = F.display, O = F.text, S = L.S, k = L.k, T = L.T, TH = L.TH, W = L.box.width;
  const t0 = g.at - TIME.lead;
  const cd = useMemo(() => countDur(g), [g]);
  const c = counter(t, g.v.value, g.v.decimals, t0, cd, fps);
  // the figure on its marker, settling as it is pulled on; it keeps its marker
  const mk = pullOn(t, L.box.left, L.box.left + L.mW, L.mH, t0);
  const sc = settleAt(t, t0, fps);
  // the track: the well draws along its length, the fill runs with the count, the glow band flares on the landing
  const pw = prog(t, t0 + 0.04, GOAL.draw, EASE.draw), wellW = lerp(TH, W, pw);
  const fillW = Math.min(wellW, Math.max(TH, (W * Math.min(100, c.value)) / 100));
  const flare = t >= c.land ? 1 - prog(t, c.land, GOAL.flareFrames / fps, "power2.out") : 0;
  const glowA = Math.max(lerp(GOAL.glowRest, GOAL.glowRun, 1 - prog(t, c.land, 0.3, "power2.out")), lerp(GOAL.glowRest, GOAL.glowFlare, flare));
  const G = TH * 0.85, glow = (a: number) => `rgba(${GOAL.glow},${f2(a)})`;
  // the target rises through its mask on its word, then one sheen crosses it
  const tIn = g.at_target - TIME.lead, tLanded = tIn + TIME.rise * 0.8;
  const rise = moving(t, dt, (u) => D.cap * T * 0.9 * (1 - prog(u, tIn, TIME.rise, EASE.rise)), k);
  const tBlur = `${sid(id)}-tb`;
  // the marker pops on the target's word; the label rises no earlier than the target + 0.15 s; two rings on "goal"
  const pop = prog(t, g.at_target - 0.04, GOAL.pop, GOAL.popEase), d = L.MD * pop;
  const labT = labelStart(g.at_target, g.at_goal), labLanded = landedAt(labT, L.label.length);
  const ringAt = g.at_goal ?? labT + 0.04;
  const dotKey = prog(t, ringAt, 3 / fps, "linear");   // a stacked key dot over the white one, never a colour blend
  const ringW = Math.max(2 * k, L.MD * 0.075);
  const out = exitAt(dur, Math.max(c.land, tLanded, labLanded), p.out_at);
  return (
    <Lockup t={t} t0={t0} out={out} box={L.box} oy={L.mTop} w={w} h={h} bridge={p}>
      <FoilDefs id={id} sizes={figureSizes(L.tgt, T)} />
      <BlurDefs defs={rise.sig > 0 ? [{ id: tBlur, sy: rise.sig }] : []} />
      {pw > 0 ? (
        <div style={{ position: "absolute", left: L.box.left, top: L.trackTop, width: W, height: TH }}>
          {/* the well: its remainder always shows; a 1 px edge in alpha and a gradient shade under its top lip */}
          <div style={{ position: "absolute", left: 0, top: 0, width: px(wellW), height: TH, borderRadius: TH, boxSizing: "border-box",
            border: `${f2(Math.max(1, k))}px solid ${GOAL.edge}`,
            background: `linear-gradient(180deg, ${GOAL.shade} 0px, rgba(0,0,0,0.12) ${f2(TH * 0.16)}px, rgba(0,0,0,0) ${f2(TH * 0.3)}px), linear-gradient(${GOAL.well}, ${GOAL.well}), ${GOAL.under}` }} />
          {/* the glow band behind the fill: a gradient feathered at both ends, never a box-shadow */}
          <div style={{ position: "absolute", left: -G, top: -G, width: px(fillW + 2 * G), height: TH + 2 * G,
            background: `linear-gradient(180deg, ${glow(0)} 0%, ${glow(glowA)} 42%, ${glow(glowA)} 58%, ${glow(0)} 100%)`,
            maskImage: `linear-gradient(90deg, transparent 0px, #000 ${f2(G)}px, #000 calc(100% - ${f2(G)}px), transparent 100%)`,
            WebkitMaskImage: `linear-gradient(90deg, transparent 0px, #000 ${f2(G)}px, #000 calc(100% - ${f2(G)}px), transparent 100%)` } as React.CSSProperties} />
          <div style={{ position: "absolute", left: 0, top: 0, width: px(fillW), height: TH, borderRadius: TH,
            background: `linear-gradient(180deg, ${GOAL.fillTop} 0%, ${KEY} 38%, ${KEY} 100%)` }} />
        </div>
      ) : null}
      {/* the target marker on the track's end: sized as it pops (never scaled), its rings fade in their border's alpha */}
      {[0, GOAL.ringGap / fps].map((off, j) => {
        const pr = prog(t, ringAt + off, GOAL.ring, "power2.out"), r = (L.MD / 2) * lerp(1, GOAL.ringOut, pr);
        return pr > 0 && pr < 1 ? <div key={j} style={{ position: "absolute", left: px(L.dcx - r), top: px(L.dcy - r), width: px(2 * r), height: px(2 * r),
          borderRadius: "50%", boxSizing: "border-box", border: `${f2(ringW)}px solid ${glow(0.9 * (1 - pr))}` }} /> : null;
      })}
      {d > 0.5 ? (
        <div style={{ position: "absolute", left: px(L.dcx - d / 2), top: px(L.dcy - d / 2), width: px(d), height: px(d), borderRadius: "50%",
          boxSizing: "border-box", background: GOAL.discFill, border: `${f2(ringW * Math.min(1, pop))}px solid ${GOAL.rim}` }}>
          {[GOAL.rim, dotKey > 0 ? glow(dotKey) : ""].filter(Boolean).map((bg, j) => (
            <div key={j} style={{ position: "absolute", left: "32%", top: "32%", width: "36%", height: "36%", borderRadius: "50%", background: bg }} />
          ))}
        </div>
      ) : null}
      {/* the target, on the figure's baseline, rising out of its mask on its word */}
      {t >= tIn - dt * 0.5 ? (
        <LineMask on={t < tLanded} y0={L.base - D.cap * T - 0.12 * T} y1={L.base + 0.08 * T}>
          <div style={{ position: "absolute", inset: 0, transform: Math.abs(rise.y) > 1e-3 ? `translateY(${f2(rise.y)}px)` : undefined,
            filter: rise.sig > 0 ? `url(#${tBlur})` : undefined }}>
            <FigureGlyphs fig={L.tgt} face={D} size={T} track={TRACK.figure} x={L.tx} base={L.base} paint="gold" id={id}
              sheen={prog(t, g.at_target + TIME.sheenDelay, TIME.sheenDur, EASE.sheen)} />
          </div>
        </LineMask>
      ) : null}
      <LineMask on={t < labLanded} y0={L.lBase - O.cap * L.Ls - 10 * k} y1={L.lBase + 10 * k}>
        <Run text={L.label} face={O} size={L.Ls} track={TRACK.label} x={L.lx} base={L.lBase} paint="white"
          rise={stagger(labT, TIME.stagger, TIME.rise, O.cap * L.Ls * 1.3)} t={t} dt={dt} id={`${id}-l`} k={k} />
      </LineMask>
      {/* the key figure: ink on its marker, counting; the % at 0.56x, cap top on the digits' cap top */}
      <MarkerReveal m={mk} y0={L.mTop} y1={L.mBot} id={`${id}-m`} w={w} h={h}>
        <Scaled s={sc} ox={L.fx} oy={L.base}>
          <Odometer face={D} size={S} v={g.v} x={L.fx} base={L.base} paint="ink" valAt={c.val} t={t} dt={dt} id={`${id}-o`} k={k} />
          <Glyphs text="%" face={D} size={L.ss} x={L.fx + L.sx} base={signBase(D, L.ss, "%", L.capTop)} paint="ink" />
        </Scaled>
      </MarkerReveal>
    </Lockup>
  );
};

export const GoalBar: React.FC<TP> = (props) => {
  const F = useFaces();
  return F ? <Bar {...props} F={F} /> : null;
};
