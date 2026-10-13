// The kinetic primitives on one frame, for test/determinism.mjs and a look at the design system: a foil counter with a
// currency sign ("€4.5K" from 40 %), a marker pull on a figure with a cap-aligned %, a supporting line rising per
// character with a foil key word, a connector drawing, a slow push, and the feathered exit. Made-up values; 3.5 s.
import React, { useMemo } from "react";
import { AbsoluteFill } from "remotion";
import { prog } from "../motion";
import { layoutBox } from "./fit";
import { Arrow, FigureGlyphs, FoilDefs, LineMask, Lockup, MarkerReveal, Odometer, Run, Scaled, figureSizes, landedAt, pullOn,
  settleAt, stagger } from "./primitives";
import { counter, useClock } from "./time";
import { TIME, TRACK } from "./tokens";
import { figureParts, figureValue, splitFigure, useFaces } from "./type";

export const KineticKit: React.FC = () => {
  const F = useFaces();
  const { t, dt, fps } = useClock();
  const w = 1080, h = 1920, box = useMemo(() => layoutBox(w, h, [8.6, 92]), []);
  if (!F) return <AbsoluteFill style={{ background: "#5E6460" }} />;
  const D = F.display, O = F.text, k = box.k, id = "kit";
  // 1: a foil counter on its word at 0.2 s, its currency sign at 0.6x
  const money = splitFigure("€4.5K"), mv = figureValue(money.body)!, S1 = 240;
  const c = counter(t, mv.value, mv.decimals, 0.2, 0.7, fps);
  const mParts = figureParts(D, S1, TRACK.figure, money);
  const y1 = box.top + D.cap * S1 + 20;
  // 2: a figure pulled on as ink on its marker at 1.0 s, its % at 0.56x, settling 1.06 -> 1
  const pct = splitFigure("40%"), S2 = 200, y2 = y1 + 120 + D.cap * S2, p2 = figureParts(D, S2, TRACK.figure, pct);
  const x2 = box.left + 20, mk = pullOn(t, x2 + p2.il - S2 * 0.1, x2 + p2.ir + S2 * 0.1, D.cap * S2 + S2 * 0.2, 1.0 - TIME.lead);
  // 3: a supporting line, one character after another, its key word in foil
  const line = "OF A 20K GOAL", key = [5, 6, 7], Ls = 64, y3 = y2 + S2 * 0.1 + 40 + O.cap * Ls, l0 = 1.3;
  // 4: a connector drawing at 1.9 s
  const y4 = y3 + 120;
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg, #8C918C 0%, #5E6460 60%, #3F4440 100%)" }}>
      <Lockup t={t} t0={0.1} out={2.9} box={box} ox={box.left} oy={box.top} w={w} h={h}>
        <FoilDefs id={id} sizes={[...figureSizes(money, S1), ...figureSizes(pct, S2), Ls]} />
        {t >= 0.2 ? (
          <Scaled s={settleAt(t, c.land, fps)} ox={box.left} oy={y1}>
            <FigureGlyphs fig={{ prefix: money.prefix, body: "", suffix: "" }} face={D} size={S1} track={TRACK.figure} x={box.left} base={y1} paint="gold" id={id}
              sheen={prog(t, c.land + TIME.sheenDelay, TIME.sheenDur, "power1.inOut")} />
            <Odometer face={D} size={S1} v={mv} x={box.left + mParts.bx} base={y1} paint="gold" valAt={c.val} t={t} dt={dt} id={id} k={k} />
          </Scaled>
        ) : null}
        <MarkerReveal m={mk} y0={y2 - D.cap * S2 - S2 * 0.1} y1={y2 + S2 * 0.1} id={`${id}-m`} w={w} h={h}>
          <Scaled s={settleAt(t, 1.0 - TIME.lead, fps)} ox={x2} oy={y2}>
            <FigureGlyphs fig={pct} face={D} size={S2} track={TRACK.figure} x={x2} base={y2} paint="ink" />
          </Scaled>
        </MarkerReveal>
        <LineMask on={t < landedAt(l0, line.length)} y0={y3 - O.cap * Ls - 10} y1={y3 + 10}>
          <Run text={line} face={O} size={Ls} track={TRACK.line} x={box.left} base={y3} paint={(j) => (key.includes(j) ? "gold" : "white")}
            rise={stagger(l0, TIME.stagger, TIME.rise, O.cap * Ls * 1.3)} t={t} dt={dt} id={`${id}-l`} k={k} />
        </LineMask>
        <svg width={w} height={h} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
          <Arrow x0={box.left} x1={box.left + 420} y={y4} p={prog(t, 1.9, TIME.connectorDur, "power3.out")} sw={11} hl={24} k={k} />
        </svg>
      </Lockup>
    </AbsoluteFill>
  );
};
