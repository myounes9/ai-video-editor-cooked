// cta_follow: the creator's handle and a follow button that presses on "follow", with an optional avatar circle
// (references/kinetic.md). Built like number_chain (NumberChain.tsx), in the family's own language:
//   - a profile lockup centred on the grid: the avatar circle on the left, the handle over the button beside it (no
//     avatar: the handle over the button, centred), fitted to the grid width and the face band at the largest size
//     that fits;
//   - on its word the avatar opens as a circle with a key-colour ring drawing round it, the handle rises per character
//     through its mask and the button wipes in as an empty well (the goal track's: rgba(255,255,255,.14), 1 px rim);
//   - on "follow" the button presses (a short dip, no transform once it is back) and the highlighter marker is pulled
//     across it, leaning, revealing FOLLOWING and a check drawn on in ink: the button lands like a key figure; two
//     rings leave it (stroke alpha, never opacity on a scaled layer);
//   - it holds at least 1.2 s after the press (unless the card ends sooner), pushes 1.5 % and leaves in one sweep.
// props: handle (an "@" is added when missing), at, follow_at, avatar? (an image file: "images/..." or a URL),
//        button? ("Follow"), pressed? ("Following"), out_at?, band?, hide_captions? (default true).
import React, { useMemo } from "react";
import { Img, staticFile } from "remotion";
import { prog } from "../motion";
import type { TP } from "../Templates";
import { layoutBox, fitDown } from "./fit";
import { LineMask, Lockup, Run, Scaled, clamp01, f2, lerp, markerPoly, pullOn, stagger, landedAt } from "./primitives";
import { exitAt, firstLanding, useClock } from "./time";
import { Part, Prober, capsRect } from "./probe";
import { EASE, INK, KEY, LABEL, TIME, TRACK, UNDER, WHITE } from "./tokens";
import { Faces, baseOff, runW, useFaces } from "./type";

/** The well an empty control sits in (goal_bar's track): a faint fill and a 1 px rim, both colour alpha. */
const WELL = "rgba(255,255,255,0.14)", RIM = "rgba(255,255,255,0.42)";
/** Sizes as shares of the lockup's height U (with an avatar, its diameter): the handle's type, the button's height and
 *  its label's type (x the button's height), the gap from the avatar to the column and from the handle to the button.
 *  The avatar's ring stands ring.gap off it, ring.w thick. */
const U_ = { handle: 0.36, button: 0.46, label: 0.44, gapA: 0.13, gapC: 0.13, ring: { gap: 0.03, w: 0.022 } };
/** The cta's own timings (s): the avatar opens and its ring draws from `at` - TIME.lead; the handle rises from at +
 *  handle (before its word, so it reads on the word, as a figure does); the button wipes in from at + button over wipe. The press dips depth over down and returns over up; the check draws
 *  from follow_at + check over checkDur; two rings leave the button at follow_at + rings[i] over ringDur. */
const T_ = { open: 0.35, ringDraw: 0.5, handle: -0.1, button: 0.04, wipe: 0.3, down: 0.07, up: 0.32, depth: 0.08,
  check: 0.12, checkDur: 0.22, rings: [0, 0.13], ringDur: 0.55 };
const src_ = (s: string) => (/^(https?:|data:)/.test(s) ? s : staticFile(s));
/** KEY at alpha a (the rings fade by their colour, never by opacity). */
const keyA = (a: number) => `rgba(${parseInt(KEY.slice(1, 3), 16)},${parseInt(KEY.slice(3, 5), 16)},${parseInt(KEY.slice(5, 7), 16)},${a.toFixed(3)})`;

export type Cta = { handle: string; at: number; follow_at: number; avatar?: string; button: string; pressed: string };
/** The props as drawn: a handle (with its "@"), the card's word and the "follow" word (missing: 0.1 s and at + 0.8 s,
 *  never random). */
export const ctaProps = (p: Record<string, any>): Cta => {
  const raw = String(p.handle ?? "").trim();
  if (!raw || /\s/.test(raw)) throw new Error(`cta_follow needs a handle with no spaces, got "${p.handle ?? ""}"`);
  const at = typeof p.at === "number" ? p.at : 0.1;
  const follow = typeof p.follow_at === "number" ? Math.max(p.follow_at, at + 0.25) : at + 0.8;
  const avatar = typeof p.avatar === "string" && p.avatar.trim() ? p.avatar.trim() : undefined;
  return { handle: raw.startsWith("@") ? raw : `@${raw}`, at, follow_at: follow, avatar,
    button: String(p.button ?? "Follow").toUpperCase(), pressed: String(p.pressed ?? "Following").toUpperCase() };
};

const solve = (F: Faces, c: Cta, w: number, h: number, band: unknown, beside: unknown) => {
  const O = F.text, box = layoutBox(w, h, band, beside), k = box.k, av = !!c.avatar;
  const at = (U: number) => {
    const Hs = Math.max(LABEL.size * k, U * U_.handle), bh = U * U_.button, Ls = bh * U_.label;
    const hw = runW(O, Hs, TRACK.line, c.handle);
    const icon = O.cap * Ls, padB = bh * 0.42, gapI = Ls * 0.4;
    const lw = Math.max(runW(O, Ls, TRACK.label, c.button), runW(O, Ls, TRACK.label, c.pressed));
    const bw = 2 * padB + icon + gapI + lw;
    const ring = av ? U * (U_.ring.gap + U_.ring.w) : 0, aw = av ? U + 2 * ring : 0, gA = av ? U * U_.gapA : 0;
    const colW = Math.max(hw, bw), colH = O.cap * Hs + U * U_.gapC + bh;
    const width = aw + gA + colW, height = Math.max(aw, colH);
    return { ok: width <= box.width && height <= box.height, U, Hs, bh, Ls, hw, icon, padB, gapI, lw, bw, ring, aw, gA, colW, colH, width, height };
  };
  const fit = fitDown((av ? 280 : 320) * k, 96 * k, 2 * k, at);   // with no avatar the column alone may grow taller
  if (!fit.ok) throw new Error(`cta_follow: the handle "${c.handle}" and the button "${c.button}" do not fit the grid at a readable size: ` +
    "a shorter handle or button");
  const x0 = box.left + (box.width - fit.width) / 2, cy = box.top + fit.height / 2, colX = x0 + fit.aw + fit.gA;
  const hBase = cy - fit.colH / 2 + O.cap * fit.Hs, by = hBase + fit.U * U_.gapC;
  // beside an avatar the column hangs from its left edge; alone it is centred
  const hx = av ? colX : colX + (fit.colW - fit.hw) / 2, bx = av ? colX : colX + (fit.colW - fit.bw) / 2;
  return { ...fit, box, k, cx: x0 + fit.aw / 2, cy, hx, hBase, bx, by };
};

/** The button's face at one state: an icon (a plus, or the check drawn on to `check` 0..1) and its label, the pair
 *  centred as if it held the wider label, so both faces share one left edge and FOLLOW runs on into FOLLOWING as the
 *  marker passes (each centred on its own width read as a garble mid-wipe). under: a crisp dark copy 2 px below (no
 *  blur: it may be scaled by the press) to hold white on a bright wall. */
const ButtonFace: React.FC<{ L: ReturnType<typeof solve>; O: Faces["text"]; text: string; color: string; icon: "plus" | "check"; check?: number;
  under?: boolean }> = ({ L, O, text, color, icon, check = 1, under = false }) => {
    const x = (L.bw - (L.icon + L.gapI + L.lw)) / 2;
    const base = L.bh / 2 + (O.cap * L.Ls) / 2, s = L.icon, iy = base - s, sw = Math.max(2.5, L.Ls * 0.13);
    const path = icon === "plus" ? `M${f2(x + s / 2)} ${f2(iy + sw / 2)} V${f2(iy + s - sw / 2)} M${f2(x + sw / 2)} ${f2(iy + s / 2)} H${f2(x + s - sw / 2)}`
      : `M${f2(x + s * 0.06)} ${f2(iy + s * 0.55)} L${f2(x + s * 0.38)} ${f2(iy + s * 0.86)} L${f2(x + s * 0.96)} ${f2(iy + s * 0.14)}`;
    const len = icon === "check" ? s * 1.3 : 0;   // the check's length (both strokes), for drawing it on
    const layer = (c: string, dy: number) => (
      <>
        <svg width={L.bw} height={L.bh} style={{ position: "absolute", left: 0, top: dy, overflow: "visible" }}>
          <path d={path} stroke={c} strokeWidth={sw} fill="none" strokeLinecap="butt" strokeLinejoin="miter"
            strokeDasharray={len ? `${f2(len)} ${f2(len)}` : undefined} strokeDashoffset={len ? f2(len * (1 - check)) : undefined} />
        </svg>
        <span style={{ position: "absolute", left: x + L.icon + L.gapI, top: base - baseOff(O, L.Ls) + dy, fontFamily: O.fam, fontWeight: O.weight,
          fontSize: L.Ls, lineHeight: `${L.Ls}px`, letterSpacing: `${f2(TRACK.label * L.Ls)}px`, whiteSpace: "pre", color: c }}>{text}</span>
      </>
    );
    return <>{under ? layer(UNDER, 2 * L.k) : null}{layer(color, 0)}</>;
  };

/** The layout as rectangles (kinetic/probe.ts). */
export const probe: Prober = (F, p, w, h, dur) => {
  const c = ctaProps(p), L = solve(F, c, w, h, p.band, p.beside), O = F.text;
  firstLanding("cta_follow", c.at, dur);
  const parts: Part[] = [{ kind: "handle", r: capsRect(L.hx, L.hw, L.hBase, O.cap * L.Hs) }, { kind: "button", r: [L.bx, L.by, L.bx + L.bw, L.by + L.bh] }];
  if (c.avatar) parts.push({ kind: "avatar", r: [L.cx - L.aw / 2, L.cy - L.aw / 2, L.cx + L.aw / 2, L.cy + L.aw / 2] });
  return { k: L.k, parts, sizes: { handle: L.Hs } };
};

const Follow: React.FC<TP & { F: Faces }> = ({ p, w, h, dur, id, F }) => {
  const { t, dt } = useClock();
  const c = useMemo(() => ctaProps(p), [p.handle, p.at, p.follow_at, p.avatar, p.button, p.pressed]);
  const L = useMemo(() => solve(F, c, w, h, p.band, p.beside), [F, c, w, h, JSON.stringify(p.band), JSON.stringify(p.beside)]);
  const O = F.text, k = L.k, U = L.U, fa = c.follow_at;
  useMemo(() => firstLanding("cta_follow", c.at, dur), [c, dur]);
  const t0 = c.at - TIME.lead;
  // the avatar and its ring
  const R = U / 2, open = prog(t, t0, T_.open, EASE.settle), ringR = R + U * (U_.ring.gap + U_.ring.w / 2);
  const ringP = prog(t, t0, T_.ringDraw, EASE.draw), circ = 2 * Math.PI * ringR;
  // the handle
  const h0 = c.at + T_.handle, hDist = O.cap * L.Hs * 1.3;
  // the button: wiped in as a well, pressed on "follow", the marker pulled across it
  const b0 = c.at + T_.button, wipe = prog(t, b0, T_.wipe, EASE.draw);
  const s = 1 - T_.depth * prog(t, fa - TIME.lead, T_.down, "power2.out") * (1 - prog(t, fa - TIME.lead + T_.down, T_.up, EASE.settle));
  const m = pullOn(t, 0, L.bw, L.bh, fa - TIME.lead);
  const pill = `inset(0px ${f2((1 - wipe) * L.bw)}px 0px 0px round ${f2(L.bh / 2)}px)`;
  const last = Math.max(fa + T_.check + T_.checkDur, landedAt(h0, c.handle.length), fa + T_.rings[T_.rings.length - 1] + T_.ringDur * 0.5);
  const out = exitAt(dur, last, p.out_at);
  const bcx = L.bx + L.bw / 2, bcy = L.by + L.bh / 2;
  return (
    <Lockup t={t} t0={t0} out={out} box={L.box} oy={L.box.top} w={w} h={h} bridge={p}>
      {c.avatar && open > 0 ? (
        <>
          <div style={{ position: "absolute", left: L.cx - R, top: L.cy - R, width: U, height: U, clipPath: `circle(${f2(R * open)}px at 50% 50%)` }}>
            <Img src={src_(c.avatar)} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
          </div>
          <svg width={w} height={h} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
            <circle cx={L.cx} cy={L.cy + 2.5 * k} r={ringR} fill="none" stroke={UNDER} strokeWidth={U * U_.ring.w + 2 * k}
              strokeDasharray={`${f2(circ * ringP)} ${f2(circ)}`} transform={`rotate(-90 ${f2(L.cx)} ${f2(L.cy + 2.5 * k)})`} />
            <circle cx={L.cx} cy={L.cy} r={ringR} fill="none" stroke={KEY} strokeWidth={U * U_.ring.w}
              strokeDasharray={`${f2(circ * ringP)} ${f2(circ)}`} transform={`rotate(-90 ${f2(L.cx)} ${f2(L.cy)})`} />
          </svg>
        </>
      ) : null}
      <LineMask on={t < landedAt(h0, c.handle.length)} y0={L.hBase - O.cap * L.Hs - 12 * k} y1={L.hBase + O.cap * L.Hs * 0.35}>
        <Run text={c.handle} face={O} size={L.Hs} track={TRACK.line} x={L.hx} base={L.hBase} paint="white"
          rise={stagger(h0, TIME.stagger, TIME.rise, hDist)} t={t} dt={dt} id={`${id}-h`} k={k} />
      </LineMask>
      {/* the rings the press sends out: the pill's own shape, growing, fading by their stroke's alpha */}
      <svg width={w} height={h} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        {T_.rings.map((d, i) => {
          const q = prog(t, fa + d, T_.ringDur, EASE.pull);
          if (q <= 0 || q >= 1) return null;
          const g = lerp(0, L.bh * 0.85, q), a = 0.9 * (1 - q) ** 1.5;
          return <rect key={i} x={L.bx - g} y={L.by - g} width={L.bw + 2 * g} height={L.bh + 2 * g} rx={L.bh / 2 + g}
            fill="none" stroke={keyA(a)} strokeWidth={lerp(5, 1.5, q) * k} />;
        })}
      </svg>
      {wipe > 0 ? (
        <Scaled s={s} ox={bcx} oy={bcy}>
          <div style={{ position: "absolute", left: L.bx, top: L.by, width: L.bw, height: L.bh, clipPath: pill }}>
            <div style={{ position: "absolute", inset: 0, background: WELL, border: `${f2(Math.max(1, k))}px solid ${RIM}`, borderRadius: L.bh / 2,
              boxSizing: "border-box" }} />
            <ButtonFace L={L} O={O} text={c.button} color={WHITE} icon="plus" under />
            {/* pressed: the flat key colour pulled across, leaning, and the ink face only where it already is */}
            {m.b - m.a > 0.5 ? (
              <div style={{ position: "absolute", inset: 0, clipPath: markerPoly(m, 0, L.bh) }}>
                <div style={{ position: "absolute", inset: 0, background: KEY }} />
                <ButtonFace L={L} O={O} text={c.pressed} color={INK} icon="check" check={clamp01(prog(t, fa + T_.check, T_.checkDur, EASE.draw))} />
              </div>
            ) : null}
          </div>
        </Scaled>
      ) : null}
    </Lockup>
  );
};

export const CtaFollow: React.FC<TP> = (props) => {
  const F = useFaces();
  return F ? <Follow {...props} F={F} /> : null;
};
