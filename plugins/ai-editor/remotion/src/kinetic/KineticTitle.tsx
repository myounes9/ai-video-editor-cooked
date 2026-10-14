// kinetic_title: a key-word title for a beat with no number ("THIS IS HOW / SOURDOUGH / WE BAKE BY HAND"): 1-3 lines,
// each word on its own spoken word, the key words in the key colour. Built like number_chain (NumberChain.tsx):
//   - a line holding a key word is a hero line, set in Anton; a line with none is a supporting line, Oswald 500 at
//     0.4x the hero size (a title with no key word at all is hero lines only, white). Every line is centred on the
//     grid and the whole title fits the grid width and the face band at the largest hero size that does;
//   - a key word is pulled on as ink on the highlighter marker on its word (1.06 -> 1 settle); consecutive key words
//     share one marker whose leading edge runs on word by word. When the next key word comes, the marker is pulled
//     off and hands its words to the foil (a stacked layer, never a colour blend): key words stay key-coloured; the
//     last keeps its marker;
//   - every other word rises per character through its line's mask on its word;
//   - the lockup holds at least 1.2 s after its last landing (unless the card ends sooner), pushes 1.5 %, and leaves
//     in one feathered sweep.
// props: lines: [{words: [{text, at, key?}]}] (1-3 lines; times in seconds after the card starts), out_at?, band?
//        ([top, bottom] % of the frame height, from face.json), hide_captions? (default true: StyleEdit.tsx).
import React, { useMemo } from "react";
import { prog } from "../motion";
import type { TP } from "../Templates";
import { layoutBox, fitDown } from "./fit";
import { Behind, FoilDefs, Glyphs, LineMask, MarkerReveal, Lockup, Run, Scaled, landedAt, pullOff, pullOn, settleAt, stagger } from "./primitives";
import { exitAt, firstLanding, useClock } from "./time";
import { Part, Prober, R } from "./probe";
import { EASE, LABEL, TIME, TRACK } from "./tokens";
import { Faces, adv, ink, runW, useFaces } from "./type";

type Word = { text: string; at: number; key: boolean };

/** The lines as drawn: 1-3, each with at least one word; a word's text in capitals, a missing time spread 0.22 s a
 *  word in reading order (never random). */
export const titleLines = (p: Record<string, any>): Word[][] => {
  const lines = Array.isArray(p.lines) ? p.lines : [];
  if (lines.length < 1 || lines.length > 3) throw new Error(`kinetic_title needs 1-3 lines, got ${lines.length}`);
  let n = 0;
  return lines.map((l: any, i: number) => {
    const ws = Array.isArray(l?.words) ? l.words : [];
    if (!ws.length) throw new Error(`kinetic_title line ${i} has no words`);
    return ws.map((x: any, j: number) => {
      const text = String(x?.text ?? "").trim();
      if (!text || /\s/.test(text)) throw new Error(`kinetic_title line ${i} word ${j} must be one word, got "${x?.text}"`);
      const at = typeof x.at === "number" ? x.at : 0.1 + n * 0.22;
      n += 1;
      return { text: text.toUpperCase(), at, key: x.key === true };
    });
  });
};

/** A supporting line's size, x the hero size (never under LABEL.size). */
const SUPPORT = 0.4;
/** A word not on the marker rises from its word's time less this (as a label does). */
const EARLY = 0.04;

const solve = (F: Faces, lines: Word[][], w: number, h: number, band: unknown, beside: unknown) => {
  const D = F.display, O = F.text, box = layoutBox(w, h, band, beside), k = box.k;
  const anyKey = lines.some((l) => l.some((x) => x.key));
  const hero = lines.map((l) => !anyKey || l.some((x) => x.key));
  const at = (S: number) => {
    const Ss = Math.max(LABEL.size * k, S * SUPPORT), padX = S * 0.1, padY = S * 0.1;
    const rows = lines.map((l, i) => {
      const face = hero[i] ? D : O, size = hero[i] ? S : Ss, track = hero[i] ? TRACK.figure : TRACK.line;
      const marked = l.some((x) => x.key);
      const sp = adv(face, size, track, " ");
      let x = 0;
      const ws = l.map((wd, j) => {
        // a marker's edge stands padX off its ink: the word beside it steps out by as much
        if (j) x += sp + (wd.key !== l[j - 1].key ? padX : 0);
        const e = ink(face, size, track, wd.text), ww = runW(face, size, track, wd.text);
        const r = { x, w: ww, il: e.il, ir: e.ir };
        x += ww;
        return r;
      });
      const left = Math.min(...ws.map((g, j) => g.x + g.il - (l[j].key ? padX : 0)));
      const right = Math.max(...ws.map((g, j) => g.x + g.ir + (l[j].key ? padX : 0)));
      const capH = face.cap * size;
      return { face, size, track, ws, left, right, capH, marked, height: capH + (marked ? 2 * padY : 0) };
    });
    // a supporting line under or over a hero line sits gap away from its marker; two supporting lines closer
    const gaps = rows.slice(1).map((r, i) => (!hero[i] && !hero[i + 1] ? Ss * 0.32 : Math.max(14 * k, S * (anyKey ? 0.09 : 0.16))));
    const totalH = rows.reduce((a, r) => a + r.height, 0) + gaps.reduce((a, b) => a + b, 0);
    const ok = rows.every((r) => r.right - r.left <= box.width) && totalH <= box.height;
    return { ok, rows, gaps, Ss, padX, padY, totalH };
  };
  const fit = fitDown(260 * k, 64 * k, 2 * k, at);
  const S = fit.size;
  let y = box.top;
  const placed = fit.rows.map((r, i) => {
    if (i) y += fit.gaps[i - 1];
    const top = y, capTop = top + (r.marked ? fit.padY : 0), base = capTop + r.capH;
    y += r.height;
    const x0 = box.left + (box.width - (r.right - r.left)) / 2 - r.left;   // centred on the grid
    // runs of consecutive key words: one marker each, from the first word's ink to each word's own right edge
    const runs: { j0: number; j1: number; a: number; edges: number[] }[] = [];
    lines[i].forEach((wd, j) => {
      if (!wd.key) return;
      const g = r.ws[j], last = runs[runs.length - 1];
      if (last && last.j1 === j - 1) { last.j1 = j; last.edges.push(x0 + g.x + g.ir + fit.padX); return; }
      runs.push({ j0: j, j1: j, a: x0 + g.x + g.il - fit.padX, edges: [x0 + g.x + g.ir + fit.padX] });
    });
    return { ...r, top, capTop, base, bottom: top + r.height, x0, runs };
  });
  return { ...fit, S, box, k, rows: placed, hero };
};

/** The layout as rectangles: each word's ink (kinetic/probe.ts). */
export const probe: Prober = (F, p, w, h, dur) => {
  const lines = titleLines(p), L = solve(F, lines, w, h, p.band, p.beside);
  firstLanding("kinetic_title", Math.min(...lines.flat().map((x) => x.at)), dur);
  const parts: Part[] = L.rows.flatMap((r) => r.ws.map((g) => ({ kind: "word", r: [r.x0 + g.x + g.il, r.capTop, r.x0 + g.x + g.ir, r.base] as R })));
  return { k: L.k, parts, sizes: { figure: L.S } };
};

const Title: React.FC<TP & { F: Faces }> = ({ p, w, h, dur, id, F }) => {
  const { t, dt, fps } = useClock();
  const lines = useMemo(() => titleLines(p), [JSON.stringify(p.lines)]);
  const L = useMemo(() => solve(F, lines, w, h, p.band, p.beside), [F, lines, w, h, JSON.stringify(p.band), JSON.stringify(p.beside)]);
  const S = L.S, k = L.k;
  // every marker run, in the order it is said: each hands its words to the foil as the next one comes
  const runs = L.rows.flatMap((r, i) => r.runs.map((run) => ({ ...run, i, at: lines[i][run.j0].at })))
    .sort((a, b) => a.at - b.at);
  const hand = runs.map((_, ri) => (ri < runs.length - 1 ? runs[ri + 1].at - TIME.handoffLead : Infinity));
  const plain = lines.flatMap((l, i) => l.map((wd, j) => ({ ...wd, i, j })).filter((x) => !x.key));
  const landed = (x: { at: number; text: string }) => landedAt(x.at - EARLY, x.text.length);
  const last = Math.max(...runs.flatMap((run) => lines[run.i].slice(run.j0, run.j1 + 1).map((x) => x.at)), ...plain.map(landed));
  const first = Math.min(...lines.flat().map((x) => x.at));
  useMemo(() => firstLanding("kinetic_title", first, dur), [first, dur]);
  const out = exitAt(dur, last, p.out_at);
  return (
    <Lockup t={t} t0={first - TIME.lead} out={out} box={L.box} oy={L.box.top} w={w} h={h} bridge={p}>
      {runs.some((_, ri) => Number.isFinite(hand[ri])) ? <FoilDefs id={id} sizes={[S]} /> : null}
      {runs.map((run, ri) => {
        const r = L.rows[run.i], ws = lines[run.i];
        // the leading edge runs on to each key word's right edge on that word
        let jj = -1;
        for (let j = run.j0; j <= run.j1; j++) if (t >= ws[j].at - TIME.lead) jj = j;
        if (jj < 0) return null;
        const from = jj === run.j0 ? run.a : run.edges[jj - run.j0 - 1];
        const on = { ...pullOn(t, from, run.edges[jj - run.j0], r.height, ws[jj].at - TIME.lead), a: run.a };
        const m = pullOff(on, on.b, t, hand[ri]);
        const sheen = Number.isFinite(hand[ri]) ? prog(t, hand[ri] + TIME.handoff + 0.04, TIME.sheenDur, EASE.sheen) : -1;
        const x1 = r.x0 + r.ws[run.j0].x, wRun = r.ws[run.j1].x + r.ws[run.j1].w - r.ws[run.j0].x;
        const words = ws.slice(run.j0, run.j1 + 1).map((wd, q) => ({ wd, g: r.ws[run.j0 + q] }));
        return (
          <React.Fragment key={ri}>
            <Behind a={m.a} off={m.off} h={h}>
              {words.map(({ wd, g }, q) => (
                <Glyphs key={q} text={wd.text} face={r.face} size={S} track={r.track} x={r.x0 + g.x} base={r.base} paint="gold" id={id}
                  sheen={sheen} sheenW={wRun} sheenX={r.x0 + g.x - x1} />
              ))}
            </Behind>
            <MarkerReveal m={m} y0={r.top} y1={r.bottom} id={`${id}-m${ri}`} w={w} h={h}>
              {words.map(({ wd, g }, q) => (
                <Scaled key={q} s={settleAt(t, wd.at - TIME.lead, fps)} ox={r.x0 + g.x} oy={r.base}>
                  <Glyphs text={wd.text} face={r.face} size={S} track={r.track} x={r.x0 + g.x} base={r.base} paint="ink" />
                </Scaled>
              ))}
            </MarkerReveal>
          </React.Fragment>
        );
      })}
      {L.rows.map((r, i) => {
        const ws = plain.filter((x) => x.i === i);
        if (!ws.length) return null;
        const dist = r.capH * 1.3;
        return (
          <LineMask key={i} on={t < Math.max(...ws.map(landed))} y0={r.capTop - 10 * k} y1={r.base + 10 * k}>
            {ws.map((x) => (
              <Run key={x.j} text={x.text} face={r.face} size={r.size} track={r.track} x={r.x0 + r.ws[x.j].x} base={r.base} paint="white"
                rise={stagger(x.at - EARLY, TIME.stagger, TIME.rise, dist)} t={t} dt={dt} id={`${id}-w${i}-${x.j}`} k={k} />
            ))}
          </LineMask>
        );
      })}
    </Lockup>
  );
};

export const KineticTitle: React.FC<TP> = (props) => {
  const F = useFaces();
  return F ? <Title {...props} F={F} /> : null;
};
