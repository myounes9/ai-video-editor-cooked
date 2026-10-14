import React from "react";
import {
  AbsoluteFill,
  CalculateMetadataFunction,
  cancelRender,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
  useVideoConfig,
  useCurrentFrame,
} from "remotion";
import { useEffect, useState } from "react";
import { Lottie, LottieAnimationData } from "@remotion/lottie";
import { Anim, AnimCard } from "./Anims";
import { Captions, CaptionStyle, Chunk } from "./Captions";
import { Capture, Mark } from "./Capture";
import { Look, Texture, loadFamily, resolveLook, useFonts } from "./look";
import { Motion, ease, pickMotion, prog, punchAt } from "./motion";
import { Sfx } from "./Sfx";
import { TextItem, Texts } from "./Texts";
import { SceneCard, SceneView, TR_S, Transition, footageX, phases, sceneGrounds } from "./Scene";
import { captionFade, groundCovers } from "./ground";
import { Ground, onGround } from "./look";
import { KINETIC, hidesCaptions } from "./kinetic";

// Shapes follow skills/style-edit/references/contracts.md "plan.json". Times are seconds on the cut's timeline.
// origin: the top centre of the head over the zoom, % of the frame (plan.py from face.json): the face holds its place, the hair never rises into a card.
type Zoom = { start: number; end: number; scale: number; kind: "punch" | "push"; ease_s: number; ease?: string; origin?: [number, number] };
// A slow sideways drift of the footage (the creator's camera.pan_per_min): from -> to, % of the width.
type Pan = { start: number; end: number; from: number; to: number };
export type Card = {
  src?: string; // an image or Lottie file, or
  anim?: Anim; // a built animation (Anims.tsx)
  start: number;
  end: number;
  trigger_word?: string;
  entrance: "pop" | "slide" | "fade" | "scale" | "cut"; // cut: the creator's measured hard cut (props.enter)
  box: [number, number, number, number];
  lane?: string; // "logo": the logo tiles' own lane
  size?: [number, number]; // image px (capture.mjs writes it), so a capture fits at its own ratio
  highlight?: { rects: [number, number, number, number][] }; // the sentence's lines, fractions of the image
  marks?: Mark[]; // capture marks, rects in image px (references/motion.md)
  format?: "shot" | "browser" | "sticker" | "plain"; // how an image card is drawn (default shot); plain = the old flat capture
  props?: Record<string, unknown>; // extra props for the format: url, label, crop, rotate, zoom, cursor; a Lottie: texts (layer name -> words)
  layout?: "scene" | "box"; // scene: a full-frame cut-away on the look's ground (Scene.tsx)
  transition_in?: Transition; // scene only: match | iris | push | block | wipe | fade | cut
  transition_out?: Transition;
  focus?: [number, number]; // scene only: where match / iris open from, % of the frame (the face)
  ground?: Ground; // scene only: ground | ink | accent (default: those in turn, scene by scene)
  layer?: "behind"; // above the footage, under the speaker's cutout (matte.py): tucks behind the head and shoulders
  key?: [number, number, number, number]; // behind: the region plan.py keeps clear of the head, % of the frame
};
// The speaker cut out of the cut (matte.py): a folder of RGBA PNGs (000000.png = frame `from`), frames from..to of the cut.
type Cutout = { src: string; from: number; to: number }; // src/<frame of the cut>.png, frames from..to (matte.py)
// "split": the visual in a top panel on `ground`, the speaker in a window under the seam. Percent of the frame.
type Layout = {
  mode: "overlay" | "split";
  ground: string;
  seam: number;
  art: [number, number, number, number];
  speaker: { scale: number; x: number; y: number; origin: [number, number] };
  caption_full_y: number;
};
// "letterbox": black 9:16, the landscape cut as a band, a title above it, one photo over the opening line. % of the frame.
type Letterbox = {
  mode: "letterbox";
  band: [number, number, number, number];
  title: string;
  title_box: [number, number, number, number];
  title_px: number;
  card?: { src: string; to: number; box: [number, number, number, number] };
};
export type Plan = {
  video: string;
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
  captions: { style: CaptionStyle; chunks: Chunk[] };
  zooms: Zoom[];
  cards: Card[];
  layout?: Layout | Letterbox;
  look?: Partial<Look>; // references/motion.md; default: the editorial look
  motion?: string | { personality?: string }; // snappy | smooth | punchy | calm
  cutouts?: Cutout[];
  pans?: Pan[];
  cover?: Cover;
  texts?: TextItem[]; // a card edit's title pill, running numbered list and X stamp (Texts.tsx)
};
// An audio-only clip (clips.py trim): the show's cover over a blurred, dimmed copy of itself. box: % of the frame.
// push: the cover's scale at the end; ground_push: the ground's scale at the start (it eases back to 1 as the
// cover grows); pulses: sentence starts, each a small punch.
export type Cover = { src: string; box: [number, number, number, number]; push: number; ground_push: number;
  pulse: number; pulses: number[] };

/** Cover and ground move together on one sine.inOut over the whole clip, in log space, so neither stops
 *  until the clip ends. */
const CoverView: React.FC<{ c: Cover; t: number; dur: number; m: Motion; width: number; height: number }> = ({ c, t, dur, m, width, height }) => {
  const p = prog(t, 0, dur, "sine.inOut");
  const [x, y, w, h] = c.box;
  const u = Math.min(width, height) / 100;
  const img = staticFile(c.src);
  return (
    <AbsoluteFill style={{ backgroundColor: "#000", overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `translateY(${m.drift * u * p}px) scale(${1.1 * Math.pow(c.ground_push, 1 - p)})` }}>
        <Img src={img} style={{ width: "100%", height: "100%", objectFit: "cover", filter: "blur(40px) brightness(0.3)" }} />
      </AbsoluteFill>
      <div style={{ position: "absolute", left: (x / 100) * width, top: (y / 100) * height, width: (w / 100) * width,
        height: (h / 100) * height, transform: `scale(${Math.pow(c.push, p) * punchAt(t, c.pulses, c.pulse)})` }}>
        <Img src={img} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
      </div>
    </AbsoluteFill>
  );
};

export const calculateMetadata: CalculateMetadataFunction<Plan> = ({ props }) => ({
  width: props.width,
  height: props.height,
  fps: props.fps,
  durationInFrames: props.durationInFrames,
});

// Faces sit in the upper middle of a talking-head frame, so zooms grow from there
// and the head stays in shot.
const ZOOM_ORIGIN = "50% 30%";

// Zoom timing. A punch keeps its speed but never snaps: it travels in PUNCH_S on an ease-out, in and back out.
// A push is a camera move: at least PUSH_MIN_S each way, on the creator's fitted ease or a long sine.inOut.
const PUNCH_S = 0.16;
const PUNCH_EASE = "power2.out";
const PUSH_MIN_S = 0.8;
const PUSH_EASE = "sine.inOut";

/** The footage's zoom at t: scale and the point it grows from. Scale moves in log space (scale ** p), so the
 *  perceived speed is the same zooming in and out. Sub-pixel: nothing is rounded. */
export const zoomAt = (t: number, zooms: Zoom[]): { k: number; origin: string } => {
  const zs = [...zooms].sort((a, b) => a.start - b.start);
  for (let i = 0; i < zs.length; i++) {
    const z = zs[i], next = zs[i + 1]?.start ?? Infinity;
    const origin = z.origin ? `${z.origin[0]}% ${z.origin[1]}%` : ZOOM_ORIGIN;
    const push = z.kind === "push" && z.ease_s > 0;
    const tail = push ? 0 : Math.min(PUNCH_S, Math.max(0, next - z.end));
    if (t < z.start || t >= z.end + tail) continue;
    let p: number;
    if (push) {
      const e = Math.min(Math.max(PUSH_MIN_S, z.ease_s), (z.end - z.start) / 2);
      const f = ease(z.ease ?? PUSH_EASE);
      p = t < z.start + e ? f((t - z.start) / e) : t > z.end - e ? f((z.end - t) / e) : 1;
    } else {
      const f = ease(z.ease && z.ease !== "none" ? z.ease : PUNCH_EASE);
      p = t < z.end ? f(Math.min(1, (t - z.start) / PUNCH_S)) : 1 - f(Math.min(1, (t - z.end) / PUNCH_S));
    }
    return { k: Math.pow(z.scale, Math.max(0, Math.min(1, p))), origin };
  }
  return { k: 1, origin: ZOOM_ORIGIN };
};
const zoomScale = (t: number, zooms: Zoom[]) => zoomAt(t, zooms).k;

/** The footage's pan offset (% of the width) and the scale that keeps its edge out of frame. */
const panAt = (t: number, pans: Pan[] = []) => {
  let x = 0;
  for (const p of pans) if (t >= p.start) x = p.from + (p.to - p.from) * prog(t, p.start, p.end - p.start, "sine.inOut");
  return { x, k: 1 + (2 * Math.abs(x)) / 100 };
};

// A designer's Lottie, as After Effects (bodymovin) exports it. Text layers name a font in fonts.list by fName;
// lottie-web reads the weight from fStyle only for bold, black, medium, regular and light/thin, so ExtraBold or
// SemiBold with no fWeight draws at 400. These fill fWeight from the style name.
const LOTTIE_WEIGHTS: Record<string, number> = { thin: 100, hairline: 100, extralight: 200, ultralight: 200, light: 300,
  regular: 400, normal: 400, book: 400, roman: 400, medium: 500, semibold: 600, demibold: 600, bold: 700, extrabold: 800,
  ultrabold: 800, black: 900, heavy: 900 };
type LottieFont = { fName: string; fFamily: string; fStyle?: string; fWeight?: string | number; fOrigin?: string; origin?: number;
  fPath?: string };
type LottieLayer = { ty: number; nm?: string; t?: { d?: { k?: { s: { t: string } }[] } } };
const lottieWeight = (f: LottieFont) =>
  Number(f.fWeight) || LOTTIE_WEIGHTS[(f.fStyle ?? "").toLowerCase().replace(/italic|oblique|[\s_-]/g, "")] || 400;

/** A copy of the Lottie with `texts` (text layer name -> words) swapped in, also inside precomps, and every font's
 *  weight filled from its style name. Returns the fonts its text layers draw with. */
const prepareLottie = (raw: LottieAnimationData, texts: Record<string, string>) => {
  const d = structuredClone(raw) as LottieAnimationData & { fonts?: { list?: LottieFont[] }; chars?: unknown[];
    layers?: LottieLayer[]; assets?: { layers?: LottieLayer[] }[] };
  for (const layers of [d.layers, ...(d.assets ?? []).map((a) => a.layers)]) {
    for (const l of layers ?? []) {
      if (l.ty === 5 && l.nm && l.nm in texts) for (const k of l.t?.d?.k ?? []) k.s.t = texts[l.nm];
    }
  }
  // glyphs exported as shapes (chars) need no font
  const fonts = d.chars?.length ? [] : d.fonts?.list ?? [];
  for (const f of fonts) f.fWeight = String(lottieWeight(f));
  return { data: d as LottieAnimationData, fonts };
};

/** A Lottie card. It plays at its own frame rate (a 60 fps Lottie in a 30 fps edit moves 2 of its frames per
 *  frame: @remotion/lottie shows Lottie frame = card frame x playbackRate). Its fonts load through look.tsx before
 *  lottie-web lays out a letter; a family Google Fonts does not have draws in Inter, like the rest of the edit
 *  (check.py lottie_findings warns), and lottie-web's own font loading (a Google CSS link, a URL) is switched off. */
const LottieCard: React.FC<{ src: string; texts?: Record<string, string> }> = ({ src, texts }) => {
  const { fps } = useVideoConfig();
  const [data, setData] = useState<LottieAnimationData | null>(null);
  const [handle] = useState(() => delayRender(`lottie ${src}`));
  const key = JSON.stringify(texts ?? {});
  useEffect(() => {
    let live = true;
    fetch(staticFile(src))
      .then((r) => r.json())
      .then(async (raw: LottieAnimationData) => {
        const { data: d, fonts } = prepareLottie(raw, JSON.parse(key));
        const families = await Promise.all(fonts.map((f) => loadFamily(f.fFamily, [Number(f.fWeight)])));
        fonts.forEach((f, i) => {
          f.fFamily = families[i];
          f.fOrigin = "n";
          f.origin = 0;
          delete f.fPath;
        });
        await document.fonts.ready;
        if (live) setData(d);
      })
      .catch((e) => {
        cancelRender(new Error(`Lottie ${src} did not load: ${e?.message ?? e}`));
        continueRender(handle);
      });
    return () => {
      live = false;
      continueRender(handle);
    };
  }, [src, key, handle]);
  // Released only once the data is on the page: <Lottie> takes its own handle while it renders, so the frame is
  // never ready with the card still empty.
  useEffect(() => {
    if (data) continueRender(handle);
  }, [data, handle]);
  if (!data) return null;
  const rate = Number.isFinite(data.fr) && data.fr > 0 ? data.fr / fps : 1;
  return <Lottie animationData={data} playbackRate={rate} style={{ width: "100%", height: "100%" }} />;
};

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const inOut = (t: number, a: number, b: number) => interpolate(t, [a, b], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });

// Timing of the layout's moves, seconds.
const PANEL_T = 0.3; // the split panel opens (and closes) over 2 x this, centred on the card's start (end)
const SWAP_S = 0.5; // overlay: a card landing this soon after the last one leaves swaps in (slide across)
const BRIDGE_S = 1.2; // split: the panel stays open across a gap this short, and the cards swap inside it
const EXIT_S = 0.4;
const CUT_FADE_S = 0.3; // the speaker's cutout fades in and out inside matte.py's 0.5 s handles

/** One card: its entrance, a wipe across when it swaps with a neighbour in the same lane, and its exit.
 *  A built card (anim) animates its own entrance and exit inside its Sequence; this only adds the swap.
 *  prev / next: the neighbouring cards when they swap with this one. covered: split, the panel closes over it. */
export const CardView: React.FC<{ card: Card; t: number; prev?: Card; next?: Card; covered: boolean; light: boolean; look: Look; m: Motion;
  fonts: ReturnType<typeof useFonts>; ground?: Ground }> = ({ card, t, prev, next, covered, light, look, m, fonts, ground }) => {
  const { fps, width, height } = useVideoConfig();
  // an image card is drawn by an overlay format: a floating shot (default), a browser window or a sticker
  if (card.src && !card.anim && !card.src.endsWith(".json") && card.format !== "plain") {
    card = { ...card, anim: { type: card.format ?? "shot", props: { src: card.src, size: card.size, marks: card.marks,
      highlight: card.highlight, ...(card.props ?? {}) } } };
  }
  if (card.layout === "scene") return <SceneView card={card} t={t} look={look} m={m} fonts={fonts} covered={!!next && next.layout === "scene"} ground={ground} />;
  const [x, y, w, h] = card.box;
  const bw = (w / 100) * width, bh = (h / 100) * height;
  const lt = t - card.start, dur = card.end - card.start;
  const SWAP = 0.5 * m.k;
  let transform = "none", opacity = 1, clipPath: string | undefined;
  if (prev) {
    // the new card wipes over the old one from the right edge (transitions-cover), riding in a little
    const p = prog(lt, 0, SWAP, m.move);
    clipPath = `inset(0% 0% 0% ${(1 - p) * 100}%)`;
    transform = `translateX(${(1 - p) * bw * 0.08}px)`;
  } else if (!card.anim) {
    const p = prog(lt, 0, 0.45 * m.k, card.entrance === "pop" ? m.pop : m.enter);
    const e = ({ pop: [`scale(${0.86 + 0.14 * p})`, Math.min(1, p * 2)], slide: [`translateY(${(1 - p) * height * 0.12}px)`, Math.min(1, p * 2)],
      fade: ["none", p], scale: [`scale(${0.92 + 0.08 * p})`, p] } as Record<string, (string | number)[]>)[card.entrance] ?? ["none", 1];
    transform = e[0] as string; opacity = e[1] as number;
  }
  if (next) {
    // covered by the next card: slides back and darkens under it
    const q = prog(t, next.start, SWAP, m.move);
    transform += ` translateX(${-q * bw * 0.06}px) scale(${1 - 0.04 * q})`;
    opacity *= 1 - 0.5 * q;
  } else if (!card.anim && !covered) {
    const q = prog(t, card.end - m.out * 0.5, m.out, m.exit);
    transform += ` scale(${1 - 0.06 * q})`;
    opacity *= 1 - q;
  }
  // A Lottie lays its text out under the transform its box has when it mounts and keeps that layout, and each tab
  // of a parallel render mounts the card at its own first frame: a box scaled or moved by its entrance or exit
  // would draw the letters differently in each tab. So a Lottie card only fades and wipes (it moves on its own).
  if (!card.anim && card.src?.endsWith(".json")) transform = "none";
  return (
    <div style={{ position: "absolute", left: `${x}%`, top: `${y}%`, width: `${w}%`, height: `${h}%`, display: "flex", alignItems: "center",
      justifyContent: "center", transform, opacity, clipPath }}>
      <Sequence from={Math.round(card.start * fps)} layout="none">
        {card.anim ? (
          <AnimCard anim={card.anim} w={bw} h={bh} look={look} m={m} fonts={fonts} dur={dur} light={light} id={`${card.start}`} />
        ) : card.src!.endsWith(".json") ? (
          <LottieCard src={card.src!} texts={card.props?.texts as Record<string, string> | undefined} />
        ) : (
          <Capture src={card.src!} size={card.size} marks={card.marks} highlight={card.highlight} bw={bw} bh={bh} dur={dur} look={look} m={m}
            font={fonts.body} light={light} />
        )}
      </Sequence>
    </div>
  );
};

type Slot = { card: Card; prev?: Card; next?: Card; from: number; to: number; covered: boolean };

/** When each card is on screen and which neighbours it swaps with. Split: cards closer than BRIDGE_S share
 *  one open panel; the last card of a run stays until the panel has closed over it. */
const slots = (cards: Card[], split: boolean): Slot[] => {
  const gap = split ? BRIDGE_S : SWAP_S;
  const lanes = new Map<string, Card[]>();
  for (const c of cards) lanes.set(c.lane ?? "", [...(lanes.get(c.lane ?? "") ?? []), c]);
  const out: Slot[] = [];
  for (const lane of lanes.values()) {
    lane.sort((a, b) => a.start - b.start);
    lane.forEach((c, i) => {
      if (c.layout === "scene") {
        const nx = lane[i + 1];
        const held = nx && nx.layout === "scene" && nx.start - c.end < gap; // the next scene grows over this one
        out.push({ card: c, next: held ? nx : undefined, covered: false, from: c.start, to: held ? nx.start + 1 : c.end + 0.05 });
        return;
      }
      if (c.anim && c.anim.type in KINETIC) {
        // a kinetic card enters and leaves on its own (no swap); the next card in its lane takes the frame at its start
        // (a step tracker's next beat carries on from it: kinetic/StepBuild.tsx join_in)
        const nx = lane[i + 1];
        out.push({ card: c, covered: false, from: c.start, to: Math.min(c.end + EXIT_S / 2, nx ? nx.start : Infinity) });
        return;
      }
      const prev = i > 0 && c.start - lane[i - 1].end < gap ? lane[i - 1] : undefined;
      const next = i + 1 < lane.length && lane[i + 1].start - c.end < gap ? lane[i + 1] : undefined;
      const covered = split && !next;
      const to = next ? next.start + EXIT_S / 2 : c.end + (covered ? PANEL_T : EXIT_S / 2);
      out.push({ card: c, prev, next, covered, from: c.start - (split && !prev ? PANEL_T : 0), to });
    });
  }
  return out;
};

/** How far the split panel is open, 0 (speaker full frame) to 1 (split), from the runs of cards. */
const panelOpen = (t: number, cards: Card[]) => {
  const runs: [number, number][] = [];
  for (const c of [...cards].filter((c) => c.layout !== "scene").sort((a, b) => a.start - b.start)) {
    const last = runs[runs.length - 1];
    if (last && c.start - last[1] < BRIDGE_S) last[1] = Math.max(last[1], c.end);
    else runs.push([c.start, c.end]);
  }
  return Math.max(0, ...runs.map(([a, b]) => Math.min(inOut(t, a - PANEL_T, a + PANEL_T), 1 - inOut(t, b - PANEL_T, b + PANEL_T))));
};

const sceneUp = (cards: Card[], t: number) => cards.find((c) => c.layout === "scene" && t >= c.start && t < c.end);
const words = (v: unknown): string[] => typeof v === "string" ? v.toLowerCase().replace(/\*/g, "").split(/[^\p{L}\p{N}]+/u).filter(Boolean)
    .flatMap((w) => [w, ...(w.match(/\d+/g) ?? [])]) // "200x" also matches a spoken "200"
  : typeof v === "number" ? [String(v)]
  : Array.isArray(v) ? v.flatMap(words) : v && typeof v === "object" ? Object.entries(v).filter(([k]) => !/src|icon|logo|platform/.test(k))
    .flatMap(([, x]) => words(x)) : [];

/** While a scene is up the captions draw in the scene's own ink (white on paper would vanish), and when
 *  the words being said are already the scene's type they are hidden: the scene is the caption. The ink
 *  starts once the transition in is half done (quality.py's "landed"): before that the footage is still
 *  behind the words, and dark ink on it does not read. It ends the moment the leaving scene's ground is
 *  gone from under the captions (ground.ts), not halfway through the exit, when the ground is still there. */
const sceneCaptions = (style: CaptionStyle, chunks: Chunk[], cards: Card[], t: number, look: Look, grounds: Map<unknown, Ground>, m: Motion,
  W: number, H: number, capY: number, split: boolean): CaptionStyle => {
  const half = (TR_S * m.k) / 2;
  const scenes = cards.filter((c) => c.layout === "scene").sort((a, b) => a.start - b.start);
  const inked = (c: Card, i: number) => {
    if (t < c.start + half || t >= c.end) return false;
    const nx = scenes[i + 1];
    if (nx && nx.start - c.end < (split ? BRIDGE_S : SWAP_S)) return true; // held: the next scene grows over it
    const { T, tout, po } = phases(c as SceneCard, t, m);
    return po <= 0 || groundCovers(tout, true, 1 - po, t - (c.end - T), T, W, H, c.focus ?? [50, 30], W / 2, (capY / 100) * H);
  };
  const sc = scenes.find(inked);
  if (!sc) return style;
  const said = words(chunks.find((c) => t >= c.start && t < c.end)?.text ?? "");
  const shown = new Set(words(sc.anim?.props ?? {}));
  if (said.length && said.every((w) => shown.has(w))) return { ...style, present: false };
  const g = onGround(look, grounds.get(sc) ?? "ground");
  return { ...style, color: g.ink, highlight_color: g.ink, emphasis_color: g.ink, stroke: false, box: false, flat: true };
};

/** The letterbox layout: plain on purpose (no zoom, no card styling), the title and the photo hard on and off. */
const LetterboxView: React.FC<Letterbox & { video: string; captions: Plan["captions"]; t: number; m: Motion; font: string | null }> = (
  { title, title_box, title_px, card, video, captions, t, m, font }) => {
  const { height } = useVideoConfig();
  const at = (b: number[]): React.CSSProperties => ({ position: "absolute", left: `${b[0]}%`, top: `${b[1]}%`, width: `${b[2]}%`, height: `${b[3]}%` });
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* the render proxy already is the cut in its band on black (edit.py footage_filter) */}
      {video ? <OffthreadVideo src={staticFile(video)} style={{ width: "100%", height: "100%" }} /> : null}
      {card && t < card.to ? <Img src={staticFile(card.src)} style={{ ...at(card.box), objectFit: "cover", objectPosition: "50% 40%" }} /> : null}
      {font ? <div style={{ ...at(title_box), display: "flex", flexDirection: "column", justifyContent: "flex-end", overflow: "hidden" }}>
        <div style={{ fontFamily: font, fontWeight: 400, fontSize: (title_px / 1920) * height, lineHeight: 1.1, color: "#fff",
          textAlign: "center", textWrap: "balance" } as React.CSSProperties}>{title}</div>
      </div> : null}
      <Captions style={captions.style} chunks={captions.chunks} t={t} m={m} />
      <Sfx />
    </AbsoluteFill>
  );
};

export const StyleEdit: React.FC<Plan> = ({ video, captions, zooms, cards, layout, look: lookIn, motion, cutouts, pans, cover, texts }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  const look = resolveLook(lookIn);
  const m = pickMotion(motion);
  const fonts = useFonts(look);
  const split = layout?.mode === "split";
  if (layout?.mode === "letterbox") return <LetterboxView {...layout} video={video} captions={captions} t={t} m={m} font={fonts.ready ? fonts.body : null} />;
  const grounds = sceneGrounds(cards);
  const capAt = (tt: number) => sceneCaptions(captions.style, captions.chunks, cards, tt, look, grounds, m, width, height,
    split && layout ? layout.caption_full_y : captions.style.y_pct ?? 70, split);
  const capStyle = capAt(t);
  // captions a scene hides fade out and back in (ground.ts captionFade), never gone in one frame
  const sceneFade = cards.some((c) => c.layout === "scene") ? captionFade((tt) => capAt(tt).present === false, t) : 1;
  // a kinetic title says the beat in its own type: the word captions fade out while it is up and come back after it
  // (card props.hide_captions, on by default for the kinetic family: kinetic/index.ts)
  const quiet = cards.filter((c) => hidesCaptions(c.anim));
  const capFade = Math.min(sceneFade, quiet.length ? captionFade((tt) => quiet.some((c) => tt >= c.start && tt < c.end), t) : 1);
  const up = fonts.ready ? slots(cards, split).filter((s) => t >= s.from && t < s.to) : [];
  const view = (s: Slot) => (
    <CardView key={`${s.card.src ?? s.card.anim?.type}${s.card.start}`} card={s.card} t={t} prev={s.prev} next={s.next} covered={s.covered}
      light={split} look={look} m={m} fonts={fonts} ground={grounds.get(s.card)} />
  );
  // Box cards sit under the speaker's window in split; scenes cut away from everything, so they go on top. A kinetic
  // card goes over a scene it shares the frame with (a stat_stack beside a full-frame capture of its numbers).
  const kin = (s: Slot) => !!s.card.anim && s.card.anim.type in KINETIC;
  const cardViews = up.filter((s) => s.card.layout !== "scene" && s.card.layer !== "behind" && !kin(s)).map(view);
  const kineticViews = up.filter((s) => s.card.layout !== "scene" && s.card.layer !== "behind" && kin(s)).map(view);
  const behindViews = up.filter((s) => s.card.layer === "behind").map(view);
  const sceneViews = up.filter((s) => s.card.layout === "scene").map(view);
  if (!split || !layout) {
    const pan = panAt(t, pans);
    const zm = zoomAt(t, zooms);
    const cam: React.CSSProperties = { transform: `translateX(${footageX(t, cards, width, m) + (pan.x / 100) * width}px) scale(${zm.k * pan.k})`,
      transformOrigin: zm.origin };
    return (
      <AbsoluteFill style={{ backgroundColor: "#000" }}>
        <AbsoluteFill style={cam}>
          {video ? <OffthreadVideo src={staticFile(video)} style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : null}
        </AbsoluteFill>
        {cover ? <CoverView c={cover} t={t} dur={durationInFrames / fps} m={m} width={width} height={height} /> : null}
        {behindViews}
        {/* the speaker over the behind cards, on the footage's own move, only while one is up */}
        {(cutouts ?? []).filter((c) => frame >= c.from && frame <= c.to).map((c) => (
          // fades in over the handle before the card (its refined edge differs a little from the raw camera)
          <AbsoluteFill key={c.src} style={{ ...cam, opacity: Math.min(1, c.from === 0 ? 1 : (frame - c.from + 1) / (CUT_FADE_S * fps),
            c.to >= durationInFrames - 1 ? 1 : (c.to - frame + 1) / (CUT_FADE_S * fps)) }}>
            <Img src={staticFile(`${c.src}/${String(frame).padStart(6, "0")}.png`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </AbsoluteFill>
        ))}
        {cardViews}
        {sceneViews}
        {kineticViews}
        {texts?.length ? <Texts items={texts} t={t} width={width} height={height} font={captions.style.font_match} /> : null}
        <AbsoluteFill style={{ opacity: capFade }}><Captions style={capStyle} chunks={captions.chunks} t={t} m={m} /></AbsoluteFill>
        <Sfx />
      </AbsoluteFill>
    );
  }
  // Split. The art sits still on the ground; the speaker's window slides down to uncover it and back up
  // to cover it, one move on one curve. The video inside moves with it so the head stays framed.
  const o = panelOpen(t, cards);
  const { scale, x, y, origin } = layout.speaker;
  const top = (layout.seam / 100) * height * o;
  const k = 1 + (scale - 1) * o;
  const r = height * 0.03 * Math.min(1, top / 40);
  const capY = interpolate(o, [0, 1], [layout.caption_full_y, captions.style.y_pct ?? layout.seam + 4.5]);
  return (
    <AbsoluteFill style={{ backgroundColor: layout.ground }}>
      <Texture look={look} w={width} h={height} id="ground" />
      {behindViews /* split has no cutout: the panel art sits clear of the window anyway */}
      {cardViews}
      {kineticViews}
      <div style={{ position: "absolute", left: 0, top, width, height: height - top, overflow: "hidden",
        borderRadius: `${r}px ${r}px 0 0`, boxShadow: o > 0 ? `0 ${-height * 0.004}px ${height * 0.02}px rgba(0,0,0,${0.12 * o})` : undefined }}>
        <div style={{ position: "absolute", left: -(x / 100) * width * o, top: -(y / 100) * height * o, width: width * k,
          height: height * k, transform: `translateX(${footageX(t, cards, width, m)}px) scale(${zoomScale(t, zooms)})`, transformOrigin: `${origin[0]}% ${origin[1]}%` }}>
          {video ? <OffthreadVideo src={staticFile(video)} style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : null}
        </div>
      </div>
      {sceneViews}
      {texts?.length ? <Texts items={texts} t={t} width={width} height={height} font={captions.style.font_match} /> : null}
      <AbsoluteFill style={{ opacity: capFade }}>
        <Captions style={{ ...capStyle, y_pct: sceneUp(cards, t) ? layout.caption_full_y : capY }} chunks={captions.chunks} t={t} m={m} />
      </AbsoluteFill>
      <Sfx />
    </AbsoluteFill>
  );
};
