// kinetic_number: one key figure ("€4.5K", "340", "40%") on its spoken word, with an optional sub-line of words
// under it, each on its own word. Copies NumberChain.tsx's shape (props, clock, fit, lockup, paint); references/
// kinetic.md has the props, tokens.ts every shared size, colour and time. Variants:
//   - hook (default): the figure pulled on as ink on its highlighter marker (1.06 -> 1 settle), the lockup centred on
//     the grid: no empty side;
//   - counter: the same marker, the figure counting inside it from 40% of its value (time.ts counter, an Odometer
//     whose width never changes) to land on its word (land_at); the landing hit (the settle) fires on the first frame
//     the value reads final;
//   - tally: a counter beside a grid of up to 30 tiles that fill as the count passes each one's share, the last
//     with a short flare;
//   - stamp: a hook with a word (REJECTED, SOLD OUT) stamped across the figure on its word. Any variant may carry a
//     stamp: as it comes the marker is pulled off the figure and hands it to the foil (a stacked layer), so the
//     figure stays key-coloured and the stamp carries the marker's key plate.
// The sub-line rises per character through its mask no earlier than the figure's landing + 0.15 s; key words in
// the foil. The lockup holds at least 1.2 s after its last landing, pushes 1.5% and leaves in one feathered sweep.
// props: num, at, variant?, land_at?, sub?: [{text, at?, key?}], stamp?: {text, at?}, tiles? (tally, 1-30), out_at?,
//        band? ([top, bottom] % of the frame height), hide_captions? (default true: StyleEdit.tsx).
import React, { useMemo } from "react";
import { prog } from "../motion";
import type { TP } from "../Templates";
import { layoutBox, fitDown } from "./fit";
import { Behind, FigureGlyphs, FoilDefs, Glyphs, LineMask, MarkerReveal, Lockup, Odometer, Run, Scaled, f2, figureSizes, landedAt, lerp,
  odometerLayout, pullOff, pullOn, settleAt, stagger } from "./primitives";
import { counter, exitAt, labelStart, toFrame, useClock } from "./time";
import { EASE, FOIL, KEY, PERCENT_K, PREFIX_K, TIME, TRACK, UNDER } from "./tokens";
import { Face, Faces, Figure, Value, adv, baseOff, figureParts, figureValue, ink, runW, splitFigure, useFaces } from "./type";

export const VARIANTS = ["hook", "counter", "tally", "stamp"] as const;
type Variant = (typeof VARIANTS)[number];
type Word = { text: string; at: number; key: boolean };
type Spec = { num: string; at: number; variant: Variant; land_at?: number; sub: Word[]; stamp?: { text: string; at: number }; tiles: number };

// The format's own proportions (shares of the figure's size S unless named): the sub-line's cap height against the
// figure's, the gap above it; the stamp's type against the figure's, its padding, tracking (em), tilt, slam, squash
// and ring (s), its jolt (frames) and its plate (ink at 94%: the footage barely shows through); the tally's tiles.
const SUB = { cap: 0.31, gap: 0.085 };
const STAMP = { cap: 0.24, padX: 0.11, padY: 0.09, track: 0.06, tilt: -6, from: 1.45, slam: 0.13, squash: 0.03, ring: 0.3, shake: 3,
  plate: "rgba(11,11,11,0.94)" };
const TILE = { gap: 0.22, max: 30, pop: 0.55, flare: 6 };
/** A tile's empty well (the goal track's): white at 14% with a 1 px border. */
const WELL = "rgba(255,255,255,0.14)", WELL_LINE = "rgba(255,255,255,0.32)";
/** A counter with no land_at lands this long after its word. */
const COUNT_S = 0.35;

/** The props as drawn. Throws on what cannot be drawn; a missing time falls back to a deterministic spread. */
export const numberSpec = (p: Record<string, any>): Spec => {
  if (p.num === undefined || p.num === null || String(p.num).trim() === "") throw new Error("kinetic_number has no num");
  const num = String(p.num);
  const variant = (p.variant ?? "hook") as Variant;
  if (!VARIANTS.includes(variant)) throw new Error(`kinetic_number variant ${JSON.stringify(p.variant)}: use ${VARIANTS.join(", ")}`);
  const at = typeof p.at === "number" ? p.at : typeof p.word_at === "number" ? p.word_at : 0.1;   // word_at: the trigger word (plan.py)
  const v = figureValue(splitFigure(num).body);
  if ((variant === "counter" || variant === "tally") && !v) throw new Error(`kinetic_number ${variant} needs a number in num, got ${JSON.stringify(num)}`);
  if (p.sub !== undefined && !Array.isArray(p.sub)) throw new Error("kinetic_number sub is a list of {text, at, key?}");
  const sub = (p.sub ?? []).map((s: any, j: number) => {
    if (!s || String(s.text ?? "").trim() === "") throw new Error(`kinetic_number sub ${j} has no text`);
    return { text: String(s.text).trim(), at: typeof s.at === "number" ? s.at : at + 0.6 + j * 0.25, key: !!s.key };
  });
  if (variant === "stamp" && !p.stamp) throw new Error("kinetic_number stamp needs stamp: {text, at}");
  if (p.stamp && String(p.stamp.text ?? "").trim() === "") throw new Error("kinetic_number stamp has no text");
  const stamp = p.stamp ? { text: String(p.stamp.text).trim(), at: typeof p.stamp.at === "number" ? p.stamp.at : at + 1.2 } : undefined;
  if (p.tiles !== undefined && !(Number.isInteger(p.tiles) && p.tiles >= 1 && p.tiles <= TILE.max))
    throw new Error(`kinetic_number tiles ${JSON.stringify(p.tiles)}: a whole number from 1 to ${TILE.max}`);
  const tiles = variant !== "tally" ? 0 : p.tiles ?? Math.max(1, Math.min(TILE.max, Math.round(v!.value)));
  return { num, at, variant, land_at: typeof p.land_at === "number" ? p.land_at : undefined, sub, stamp, tiles };
};

/** A counting figure's parts at `size`: like figureParts, its body the odometer's fixed width (tabular digits). */
const countParts = (f: Face, size: number, fig: Figure, v: Value) => {
  const ps = size * PREFIX_K, ss = size * PERCENT_K, gap = size * 0.035;
  const odo = odometerLayout(f, size, v);
  const pw = fig.prefix ? runW(f, ps, 0, fig.prefix) : 0, sw = fig.suffix ? runW(f, ss, 0, fig.suffix) : 0;
  const bx = pw ? pw + gap : 0, sx = bx + odo.w + (sw ? gap : 0);
  const il = fig.prefix ? ink(f, ps, 0, fig.prefix).il : (odo.cells[0].w - adv(f, size, 0, "0")) / 2;
  const ir = fig.suffix ? sx + ink(f, ss, 0, fig.suffix).ir : bx + odo.w - (v.tail ? 0 : (odo.cells[odo.cells.length - 1].w - adv(f, size, 0, "0")) / 2);
  return { ps, ss, px: 0, bx, sx, pw, bw: odo.w, sw, w: sx + sw, il, ir };
};

/** The tally's grid for n tiles beside a marker mH tall: the fewest rows (2 or more when n > 3) whose width fits. */
const tileGrid = (n: number, mH: number, maxW: number) => {
  for (let r = n <= 3 ? 1 : 2; r <= 6; r++) {
    const pitch = (mH + (mH / r) * TILE.gap / (1 + TILE.gap)) / r, tile = pitch / (1 + TILE.gap), cols = Math.ceil(n / r);
    const gw = cols * pitch - (pitch - tile);
    if (gw <= maxW || r === 6) return { rows: r, cols, pitch, tile, gw, ok: gw <= maxW };
  }
  throw new Error("unreachable");
};

const solve = (F: Faces, sp: Spec, w: number, h: number, band: unknown) => {
  const D = F.display, O = F.text, box = layoutBox(w, h, band), k = box.k;
  const fig = splitFigure(sp.num);
  const v = sp.variant === "counter" || sp.variant === "tally" ? figureValue(fig.body) : null;
  const words = sp.sub.map((s) => s.text.toUpperCase());
  const line = words.join(" ");
  const stampText = sp.stamp?.text.toUpperCase() ?? "";
  const at = (S: number) => {
    const padX = S * 0.1, padY = S * 0.1;
    const g = v ? countParts(D, S, fig, v) : figureParts(D, S, TRACK.figure, fig);
    const mW = g.ir - g.il + 2 * padX, mH = D.cap * S + 2 * padY;
    const Ss = Math.max((D.cap * S * SUB.cap) / O.cap, 30 * k), gapS = S * SUB.gap;
    const subW = line ? runW(O, Ss, TRACK.line, line) : 0;
    const gx = S * 0.16;
    const grid = sp.tiles ? tileGrid(sp.tiles, mH, box.width - mW - gx) : null;
    const rowW = mW + (grid ? gx + grid.gw : 0);
    // the stamp: a key plate across the figure's lower half, as wide as its word (never past the grid when tilted)
    let Ts = S * STAMP.cap, plate = { w: 0, h: 0 };
    if (stampText) {
      const fitPlate = (T: number) => ({ w: runW(D, T, STAMP.track, stampText) + 2 * S * STAMP.padX, h: D.cap * T + 2 * S * STAMP.padY });
      plate = fitPlate(Ts);
      const rad = (Math.abs(STAMP.tilt) * Math.PI) / 180;
      while (plate.w * Math.cos(rad) + plate.h * Math.sin(rad) > box.width && Ts > 12 * k) plate = fitPlate((Ts -= 2 * k));
    }
    const totalH = mH + (line ? gapS + O.cap * Ss : 0);
    return { ok: rowW <= box.width && subW <= box.width && totalH <= box.height && (!grid || grid.ok), padX, padY, g, mW, mH, Ss, gapS, subW,
      gx, grid, rowW, Ts, plate, totalH };
  };
  const fit = fitDown(460 * k, 80 * k, 2 * k, at);
  const S = fit.size;
  // the row (figure, and the tally's grid) centred on the grid; the sub-line centred under it
  const cx = box.left + box.width / 2, rowL = cx - fit.rowW / 2;
  const mk = { a: rowL, b: rowL + fit.mW };
  const fx = mk.a + fit.padX - fit.g.il;   // the figure's origin: its ink sits padX inside the marker
  const mTop = box.top, capTop = mTop + fit.padY, base = capTop + D.cap * S, mBot = base + fit.padY;
  const subBase = mBot + fit.gapS + O.cap * fit.Ss;
  let acc = "";
  const subX = words.map((wd) => {
    const x = cx - fit.subW / 2 + (acc ? adv(O, fit.Ss, TRACK.line, acc + " ") : 0);
    acc += (acc ? " " : "") + wd;
    return x;
  });
  const gridX = mk.b + fit.gx;
  // the stamp's centre: on the figure's ink centre, on its baseline (most of the figure stays clear), raised only as
  // far as its tilted plate needs to stay off the sub-line's caps
  const rad = (Math.abs(STAMP.tilt) * Math.PI) / 180, half = (fit.plate.h * Math.cos(rad) + fit.plate.w * Math.sin(rad)) / 2;
  const stampC = { x: fx + (fit.g.il + fit.g.ir) / 2, y: line ? Math.min(base, subBase - O.cap * fit.Ss - S * 0.02 - half) : base };
  return { ...fit, S, box, k, fig, v, words, line, stampText, cx, mk, fx, mTop, capTop, base, mBot, subBase, subX, gridX, stampC };
};
type L = ReturnType<typeof solve>;

/** The figure as drawn in one paint: static glyphs, or (counting) the odometer with its sign and % around it. */
const FigureLayer: React.FC<{ L: L; F: Faces; paint: "ink" | "gold"; valAt?: (u: number) => number; t: number; dt: number; id: string;
  sheen?: number }> = ({ L, F, paint, valAt, t, dt, id, sheen = -1 }) => {
  const D = F.display;
  if (!L.v || !valAt) return <FigureGlyphs fig={L.fig} face={D} size={L.S} track={TRACK.figure} x={L.fx} base={L.base} paint={paint} id={id} sheen={sheen} />;
  const g = L.g, capTop = L.base - D.cap * L.S;
  return (
    <>
      {L.fig.prefix ? <Glyphs text={L.fig.prefix} face={D} size={g.ps} x={L.fx} base={capTop + D.cap * g.ps} paint={paint} id={id}
        sheen={sheen} sheenW={g.w} sheenX={0} /> : null}
      <Odometer face={D} size={L.S} v={L.v} x={L.fx + g.bx} base={L.base} paint={paint} valAt={valAt} t={t} dt={dt} id={id} k={L.k} />
      {L.fig.suffix ? <Glyphs text={L.fig.suffix} face={D} size={g.ss} x={L.fx + g.sx} base={capTop + D.cap * g.ss} paint={paint} id={id}
        sheen={sheen} sheenW={g.w} sheenX={g.sx} /> : null}
    </>
  );
};

/** The tally's tiles: wells that appear with the lockup, each filled (a key tile popping from TILE.pop to full size)
 *  on the frame the count passes its share; the last one flares as the count lands. No opacity on a scaled layer:
 *  a well fades in by its colours' alpha, a fill pops at full colour and drops its transform once settled. */
const Tiles: React.FC<{ L: L; fills: number[]; t0: number; land: number; t: number; fps: number }> = ({ L, fills, t0, land, t, fps }) => {
  const g = L.grid!, n = fills.length, r = Math.max(2, 3 * L.k);
  const fill = `linear-gradient(180deg, ${FOIL[1][0]} 0%, ${KEY} 45%, ${FOIL[4][0]} 100%)`;
  const flare = 1 - prog(t, land, TILE.flare / fps, EASE.count);
  return (
    <>
      {t >= land && flare > 0 ? (
        <div style={{ position: "absolute", left: L.gridX - g.pitch, top: L.mTop - g.pitch, width: g.gw + 2 * g.pitch, height: L.mH + 2 * g.pitch,
          background: `radial-gradient(closest-side, rgba(255,212,0,${f2(0.45 * flare)}), rgba(255,212,0,0))` }} />
      ) : null}
      {fills.map((tf, i) => {
        const x = L.gridX + (i % g.cols) * g.pitch, y = L.mTop + Math.floor(i / g.cols) * g.pitch;
        const a = prog(t, t0 + i * 0.012, 0.2, EASE.rise);
        const s = t < tf ? 0 : lerp(TILE.pop, 1, prog(t, tf, TIME.settleFrames / fps, EASE.settle));
        return (
          <React.Fragment key={i}>
            {a > 0 ? <div style={{ position: "absolute", left: x, top: y, width: g.tile, height: g.tile, borderRadius: r, boxSizing: "border-box",
              background: `rgba(255,255,255,${f2(0.14 * a)})`, border: `${f2(Math.max(1, L.k))}px solid rgba(255,255,255,${f2(0.32 * a)})` }} /> : null}
            {s > 0 ? <div style={{ position: "absolute", left: x, top: y, width: g.tile, height: g.tile, borderRadius: r, background: fill,
              boxShadow: `inset 0 ${f2(-2 * L.k)}px 0 rgba(138,86,0,0.35)`,
              transform: s < 1 - 1e-5 ? `scale(${s.toFixed(5)})` : undefined }} /> : null}
          </React.Fragment>
        );
      })}
    </>
  );
};

/** The stamp: the word in key type on an ink plate inside a key rule (a rubber stamp's frame), tilted, slamming down
 *  from STAMP.from to 1 onto its word, a small squash, one ring of key colour leaving the plate. Ink, not key, so it
 *  reads apart from the gold figure it crosses; its crisp offset underlay (no blur) lifts it off the footage. */
const Stamp: React.FC<{ L: L; F: Faces; at: number; t: number; fps: number }> = ({ L, F, at, t, fps }) => {
  if (t < at - STAMP.slam) return null;
  const D = F.display, k = L.k, pw = L.plate.w, ph = L.plate.h;
  const s = t < at ? lerp(STAMP.from, 1, prog(t, at - STAMP.slam, STAMP.slam, "power2.in"))
    : 1 - STAMP.squash * (1 - prog(t, at, 3 / fps, "power2.out"));
  const ring = prog(t, at, STAMP.ring, EASE.count), ringS = 1 + 0.22 * ring;
  const box = (dx: number, dy: number, sc: number): React.CSSProperties => ({ position: "absolute", left: L.stampC.x - pw / 2 + dx, top: L.stampC.y - ph / 2 + dy,
    width: pw, height: ph, transformOrigin: "50% 50%",
    transform: `rotate(${STAMP.tilt}deg)${Math.abs(sc - 1) > 1e-5 ? ` scale(${sc.toFixed(5)})` : ""}` });
  const textBase = ph / 2 + (D.cap * L.Ts) / 2, rule = Math.max(2, 3.5 * k), inset = Math.max(3, 7 * k);
  return (
    <>
      {t >= at && ring < 1 ? <div style={{ ...box(0, 0, ringS), boxSizing: "border-box", border: `${f2(4 * k)}px solid rgba(255,212,0,${f2(0.85 * (1 - ring))})` }} /> : null}
      <div style={{ ...box(0, 4 * k, s), background: UNDER }} />
      <div style={{ ...box(0, 0, s), background: STAMP.plate }}>
        <div style={{ position: "absolute", inset, border: `${f2(rule)}px solid ${KEY}` }} />
        <span style={{ position: "absolute", left: 0, width: pw, top: textBase - baseOff(D, L.Ts), textAlign: "center", fontFamily: D.fam, fontWeight: D.weight,
          fontSize: L.Ts, lineHeight: `${f2(L.Ts)}px`, letterSpacing: `${f2(STAMP.track * L.Ts)}px`, paddingLeft: STAMP.track * L.Ts, whiteSpace: "pre",
          color: KEY }}>{L.stampText}</span>
      </div>
    </>
  );
};

/** The stamp's impact: a three-frame jolt of the whole lockup that dies away (translate only; none once over). */
const jolt = (t: number, at: number, fps: number, k: number) => {
  const i = toFrame(t, fps) - toFrame(at, fps);
  if (i < 0 || i >= STAMP.shake) return undefined;
  const amp = 7 * k * (1 - i / STAMP.shake), dir = [[1, -0.6], [-0.7, 0.5], [0.4, -0.2]][i];
  return `translate(${f2(dir[0] * amp)}px, ${f2(dir[1] * amp)}px)`;
};

const Number_: React.FC<TP & { F: Faces }> = ({ p, w, h, dur, id, F }) => {
  const { t, dt, fps } = useClock();
  const sp = useMemo(() => numberSpec(p), [JSON.stringify(p)]);
  const L = useMemo(() => solve(F, sp, w, h, p.band), [F, sp, w, h, JSON.stringify(p.band)]);
  const D = F.display, O = F.text, S = L.S, k = L.k;
  const t0 = sp.at - TIME.lead;
  // the count: from 40% as the marker is pulled on, over the window whose first final frame is land_at (its word):
  // the shown value reads final on the word, never early; the hit fires on `land`
  const cd = useMemo(() => {
    if (!L.v) return 0;
    const want = sp.land_at ?? sp.at + COUNT_S;
    for (let n = 3; n < 20 * fps; n++) if (counter(0, L.v.value, L.v.decimals, t0, n / fps, fps).land >= want - 0.5 / fps) return n / fps;
    return 20;
  }, [L, sp, fps]);
  const c = L.v ? counter(t, L.v.value, L.v.decimals, t0, cd, fps) : null;
  const land = c ? c.land : sp.at;
  // the tally's fills: each tile on the first frame the shown count reaches its share (the ones under 40% in a quick run)
  const fills = useMemo(() => {
    if (!c || !sp.tiles) return [];
    const unit = 10 ** L.v!.decimals;
    return Array.from({ length: sp.tiles }, (_, i) => {
      const need = ((i + 1) * L.v!.value) / sp.tiles;
      for (let f = toFrame(t0, fps); f <= toFrame(c.land, fps); f++) {
        if (Math.round(c.val(f / fps) * unit) / unit >= need - 1e-9) return Math.max(f / fps, t0 + i * 0.02);
      }
      return c.land;
    });
  }, [L, sp, fps]);
  // the sub-line: each word no earlier than the figure's landing + TIME.labelAfter; words starting together run on as one stagger
  const subT: number[] = [];
  sp.sub.forEach((s, j) => {
    const st = labelStart(land, s.at);
    subT.push(j && Math.abs(st - subT[j - 1]) < 0.05 ? subT[j - 1] : st);
  });
  const subRise = L.words.map((_, j) => {
    let before = 0;
    for (let i = j - 1; i >= 0 && subT[i] === subT[j]; i--) before += L.words[i].length + 1;
    return stagger(subT[j] + before * TIME.stagger, TIME.stagger, TIME.rise, O.cap * L.Ss * 1.3);
  });
  const subLanded = L.words.length ? Math.max(...L.words.map((wd, j) => landedAt(subRise[j](0).tIn, wd.length))) : 0;
  const stampAt = sp.stamp ? Math.max(sp.stamp.at, land + TIME.labelAfter) : Infinity;
  const last = Math.max(land, subLanded, Number.isFinite(stampAt) ? stampAt + STAMP.ring : 0);
  const out = exitAt(dur, last, p.out_at);
  // the marker: pulled on at the word; pulled off (handing the figure to the foil) only as a stamp comes
  const on = pullOn(t, L.mk.a, L.mk.b, L.mH, t0);
  const hand = Number.isFinite(stampAt) ? stampAt - TIME.handoffLead : Infinity;
  const m = pullOff(on, L.mk.b, t, hand);
  const sc = settleAt(t, c ? land : t0, fps);
  const sheen = Number.isFinite(hand) ? prog(t, hand + TIME.handoff + 0.04, TIME.sheenDur, EASE.sheen) : -1;
  const gold = L.words.flatMap((_, j) => (sp.sub[j].key ? [j] : []));
  const shake = Number.isFinite(stampAt) ? jolt(t, stampAt, fps, k) : undefined;
  return (
    <Lockup t={t} t0={t0} out={out} box={L.box} oy={L.mTop} w={w} h={h}>
      <div style={{ position: "absolute", inset: 0, transform: shake }}>
        {Number.isFinite(hand) ? <FoilDefs id={id} sizes={figureSizes(L.fig, S)} /> : null}
        {gold.map((j) => <FoilDefs key={j} id={`${id}-s${j}`} sizes={[L.Ss]} />)}
        {sp.tiles ? <Tiles L={L} fills={fills} t0={t0} land={land} t={t} fps={fps} /> : null}
        <Behind a={m.a} off={m.off} h={h}>
          <FigureLayer L={L} F={F} paint="gold" valAt={c?.val} t={t} dt={dt} id={id} sheen={sheen} />
        </Behind>
        <MarkerReveal m={m} y0={L.mTop} y1={L.mBot} id={`${id}-m`} w={w} h={h}>
          <Scaled s={sc} ox={L.mk.a + L.mW / 2} oy={L.base}>
            <FigureLayer L={L} F={F} paint="ink" valAt={c?.val} t={t} dt={dt} id={id} />
          </Scaled>
        </MarkerReveal>
        {L.words.length ? (
          <LineMask on={t < subLanded} y0={L.subBase - O.cap * L.Ss - 10 * k} y1={L.subBase + 10 * k}>
            {L.words.map((wd, j) => (
              <Run key={j} text={wd} face={O} size={L.Ss} track={TRACK.line} x={L.subX[j]} base={L.subBase} paint={sp.sub[j].key ? "gold" : "white"}
                rise={subRise[j]} t={t} dt={dt} id={`${id}-s${j}`} k={k} />
            ))}
          </LineMask>
        ) : null}
        {sp.stamp ? <Stamp L={L} F={F} at={stampAt} t={t} fps={fps} /> : null}
      </div>
    </Lockup>
  );
};

export const KineticNumber: React.FC<TP> = (props) => {
  const F = useFaces();
  return F ? <Number_ {...props} F={F} /> : null;
};
