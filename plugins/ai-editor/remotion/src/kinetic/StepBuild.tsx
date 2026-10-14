// step_build: a tracker of 2-4 slots that comes back at several beats of one video with the same slots and identity
// ("two shops to open": two empty slots; later the first fills; later the second; later a third pops up as "?").
// One card per beat. Every beat of one tracker passes the same slots (labels included) and only states and times change:
//   - empty: a glass well with its number; filled: its label; question: a dashed well with a "?"; off: not up in this
//     beat (a later beat adds it), kept in the columns so every beat lays out the same;
//   - a slot with `at` changes on that word: an empty or question slot pops in there (the slots already up slide aside
//     first), a filled one fills there: the marker is pulled across its well and reveals the label as ink (1.06 -> 1
//     settle), and hands the label to the foil (with a gold edge) as the next slot lands; the last keeps its marker;
//   - a slot with no `at` is already so when the card comes up (an earlier beat did it): a filled one shows its label in
//     the foil; a tracker with slots already up sweeps in left to right;
//   - fixed columns solved once from every slot's label: equal wells on the grid, the slots up centred on it; every
//     label inside its well (wrapped onto two lines, and smaller, when four long labels share the grid; labels that
//     fit no well even then throw);
//   - beats close together are joined (plan.py): join_out holds the tracker still to the end of its card (no sweep,
//     no push; a fill that kept its marker hands it to the foil just before), join_in carries on from it (no sweep in,
//     the scrim already up), so the next beat continues the same tracker.
// props: slots: [{label?, state: "empty" | "filled" | "question" | "off", at?}] (2-4), id? (names the tracker), out_at?,
//        join_in?, join_out?, band?, hide_captions?
import React, { useMemo } from "react";
import { prog } from "../motion";
import type { TP } from "../Templates";
import { fitDown, layoutBox } from "./fit";
import { wrap2 } from "./NumberChain";
import { Behind, FoilDefs, Glyphs, Lockup, MarkerReveal, Scaled, f2, lerp, pullOff, pullOn, settleAt } from "./primitives";
import { exitAt, useClock } from "./time";
import { Part, Prober, R } from "./probe";
import { EASE, SLOT, STEP, TIME, TRACK } from "./tokens";
import { Face, Faces, baseOff, ink, runW, useFaces } from "./type";

type State = "empty" | "filled" | "question" | "off";
type Slot = { label: string; state: State; at?: number };
const STATES: State[] = ["empty", "filled", "question", "off"];

/** The slots as drawn: 2-4, each in a known state; a filled one needs its label. No `at`: already so as the card comes up. */
export const stepSlots = (p: Record<string, any>): Slot[] => {
  const slots = Array.isArray(p.slots) ? p.slots : [];
  if (slots.length < 2 || slots.length > 4) throw new Error(`step_build needs 2-4 slots, got ${slots.length}`);
  const out = slots.map((s: any, i: number): Slot => {
    const state = (s?.state ?? "empty") as State;
    if (!STATES.includes(state)) throw new Error(`step_build slot ${i} has state "${s?.state}" (empty, filled, question or off)`);
    const label = s?.label === undefined || s?.label === null ? "" : String(s.label).trim();
    if (state === "filled" && !label) throw new Error(`step_build slot ${i} is filled and has no label`);
    return { label, state, at: typeof s?.at === "number" ? s.at : undefined };
  });
  if (out.every((s) => s.state === "off")) throw new Error("step_build has no slot up (every slot is off)");
  return out;
};

/** Lines of a wrapped label sit this many label sizes apart. */
const LEAD = 0.98;

/** Label sizes (px at 1080): the largest, the smallest that reads as a tracker, and the floor a crowded one may go to. */
const SIZE = { max: 130, read: 48, floor: 34 };

const solve = (F: Faces, slots: Slot[], w: number, h: number, band: unknown, beside: unknown) => {
  const D = F.display, box = layoutBox(w, h, band, beside), k = box.k, n = slots.length;
  const G = SLOT.gap * k, W = (box.width - (n - 1) * G) / n;
  // every label any beat may show, so the size is the same in each beat
  const texts = slots.map((s) => (s.state === "question" ? "?" : s.label.toUpperCase()));
  const at = (S: number, wrap: boolean) => {
    const padX = S * 0.22, padY = S * 0.3;
    const lines = texts.map((x) => (!x ? [] : wrap ? wrap2(x) : [x]));
    const rows = Math.max(1, ...lines.map((l) => l.length));
    const H = D.cap * S + (rows - 1) * S * LEAD + 2 * padY;
    const fits = lines.every((ls) => ls.every((l) => runW(D, S, TRACK.figure, l) <= W - 2 * padX));
    return { ok: fits && H <= box.height, lines, H };
  };
  // one line when it reads; two-word labels wrap only when that makes them clearly bigger. When neither fits at
  // SIZE.read, smaller down to SIZE.floor, wrapped first; never a label past its well
  const words = texts.some((x) => x.includes(" "));
  let fit = fitDown(SIZE.max * k, SIZE.read * k, 2 * k, (S) => at(S, false));
  if ((!fit.ok || fit.size < 72 * k) && words) {
    const wr = fitDown(SIZE.max * k, SIZE.read * k, 2 * k, (S) => at(S, true));
    if (wr.ok && (!fit.ok || wr.size > fit.size * 1.2)) fit = wr;
  }
  for (const wrap of fit.ok ? [] : words ? [true, false] : [false]) {
    const f = fitDown(SIZE.read * k, SIZE.floor * k, 2 * k, (S) => at(S, wrap));
    if (f.ok) { fit = f; break; }
  }
  if (!fit.ok) throw new Error(`step_build: the labels ${texts.filter(Boolean).map((x) => JSON.stringify(x)).join(", ")} do not fit ${n} wells ` +
    "across the grid: shorter labels or fewer slots");
  return { ...fit, S: fit.size, box, k, W, G, cx: box.left + box.width / 2, top: box.top, r: SLOT.radius * k, bw: Math.max(1, SLOT.line * k) };
};

/** The beat's timeline: which slots are up as the card comes up, when the others pop in (slots on one word as one
 *  event, popStagger apart), each slot's x as the row makes room, every landing, and when a fill hands off. */
const timeline = (slots: Slot[], fps: number, L: { W: number; G: number; cx: number }, dur: number, joinOut: boolean) => {
  const up0 = slots.map((s, i) => (s.state !== "off" && (s.at === undefined || s.state === "filled") ? i : -1)).filter((i) => i >= 0);
  const popping = slots.map((s, i) => (s.state !== "off" && s.state !== "filled" && s.at !== undefined ? i : -1)).filter((i) => i >= 0);
  const groups = [...new Set(popping.map((i) => slots[i].at!))].sort((a, b) => a - b);
  const popT: Record<number, number> = {};
  const events = groups.map((a) => {
    const ids = popping.filter((i) => slots[i].at === a);
    ids.forEach((i, r) => { popT[i] = a - TIME.lead + r * STEP.popStagger; });
    return { t: a - TIME.lead, ids };
  });
  const sets: number[][] = [];
  events.reduce((prev, e) => { const s = [...prev, ...e.ids].sort((a, b) => a - b); sets.push(s); return s; }, up0);
  const xIn = (set: number[], i: number) => {
    const m = set.length, j = set.indexOf(i);
    return L.cx - (m * L.W + (m - 1) * L.G) / 2 + j * (L.W + L.G);
  };
  // a slot's left edge at t: where it stood, sliding to each new place just before the slot that needs room lands
  const xAt = (i: number, t: number) => {
    let x = up0.includes(i) ? xIn(up0, i) : undefined;
    events.forEach((e, ei) => {
      if (!sets[ei].includes(i)) return;
      const to = xIn(sets[ei], i);
      x = x === undefined ? to : lerp(x, to, prog(t, e.t - STEP.reflow, STEP.reflow, STEP.reflowEase));
    });
    return x ?? L.cx;
  };
  const landing = slots.map((s, i) => (s.at === undefined || s.state === "off" ? undefined : s.state === "filled" ? s.at : popT[i] + TIME.lead));
  const lands = landing.filter((x): x is number => x !== undefined);
  // a fill keeps its marker until the next landing after it comes; the last keeps it, unless the next beat carries on
  // (join_out): then it hands it to the foil just before the card ends, so the next beat starts in foil (no sheen: it
  // would be cut off)
  const hand = slots.map((s, i) => {
    if (s.state !== "filled" || s.at === undefined) return Infinity;
    const after = lands.filter((x) => x > landing[i]! + 1e-6);
    if (after.length) return Math.min(...after) - TIME.handoffLead;
    return joinOut ? Math.max(s.at + 0.3, dur - TIME.handoff - 0.05) : Infinity;
  });
  const sheenOn = slots.map((s, i) => Number.isFinite(hand[i]) && lands.some((x) => x > landing[i]! + 1e-6));
  return { up0, popT, xAt, landing, lands, hand, sheenOn, fps };
};

/** An empty slot's well with its number, or a filled slot's gold-edged well, or a question's dashed well. */
const Well: React.FC<{ x: number; y: number; W: number; H: number; r: number; bw: number; edge: string; dash?: number }> =
  ({ x, y, W, H, r, bw, edge, dash }) => dash ? (
    <svg width={W + 2 * bw} height={H + 2 * bw} style={{ position: "absolute", left: x - bw, top: y - bw, overflow: "visible" }}>
      <rect x={bw * 1.5} y={bw * 1.5} width={W - bw} height={H - bw} rx={r} fill={SLOT.well} stroke={edge} strokeWidth={bw}
        strokeDasharray={`${f2(dash)} ${f2(dash * 0.7)}`} />
    </svg>
  ) : (
    <div style={{ position: "absolute", left: x, top: y, width: W, height: H, borderRadius: r, background: SLOT.well,
      border: `${f2(bw)}px solid ${edge}`, boxSizing: "border-box" }} />
  );

/** A label's lines centred on their ink in a well at x (each line's own ink), the block centred on the well's height. */
const Label: React.FC<{ lines: string[]; face: Face; S: number; x: number; y: number; W: number; H: number; paint: "ink" | "gold"; id: string;
  sheen?: number }> = ({ lines, face, S, x, y, W, H, paint, id, sheen = -1 }) => {
  const capTop = y + (H - (face.cap * S + (lines.length - 1) * S * LEAD)) / 2;
  return (
    <>
      {lines.map((l, li) => {
        const g = ink(face, S, TRACK.figure, l), lw = runW(face, S, TRACK.figure, l);
        return <Glyphs key={li} text={l} face={face} size={S} track={TRACK.figure} x={x + W / 2 - (g.il + g.ir) / 2} base={capTop + face.cap * S + li * S * LEAD}
          paint={paint} id={id} sheen={sheen} sheenW={lw} sheenX={0} />;
      })}
    </>
  );
};

/** The layout as rectangles, every slot up in its last place (kinetic/probe.ts): each label inside its well. */
export const probe: Prober = (F, p, w, h) => {
  const slots = stepSlots(p), L = solve(F, slots, w, h, p.band, p.beside), D = F.display;
  const up = slots.map((s, i) => (s.state === "off" ? -1 : i)).filter((i) => i >= 0), m = up.length;
  const parts: Part[] = [];
  up.forEach((i, j) => {
    const x = L.cx - (m * L.W + (m - 1) * L.G) / 2 + j * (L.W + L.G), well: R = [x, L.top, x + L.W, L.top + L.H];
    parts.push({ kind: "slot", r: well });
    const ls = L.lines[i], capTop = L.top + (L.H - (D.cap * L.S + (ls.length - 1) * L.S * LEAD)) / 2;
    ls.forEach((l, li) => {
      const g = ink(D, L.S, TRACK.figure, l), x0 = x + L.W / 2 - (g.il + g.ir) / 2, base = capTop + D.cap * L.S + li * L.S * LEAD;
      parts.push({ kind: "slot-label", r: [x0 + g.il, base - D.cap * L.S, x0 + g.ir, base], in: well });
    });
  });
  return { k: L.k, parts, sizes: { label: L.S } };
};

const Tracker: React.FC<TP & { F: Faces }> = ({ p, w, h, dur, id, F }) => {
  const { t, dt, fps } = useClock();
  const slots = useMemo(() => stepSlots(p), [JSON.stringify(p.slots)]);
  const L = useMemo(() => solve(F, slots, w, h, p.band, p.beside), [F, slots, w, h, JSON.stringify(p.band), JSON.stringify(p.beside)]);
  const joinIn = p.join_in === true, joinOut = p.join_out === true;
  const T = useMemo(() => timeline(slots, fps, L, dur, joinOut), [slots, fps, L, dur, joinOut]);
  const D = F.display, S = L.S, k = L.k, y = L.top, H = L.H;
  const t0 = T.up0.length ? TIME.lead : Math.min(...T.lands) - TIME.lead;
  // joined to the next beat: it stays (StyleEdit hands the frame to the next card at its start)
  const out = joinOut ? Infinity : exitAt(dur, Math.max(TIME.lead, ...T.lands), p.out_at);
  // a tracker with slots already up comes back with one feathered edge sweeping in, left to right (not when it carries on)
  const pe = T.up0.length && !joinIn ? prog(t, 0, TIME.exit, STEP.enterEase) : 1;
  const FE = 240 * k, ex = lerp(L.box.left - 30, w + FE + 30, pe);
  const sweep = pe < 1 ? `linear-gradient(90deg, #000 ${f2(ex - FE)}px, rgba(0,0,0,0) ${f2(ex)}px)` : undefined;
  const num = (i: number) => String(i + 1);
  const NS = S * 0.62;
  return (
    <Lockup t={t} t0={t0} out={out} box={L.box} oy={y} w={w} h={h} joined={joinIn} bridge={p}>
      <FoilDefs id={id} sizes={[S]} />
      <div style={{ position: "absolute", inset: 0, maskImage: sweep, WebkitMaskImage: sweep } as React.CSSProperties}>
        {slots.map((s, i) => {
          if (s.state === "off") return null;
          const popAt = T.popT[i];
          if (popAt !== undefined && t < popAt - dt * 0.5) return null;
          const x = T.xAt(i, t), lines = L.lines[i];
          const pop = popAt !== undefined ? STEP.popFrom + (1 - STEP.popFrom) * prog(t, popAt, STEP.popFrames / fps, STEP.popEase) : 1;
          const ng = ink(D, NS, 0, num(i));
          const numeral = (
            <span style={{ position: "absolute", left: x + L.W / 2 - (ng.il + ng.ir) / 2, top: y + (H - D.cap * NS) / 2 + D.cap * NS - baseOff(D, NS),
              fontFamily: D.fam, fontWeight: D.weight, fontSize: NS, lineHeight: `${f2(NS)}px`, color: SLOT.numeral, whiteSpace: "pre" }}>{num(i)}</span>
          );
          if (s.state === "empty") return (
            <Scaled key={i} s={pop} ox={x + L.W / 2} oy={y + H / 2}>
              <Well x={x} y={y} W={L.W} H={H} r={L.r} bw={L.bw} edge={SLOT.edge} />
              {numeral}
            </Scaled>
          );
          if (s.state === "question") {
            const land = T.landing[i];
            const sheen = land === undefined ? -1 : prog(t, land + TIME.sheenDelay, TIME.sheenDur, EASE.sheen);
            return (
              <Scaled key={i} s={pop} ox={x + L.W / 2} oy={y + H / 2}>
                <Well x={x} y={y} W={L.W} H={H} r={L.r} bw={L.bw * 1.4} edge={SLOT.ask} dash={14 * k} />
                <Label lines={lines} face={D} S={S} x={x} y={y} W={L.W} H={H} paint="gold" id={id} sheen={sheen} />
              </Scaled>
            );
          }
          // filled: already so (an earlier beat filled it), or filling on its word
          const done = (
            <>
              <Well x={x} y={y} W={L.W} H={H} r={L.r} bw={L.bw * 1.4} edge={SLOT.done} />
              <Label lines={lines} face={D} S={S} x={x} y={y} W={L.W} H={H} paint="gold" id={id}
                sheen={T.sheenOn[i] ? prog(t, T.hand[i] + TIME.handoff + 0.04, TIME.sheenDur, EASE.sheen) : -1} />
            </>
          );
          if (s.at === undefined) return <React.Fragment key={i}>{done}</React.Fragment>;
          const on = pullOn(t, x, x + L.W, H, s.at - TIME.lead);
          const m = pullOff(on, x + L.W, t, T.hand[i]);
          const clip = `inset(${f2(y)}px ${f2(w - x - L.W)}px ${f2(h - y - H)}px ${f2(x)}px round ${f2(L.r)}px)`;
          // the empty well stays only ahead of the marker's leading edge
          const ahead = `polygon(${f2(on.b + on.k)}px ${f2(y)}px, ${w + 4000}px ${f2(y)}px, ${w + 4000}px ${f2(y + H)}px, ${f2(on.b - on.k)}px ${f2(y + H)}px)`;
          return (
            <React.Fragment key={i}>
              {on.b < x + L.W - 0.5 ? (
                <div style={{ position: "absolute", inset: 0, clipPath: on.b - on.a > 0.5 ? ahead : undefined }}>
                  <Well x={x} y={y} W={L.W} H={H} r={L.r} bw={L.bw} edge={SLOT.edge} />
                  {numeral}
                </div>
              ) : null}
              <Behind a={m.a} off={m.off} h={h}>{done}</Behind>
              <div style={{ position: "absolute", inset: 0, clipPath: clip }}>
                <MarkerReveal m={m} y0={y} y1={y + H} id={`${id}-m${i}`} w={w} h={h}>
                  <Scaled s={settleAt(t, s.at - TIME.lead, fps)} ox={x + L.W / 2} oy={y + H / 2}>
                    <Label lines={lines} face={D} S={S} x={x} y={y} W={L.W} H={H} paint="ink" id={id} />
                  </Scaled>
                </MarkerReveal>
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </Lockup>
  );
};

export const StepBuild: React.FC<TP> = (props) => {
  const F = useFaces();
  return F ? <Tracker {...props} F={F} /> : null;
};
