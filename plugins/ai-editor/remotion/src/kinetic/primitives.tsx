// The kinetic family's primitives (references/kinetic.md). Every one is a pure function of the card's clock: no GSAP
// timeline state, no randomness, no wall clock, so a frame draws the same in every render tab. Determinism rules
// (proven by test/determinism.mjs): no blurred box-shadow on anything that moves (a crisp underlay or a gradient
// instead), a transform is dropped once its move has settled, and a scaled layer never carries opacity (the fade
// lives on an unscaled parent or in a colour's alpha).
import React, { useMemo } from "react";
import { useVideoConfig } from "remotion";
import { prog } from "../motion";
import { BLUR, BRONZE, EASE, FOIL, INK, KEY, SHEEN, SOFT, TIME, UNDER, WHITE } from "./tokens";
import { Face, Figure, Value, adv, baseOff, figureParts, offsets, runW, signBase, writeValue } from "./type";
import type { Box } from "./fit";

export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const f2 = (n: number) => n.toFixed(2);
/** An id safe inside url(#...). */
export const sid = (s: string) => s.replace(/[^A-Za-z0-9_-]/g, "-");

// =========================================================================================== motion blur
/** Vertical blur sigma from a glyph's travel across one frame (BLUR, scaled by k = width / 1080). */
export const sigOf = (disp: number, k = 1) => (Math.abs(disp) < BLUR.minPx * k ? 0 : Math.min(BLUR.maxPx * k, Math.abs(disp) * BLUR.k));
/** A position function's value at t and the blur its speed earns this frame. */
export const moving = (t: number, dt: number, f: (u: number) => number, k = 1) => ({ y: f(t), sig: sigOf(f(t + dt / 2) - f(t - dt / 2), k) });
type BlurDef = { id: string; sy: number };
/** Y-only gaussian blur filters, one per moving glyph or cell this frame. */
export const BlurDefs: React.FC<{ defs: BlurDef[] }> = ({ defs }) => defs.length ? (
  <svg width={0} height={0} style={{ position: "absolute" }}>
    <defs>
      {defs.map((d) => (
        <filter key={d.id} id={d.id} x="-40%" y="-80%" width="180%" height="260%" colorInterpolationFilters="sRGB">
          <feGaussianBlur stdDeviation={`0 ${f2(d.sy)}`} />
        </filter>
      ))}
    </defs>
  </svg>
) : null;

// =========================================================================================== paint
/** How a run of type is filled: flat ink (on the marker), white (over footage, with SOFT), or the foil. */
export type Paint = "ink" | "white" | "gold";
/** Pad round a foil span: background-clip:text paints only inside the span's box, and a glyph's ink overhangs its
 *  advance and its line box a little. */
const PAD = 0.25;
/** The foil as CSS for one span of `face` at `size` (its line box `size` tall, padded by PAD): the gradient's stops
 *  sit on the glyphs' own cap height, so it reads the same in any face at any size. sheen: the one warm pass,
 *  0..1 across `sheenW` px of a figure whose left is `sheenX` px left of this span (-1: none). */
export const foil = (face: Face, size: number, sheen = -1, sheenW = 0, sheenX = 0): React.CSSProperties => {
  const pad = PAD * size, capTop = pad + baseOff(face, size) - face.cap * size, capH = face.cap * size;
  const grad = `linear-gradient(180deg, ${FOIL.map(([c, u]) => `${c} ${f2(capTop + u * capH)}px`).join(", ")})`;
  const band = sheen > 0 && sheen < 1;
  const c = -25 + 150 * sheen; // band centre, % of the figure's width: starts and ends off the glyphs
  const sh = `linear-gradient(112deg, rgba(255,236,160,0) ${f2(c - 16)}%, rgba(255,236,160,0.18) ${f2(c - 7)}%, ${SHEEN} ${f2(c)}%, ` +
    `rgba(255,236,160,0.18) ${f2(c + 7)}%, rgba(255,236,160,0) ${f2(c + 16)}%)`;
  return { color: "transparent", WebkitBackgroundClip: "text", backgroundClip: "text", backgroundRepeat: "no-repeat",
    backgroundImage: band ? `${sh}, ${grad}` : grad,
    backgroundSize: band ? `${f2(sheenW + 2 * pad)}px ${f2(size + 2 * pad)}px, 100% 100%` : "100% 100%",
    backgroundPosition: band ? `${f2(-sheenX)}px 0px, 0px 0px` : "0px 0px" };
};
/** The foil's relief for type at `size`: a hairline bronze outline, a quiet bevel (a pale lip on upward edges, a warm
 *  shade under them) and a tight contact shadow. One filter per size; ids from foilId. */
export const foilId = (id: string, size: number) => `${sid(id)}-foil-${Math.round(size)}`;
export const FoilDefs: React.FC<{ id: string; sizes: number[] }> = ({ id, sizes }) => (
  <svg width={0} height={0} style={{ position: "absolute" }}>
    <defs>
      {[...new Set(sizes.map((s) => Math.round(s)))].map((S) => {
        const e = Math.max(1.2, S * 0.007), o = Math.max(0.8, S * 0.004);
        return (
          <filter key={S} id={foilId(id, S)} x="-20%" y="-25%" width="140%" height="160%" colorInterpolationFilters="sRGB">
            <feMorphology in="SourceAlpha" operator="dilate" radius={f2(o)} result="dil" />
            <feComposite in="dil" in2="SourceAlpha" operator="out" result="ring" />
            <feFlood floodColor={BRONZE} floodOpacity={0.55} />
            <feComposite in2="ring" operator="in" result="outline" />
            <feOffset in="SourceAlpha" dy={f2(e)} result="down" />
            <feComposite in="SourceAlpha" in2="down" operator="out" result="topEdge" />
            <feGaussianBlur in="topEdge" stdDeviation={f2(e * 0.35)} result="topB" />
            <feComposite in="topB" in2="SourceAlpha" operator="in" result="topIn" />
            <feFlood floodColor="#FFFDF0" floodOpacity={0.5} />
            <feComposite in2="topIn" operator="in" result="hi" />
            <feOffset in="SourceAlpha" dy={f2(-e * 0.9)} result="up" />
            <feComposite in="SourceAlpha" in2="up" operator="out" result="botEdge" />
            <feGaussianBlur in="botEdge" stdDeviation={f2(e * 0.4)} result="botB" />
            <feComposite in="botB" in2="SourceAlpha" operator="in" result="botIn" />
            <feFlood floodColor="#8A5600" floodOpacity={0.35} />
            <feComposite in2="botIn" operator="in" result="lo" />
            <feGaussianBlur in="dil" stdDeviation={f2(S * 0.012)} result="cb" />
            <feOffset in="cb" dy={f2(S * 0.016)} result="co" />
            <feFlood floodColor="#000" floodOpacity={0.42} />
            <feComposite in2="co" operator="in" result="contact" />
            <feMerge>
              <feMergeNode in="contact" />
              <feMergeNode in="outline" />
              <feMergeNode in="SourceGraphic" />
              <feMergeNode in="lo" />
              <feMergeNode in="hi" />
            </feMerge>
          </filter>
        );
      })}
    </defs>
  </svg>
);

/** The style of one run of type on a baseline: its line box `size` tall, positioned so its baseline is at `base`. */
const runStyle = (face: Face, size: number, track: number, x: number, base: number, paint: Paint, id: string,
  sheen = -1, sheenW = 0, sheenX = 0): React.CSSProperties => {
  const gold = paint === "gold", pad = gold ? PAD * size : 0;
  return { position: "absolute", left: x - pad, top: base - baseOff(face, size) - pad, padding: pad || undefined,
    fontFamily: face.fam, fontWeight: face.weight, fontSize: size, lineHeight: `${size}px`, letterSpacing: track ? `${f2(track * size)}px` : undefined,
    whiteSpace: "pre", fontVariantNumeric: "tabular-nums lining-nums",
    ...(gold ? { ...foil(face, size, sheen, sheenW, sheenX + pad), filter: `url(#${foilId(id, size)})` }
      : { color: paint === "ink" ? INK : WHITE, textShadow: paint === "white" ? SOFT : undefined }) };
};

/** A static run on a baseline in one paint. id: the card's foil id (gold only). */
export const Glyphs: React.FC<{ text: string; face: Face; size: number; track?: number; x: number; base: number; paint: Paint; id?: string;
  sheen?: number; sheenW?: number; sheenX?: number }> = ({ text, face, size, track = 0, x, base, paint, id = "k", sheen, sheenW, sheenX }) => (
  <span style={runStyle(face, size, track, x, base, paint, id, sheen, sheenW, sheenX)}>{text}</span>
);

/** A figure (currency sign, body, %) on a baseline: the sign and the % set smaller with their ink tops on the
 *  body's cap top (type.ts signBase). One sheen crosses all of it (gold). */
export const FigureGlyphs: React.FC<{ fig: Figure; face: Face; size: number; track: number; x: number; base: number; paint: Paint; id?: string;
  sheen?: number }> = ({ fig, face, size, track, x, base, paint, id = "k", sheen = -1 }) => {
  const g = figureParts(face, size, track, fig);
  const capTop = base - face.cap * size;
  return (
    <>
      {fig.prefix ? <Glyphs text={fig.prefix} face={face} size={g.ps} x={x + g.px} base={signBase(face, g.ps, fig.prefix, capTop)} paint={paint} id={id}
        sheen={sheen} sheenW={g.w} sheenX={g.px} /> : null}
      <Glyphs text={fig.body} face={face} size={size} track={track} x={x + g.bx} base={base} paint={paint} id={id} sheen={sheen} sheenW={g.w} sheenX={g.bx} />
      {fig.suffix ? <Glyphs text={fig.suffix} face={face} size={g.ss} x={x + g.sx} base={signBase(face, g.ss, fig.suffix, capTop)} paint={paint} id={id}
        sheen={sheen} sheenW={g.w} sheenX={g.sx} /> : null}
    </>
  );
};
/** The sizes a figure draws at (for FoilDefs). */
export const figureSizes = (fig: Figure, size: number) => [size, ...(fig.prefix ? [size * 0.6] : []), ...(fig.suffix ? [size * 0.56] : [])];

// =========================================================================================== line reveal
/** A character's entrance: it rises `dist` px into place from tIn over dIn. */
export type Rise = { tIn: number; dIn: number; dist: number };
const riseY = (t: number, r: Rise) => r.dist * (1 - prog(t, r.tIn, r.dIn, EASE.rise));
/** Characters starting at t0, each `stagger` after the one before. */
export const stagger = (t0: number, s = TIME.stagger, dIn = TIME.rise, dist = 0) => (j: number): Rise => ({ tIn: t0 + j * s, dIn, dist });
/** When a staggered run of n characters has landed (its line mask may go, so its shadow is never cut). */
export const landedAt = (t0: number, n: number, s = TIME.stagger, dIn = TIME.rise) => t0 + s * Math.max(0, n - 1) + dIn * 0.8;

/** One line's characters rising out of their line mask, each at its measured offset (kerning kept), with a short
 *  vertical blur trail from its own speed this frame. paint per character: a key word in foil inside a white line. */
export const Run: React.FC<{ text: string; face: Face; size: number; track: number; x: number; base: number; paint: Paint | ((j: number) => Paint);
  rise: (j: number) => Rise; t: number; dt: number; id: string; k: number }> = ({ text, face, size, track, x, base, paint, rise, t, dt, id, k }) => {
  const xs = useMemo(() => offsets(face, size, track, text), [face, size, track, text]);
  const defs: BlurDef[] = [];
  const spans: React.ReactNode[] = [];
  [...text].forEach((ch, j) => {
    if (ch === " ") return;
    const r = rise(j);
    if (t < r.tIn - dt * 0.5) return;
    const { y, sig } = moving(t, dt, (u) => riseY(u, r), k);
    const fid = `${sid(id)}-b${j}`;
    if (sig > 0) defs.push({ id: fid, sy: sig });
    const pt = typeof paint === "function" ? paint(j) : paint;
    const st = runStyle(face, size, 0, x + xs[j], base, pt, id, -1);
    spans.push(
      <span key={j} style={{ ...st, transform: y ? `translateY(${f2(y)}px)` : undefined,
        filter: [st.filter, sig > 0 ? `url(#${fid})` : ""].filter(Boolean).join(" ") || undefined }}>{ch}</span>);
  });
  return <><BlurDefs defs={defs} />{spans}</>;
};

/** A line's mask: a horizontal strip of the frame (never clipping sideways) while its characters rise; gone once they
 *  have landed, so nothing is cut afterwards. y0..y1: the strip in px. */
export const LineMask: React.FC<{ on: boolean; y0: number; y1: number; children: React.ReactNode }> = ({ on, y0, y1, children }) => (
  <div style={{ position: "absolute", inset: 0, clipPath: on ? `polygon(-4000px ${f2(y0)}px, 8000px ${f2(y0)}px, 8000px ${f2(y1)}px, -4000px ${f2(y1)}px)` : undefined }}>
    {children}
  </div>
);

// =========================================================================================== the marker
/** A marker stroke: from a to b (px), its leading edge leaning k px either way of vertical. */
export type Mk = { a: number; b: number; k: number };
export const markerPoly = (m: Mk, y0: number, y1: number) =>
  `polygon(${f2(m.a)}px ${f2(y0)}px, ${f2(m.b + m.k)}px ${f2(y0)}px, ${f2(m.b - m.k)}px ${f2(y1)}px, ${f2(m.a)}px ${f2(y1)}px)`;
/** The highlighter pull: the left edge stays at a, the leading edge runs to b from t0 over TIME.pull, leaning
 *  TIME.lean degrees for the first half of the run (so a 5-frame pull shows it) and straightening as it lands. */
export const pullOn = (t: number, a: number, b: number, h: number, t0: number): Mk => {
  const p = prog(t, t0, TIME.pull, EASE.pull);
  return { a, b: lerp(a, b, p), k: p > 0 && p < 1 ? h * Math.tan((TIME.lean * Math.PI) / 180) * 0.5 * Math.min(1, 2 * (1 - p)) : 0 };
};
/** The marker pulled off its figure: its trailing edge runs to the leading one from t0 over TIME.handoff. off: 0..1
 *  (t0 Infinity: never, the figure keeps its marker). */
export const pullOff = (m: Mk, b: number, t: number, t0: number) => {
  const off = Number.isFinite(t0) ? prog(t, t0, TIME.handoff, EASE.handoff) : 0;
  return { ...m, a: lerp(m.a, b, off), off };
};
/** Flat printed key colour with a whisper of paper grain (overlay blend, seeded: the same in every process). */
export const Marker: React.FC<{ m: Mk; y0: number; y1: number; id: string; w: number; h: number }> = ({ m, y0, y1, id, w, h }) =>
  m.b - m.a > 0.5 ? (
    <div style={{ position: "absolute", inset: 0, clipPath: markerPoly(m, y0, y1) }}>
      <div style={{ position: "absolute", left: m.a - 40, top: y0, width: m.b - m.a + 80, height: y1 - y0, background: KEY }} />
      <svg width={w} height={h} style={{ position: "absolute", inset: 0, mixBlendMode: "overlay", opacity: 0.45 }}>
        <filter id={`${sid(id)}-grain`} x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={1} seed={7} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect x={m.a - 40} y={y0} width={m.b - m.a + 80} height={y1 - y0} filter={`url(#${sid(id)}-grain)`} />
      </svg>
    </div>
  ) : null;
/** The marker and what it reveals: `children` (ink type) exists only where the stroke already is. */
export const MarkerReveal: React.FC<{ m: Mk; y0: number; y1: number; id: string; w: number; h: number; children: React.ReactNode }> =
  ({ m, y0, y1, id, w, h, children }) => m.b - m.a > 0.5 ? (
    <>
      <Marker m={m} y0={y0} y1={y1} id={id} w={w} h={h} />
      <div style={{ position: "absolute", inset: 0, clipPath: markerPoly(m, y0, y1) }}>{children}</div>
    </>
  ) : null;
/** What the marker hands its figure to as it is pulled off: a stacked layer (the foil) shown only left of the
 *  retreating edge. Never a colour interpolation, so no in-between colour is ever drawn. */
export const Behind: React.FC<{ a: number; off: number; h: number; children: React.ReactNode }> = ({ a, off, h, children }) => off > 0 ? (
  <div style={{ position: "absolute", inset: 0, clipPath: off >= 1 ? undefined : `polygon(-4000px -200px, ${f2(a)}px -200px, ${f2(a)}px ${h + 200}px, -4000px ${h + 200}px)` }}>
    {children}
  </div>
) : null;

// =========================================================================================== settle
/** The cut-in settle: TIME.settleFrom -> 1 over TIME.settleFrames frames on EASE.settle, from t0. */
export const settleAt = (t: number, t0: number, fps: number) => 1 + (TIME.settleFrom - 1) * (1 - prog(t, t0, TIME.settleFrames / fps, EASE.settle));
/** A layer scaled by `s` about (ox, oy); no transform at all once settled (s = 1). */
export const Scaled: React.FC<{ s: number; ox: number; oy: number; children: React.ReactNode }> = ({ s, ox, oy, children }) => (
  <div style={{ position: "absolute", inset: 0, transform: Math.abs(s - 1) > 1e-5 ? `scale(${s.toFixed(5)})` : undefined,
    transformOrigin: `${f2(ox)}px ${f2(oy)}px` }}>{children}</div>
);

// =========================================================================================== the lockup's life
/** Every kinetic lockup's frame: a light top scrim under the Reels header (a gradient, enough to carry white type over
 *  a bright wall; it fades in from the card's start, over TIME.scrim before the first landing when the card starts
 *  that early and over 4 frames at least, and out with the sweep, never on or off in one frame), the held lockup's slow push (TIME.push over its life, about (ox, oy): the grid's centre unless a
 *  format hangs from an edge), and the
 *  exit: one feathered edge (240 px at 1080) sweeping left to right, so a glyph fades as it passes, never cut in two.
 *  t0: the first landing; out: when the sweep starts (Infinity: it never leaves, the next beat of the same lockup
 *  takes over, and it holds still: no push). joined: it carries on from the beat before (the scrim is already up). Nothing
 *  is drawn once the sweep has passed. bridge: the card's props; plan.py bridge_kinetic sets bridge_in / bridge_out when
 *  it starts as another kinetic card ends, or ends as one starts: the scrim stays up across the hand-over (it breathed
 *  out and back in over ten frames there). */
export const Lockup: React.FC<{ t: number; t0: number; out: number; box: Box; oy: number; ox?: number; w: number; h: number; joined?: boolean;
  bridge?: Record<string, unknown>; children: React.ReactNode }> = ({ t, t0, out, box, oy, ox = box.left + box.width / 2, w, h, joined = false,
  bridge, children }) => {
    const { fps } = useVideoConfig();
    const held = { in: joined || bridge?.bridge_in === true, out: bridge?.bridge_out === true };
    const stays = !Number.isFinite(out);
    const pe = stays ? 0 : prog(t, out, TIME.exit, EASE.exit);
    if ((pe >= 1 && !held.out) || (!held.in && t < t0 - TIME.scrim - 0.5)) return null;
    const s0 = Math.max(0, t0 - TIME.scrim);
    const scrimA = (held.in ? 1 : prog(t, s0, Math.max(4 / fps, t0 - s0), EASE.scrimIn)) *
      (stays || held.out ? 1 : 1 - prog(t, out, TIME.exit, EASE.scrimOut));
    const push = stays ? 1 : 1 + TIME.push * clamp01((t - t0) / Math.max(0.5, out - t0));
    const FE = 240 * box.k, ex = lerp(box.left - FE - 30, w + 30, pe);
    const mask = pe > 0 ? `linear-gradient(90deg, rgba(0,0,0,0) ${f2(ex)}px, #000 ${f2(ex + FE)}px)` : undefined;
    return (
      <div style={{ position: "absolute", inset: 0 }}>
        {scrimA > 0 ? <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: Math.min(h, box.bottom * 1.4), opacity: scrimA,
          background: "linear-gradient(180deg, rgba(0,0,0,0.25) 0%, rgba(0,0,0,0.16) 45%, rgba(0,0,0,0) 100%)" }} /> : null}
        {pe < 1 ? (
          <div style={{ position: "absolute", inset: 0, maskImage: mask, WebkitMaskImage: mask } as React.CSSProperties}>
            <Scaled s={push} ox={ox} oy={oy}>{children}</Scaled>
          </div>
        ) : null}
      </div>
    );
  };

// =========================================================================================== connector
/** The chain's connector, drawn from x0 to x1 at y as p runs 0 -> 1: a heavy white shaft, then its chevron head opens
 *  over the last 45% of the draw. A crisp dark underlay (offset, no blur) keeps it readable on a bright wall. sw: stroke
 *  px, hl: the head's arm length px. An SVG <g>: put several in one full-frame <svg>. */
export const Arrow: React.FC<{ x0: number; x1: number; y: number; p: number; sw: number; hl: number; k: number; color?: string }> =
  ({ x0, x1, y, p, sw, hl, k, color = WHITE }) => {
    if (p <= 0) return null;
    const xe = lerp(x0, x1, p), hp = clamp01((p - 0.55) / 0.45), arm = hl * hp;
    const shaft = `M${f2(x0)} ${f2(y)} L${f2(xe - (hp > 0 ? sw * 0.5 : 0))} ${f2(y)}`;
    const head = hp > 0 ? `M${f2(xe - arm)} ${f2(y - arm)} L${f2(xe)} ${f2(y)} L${f2(xe - arm)} ${f2(y + arm)}` : "";
    const dy = 2.5 * k;
    return (
      <g>
        <g transform={`translate(0 ${f2(dy)})`} stroke={UNDER} strokeWidth={sw + 2 * k} fill="none" strokeLinejoin="miter" strokeMiterlimit={8}>
          <path d={shaft} strokeLinecap="butt" />
          {head ? <path d={head} strokeLinecap="square" /> : null}
        </g>
        <g stroke={color} strokeWidth={sw} fill="none" strokeLinejoin="miter" strokeMiterlimit={8}>
          <path d={shaft} strokeLinecap="butt" />
          {head ? <path d={head} strokeLinecap="square" /> : null}
        </g>
      </g>
    );
  };

// =========================================================================================== counter
/** The whole number an odometer shows at t (in units of its last decimal): valAt rounded, never past the final value.
 *  Every place draws its digit from it, so the figure never reads more than it will land on (a higher place rolling
 *  ahead of the ones once showed "49%" on the way to 40%). */
export const odometerShown = (valAt: (u: number) => number, v: Value, t: number) => {
  const unit = 10 ** v.decimals;
  return Math.round(Math.min(Math.round(v.value * unit), valAt(t) * unit));
};
/** An odometer for a figure's body: every place a crisp digit of the same whole number (odometerShown) in its own
 *  tabular cell, a higher place blurred vertically while it changes fast (its speed as a rolling place), so it reads as
 *  counting, never as a smear and never past its final value. Places above the number's current length are blank; a
 *  separator (".", ",") shows once the digit before it does. valAt: the number shown at any time (time.ts counter: from
 *  COUNT_FROM x the final value). Draws v.lead and v.tail (a "K") static around it. Returns nothing else: its width is
 *  odometerW, the same on every frame, so nothing beside it moves. */
export const odometerLayout = (face: Face, size: number, v: Value) => {
  const final = `${v.lead}${writeValue(v.value, v)}${v.tail}`;
  const dw = Math.max(...Array.from({ length: 10 }, (_, d) => adv(face, size, 0, String(d))));
  const num = writeValue(v.value, v);
  const cells: { ch: string; x: number; w: number; place: number }[] = [];
  let x = v.lead ? runW(face, size, 0, v.lead) + size * 0.02 : 0;
  let place = num.replace(/\D/g, "").length;
  for (const ch of num) {
    const digit = /\d/.test(ch);
    if (digit) place -= 1;
    const w = digit ? dw : adv(face, size, 0, ch);
    cells.push({ ch, x, w, place: digit ? place : -1 });
    x += w;
  }
  const tailX = x;
  return { cells, tailX, w: tailX + (v.tail ? runW(face, size, 0, v.tail) : 0), final };
};
export const Odometer: React.FC<{ face: Face; size: number; v: Value; x: number; base: number; paint: Paint;
  valAt: (u: number) => number; t: number; dt: number; id: string; k: number }> = ({ face, size, v, x, base, paint, valAt, t, dt, id, k }) => {
  const L = useMemo(() => odometerLayout(face, size, v), [face, size, v]);
  const unit = 10 ** v.decimals;
  const fin = Math.round(v.value * unit);
  const u = (tt: number) => Math.min(fin, valAt(tt) * unit);
  const n = odometerShown(valAt, v, t);
  const cellTop = base - face.cap * size - size * 0.3, cellH = face.cap * size + size * 0.55;
  const glyphTop = base - baseOff(face, size) - cellTop; // a glyph's line box top inside its cell
  const lenNow = String(n).length;
  const defs: BlurDef[] = [];
  const out: React.ReactNode[] = [];
  L.cells.forEach((c, i) => {
    const shown = (p: number) => p <= v.decimals || p < lenNow;
    if (c.place < 0) {
      // a separator shows once the digit before it does
      const prev = L.cells[i - 1];
      if (prev && prev.place >= 0 && shown(prev.place)) out.push(<Glyphs key={i} text={c.ch} face={face} size={size} x={x + c.x} base={base} paint={paint} id={id} />);
      return;
    }
    const idx = Math.floor(n / 10 ** c.place);
    const rows = [{ d: idx % 10, y: 0, idx }];
    const sig = c.place === 0 ? 0 : moving(t, dt, (tt) => (u(tt) / 10 ** c.place) * cellH, k).sig;
    const lead = c.place > v.decimals; // a place left of the units: blank while the number is shorter
    const fid = `${sid(id)}-odo${i}`;
    if (sig > 0) defs.push({ id: fid, sy: sig });
    out.push(
      <div key={i} style={{ position: "absolute", left: x + c.x, top: cellTop, width: c.w, height: cellH, overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: 0, filter: sig > 0 ? `url(#${fid})` : undefined }}>
          {rows.map((r) => (lead && r.idx === 0 ? null : (
            <span key={r.idx} style={{ ...runStyle(face, size, 0, 0, 0, paint, id), left: (c.w - adv(face, size, 0, String(r.d))) / 2 - (paint === "gold" ? PAD * size : 0),
              top: glyphTop + r.y - (paint === "gold" ? PAD * size : 0) }}>{r.d}</span>
          )))}
        </div>
      </div>,
    );
  });
  return (
    <>
      <BlurDefs defs={defs} />
      {v.lead ? <Glyphs text={v.lead} face={face} size={size} x={x} base={base} paint={paint} id={id} /> : null}
      {out}
      {v.tail ? <Glyphs text={v.tail} face={face} size={size} x={x + L.tailX} base={base} paint={paint} id={id} /> : null}
    </>
  );
};
