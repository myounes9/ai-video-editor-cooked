// Proves each GSAP plugin is deterministic under Remotion: the same frame rendered in two separate
// processes, and a still against the same frame inside a sequential (video) frame render, must be
// pixel-identical. Then the parallel render: every frame of each plugin, every ease, three real cards
// (chat from Overlays.tsx, social_post from Templates.tsx, the Lottie fixture with a text layer through
// StyleEdit.tsx LottieCard, entering with a pop) and a product page zoom (ProductVideo.tsx, on two
// tiles ffmpeg draws), rendered across 6 Chrome tabs (--tabs; each tab
// jumps several frames at a time and lands on held frames from different places, as a real render does),
// must equal the same frame rendered in one tab in order. The kinetic family runs too: its primitives (KineticKit)
// and each format's case marked "determinism" in test/kinetic/*.json. Prints each differing frame with its largest
// channel difference (0-255) and exits 1 on any difference.
//   node test/determinism.mjs [outDir] [--only <case-substring>] [--tabs <n>]
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderFrames, renderStill, selectComposition } from "@remotion/renderer";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PLUGINS = ["drawsvg", "morphsvg", "motionpath", "customease", "customwiggle", "physics2d", "physics2d-friction", "splittext"];
const FRAME = 23;
// Real cards on the Preview composition, as test/templates.mjs renders them; no image assets needed.
const CARDS = {
  "card-chat": { dur: 3.6, light: true, card: { anim: { type: "chat", props: { app: "Assistant", messages: [
    { from: "user", text: "make it shorter", at: 0.4 }, { from: "app", text: "Cut to 40 seconds.", at: 1.3 }] } }, box: [6, 14, 88, 34] } },
  "card-post": { dur: 4, light: true, look: { preset: "editorial-dark" }, card: { anim: { type: "social_post", props: { platform: "x",
    name: "jack", handle: "jack", text: "just setting up my twttr", highlight: "setting up", likes: "309,515", replies: "18,073",
    time: "Mar 21, 2006" } }, box: [4, 12, 92, 37] } },
  // lottie-web lays text out under its box's transform when it mounts, and each tab mounts the card at its own
  // first frame: test/public/lottie/title-60fps.json, landing at 0.5 s. Its bar's moving edge is let off a few
  // pixels at 8/255: Chrome repaints only what moved since the last frame, and on 3 of these frames that lands
  // one edge pixel 7/255 off a frame painted whole (the bar's SVG path is the same, logged both ways). Text
  // laid out under a scaled box differs on its glyph edges on most frames, over 60 to 300 px (up to 95/255).
  "card-lottie": { dur: 3, card: { src: "lottie/title-60fps.json", start: 0.5, box: [10, 30, 80, 25] }, edge: { max: 8, px: 4 } },
};
// The kinetic family: its primitives on one frame (KineticKit), and every case in test/kinetic/*.json marked
// "determinism": true (one per format, over a gradient ground: no assets).
const KINETIC = Object.fromEntries(fs.readdirSync(path.join(HERE, "kinetic")).filter((f) => f.endsWith(".json")).sort()
  .flatMap((f) => JSON.parse(fs.readFileSync(path.join(HERE, "kinetic", f), "utf8")))
  .filter((c) => c.determinism).map(({ name, determinism, ...c }) => [`kinetic-${name}`, c]));
// A page shot: the camera zooms from the whole window onto a small part of it while scrolling.
const PRODUCT = { width: 1920, height: 1080, fps: 30, durationInFrames: 90, variant: "linear", url: "https://example.com",
  brand: { ground: "#FFFFFF", ink: "#0A0A0A", muted: "#6B6B6B", accent: "#0A0A0A", dark: false, radius_px: 8,
    display: { family: "Inter", weight: 600, tracking_em: -0.02 }, body: { family: "Inter", weight: 400 }, fonts: [] },
  page: { vw: 1440, vh: 900, height: 1800, domain: "example.com",
    tiles: [{ src: "images/tile-0.jpg", y: 0, size: [2880, 1800] }, { src: "images/tile-1.jpg", y: 900, size: [2880, 1800] }] },
  shots: [{ kind: "page", start: 0, end: 3, keys: [{ t: 0, scroll: 0, rect: [0, 0, 1440, 900] }, { t: 2.2, scroll: 200, rect: [500, 300, 360, 225] }] }] };
const argv = process.argv.slice(2);
const [mode, ...args] = argv;

if (mode === "child") {
  const [serveUrl, plugin, out] = args;
  const inputProps = { plugin };
  const composition = await selectComposition({ serveUrl, id: "Proof", inputProps });
  await renderStill({ serveUrl, composition, inputProps, output: out, frame: FRAME });
  process.exit(0);
}

const opt = (name, d) => (argv.includes(name) ? argv[argv.indexOf(name) + 1] : d);
const only = opt("--only", "");
const PARALLEL = Math.max(4, Number(opt("--tabs", 6)));   // tabs in the parallel render: 4 or more, so each tab skips frames
if (!Number.isFinite(PARALLEL)) throw new Error(`--tabs ${opt("--tabs")}: give a number`);
const outDir = path.resolve(argv.find((a, i) => !a.startsWith("--") && !String(argv[i - 1]).startsWith("--")) ?? "out/determinism");
fs.mkdirSync(outDir, { recursive: true });
const pub = path.join(outDir, "public");
fs.mkdirSync(path.join(pub, "images"), { recursive: true });
fs.cpSync(path.join(HERE, "public"), pub, { recursive: true });   // the Lottie fixture
for (const [f, src] of [["tile-0.jpg", "testsrc2=s=2880x1800"], ["tile-1.jpg", "mandelbrot=s=2880x1800"]])
  spawnSync("ffmpeg", ["-v", "error", "-y", "-f", "lavfi", "-i", src, "-frames:v", "1", "-q:v", "2", path.join(pub, "images", f)]);
const serveUrl = await bundle({ entryPoint: path.join(HERE, "..", "src", "index.ts"), publicDir: pub });
// decode to raw RGBA: PNG bytes can differ only by encoder metadata. A file that does not decode stops the
// test: two missing frames must never compare as the same.
const raw = (f) => {
  const r = spawnSync("ffmpeg", ["-v", "error", "-i", String(f), "-f", "rawvideo", "-pix_fmt", "rgba", "-"], { maxBuffer: 1 << 28 });
  if (r.status !== 0 || !r.stdout?.length) throw new Error(`could not decode ${f}: ${r.stderr}`);
  return r.stdout;
};
const same = (a, b) => Buffer.compare(raw(a), raw(b)) === 0;
/** Largest channel difference (0-255) and the count of pixels that differ; identical bytes skip the decode. */
const delta = (a, b) => {
  const [fa, fb] = [fs.readFileSync(a), fs.readFileSync(b)];
  if (fa.length && Buffer.compare(fa, fb) === 0) return { max: 0, px: 0 };
  const [x, y] = [raw(a), raw(b)];
  if (x.length !== y.length) return { max: 255, px: -1 };
  let max = 0, px = 0;
  for (let i = 0; i < x.length; i += 4) {
    const d = Math.max(Math.abs(x[i] - y[i]), Math.abs(x[i + 1] - y[i + 1]), Math.abs(x[i + 2] - y[i + 2]), Math.abs(x[i + 3] - y[i + 3]));
    if (d) { px++; if (d > max) max = d; }
  }
  return { max, px };
};
const frames = async (id, inputProps, dir, concurrency) => {
  const composition = await selectComposition({ serveUrl, id, inputProps });
  fs.rmSync(dir, { recursive: true, force: true });
  await renderFrames({ serveUrl, composition, inputProps, outputDir: dir, imageFormat: "png",
    frameRange: [0, composition.durationInFrames - 1], onStart: () => {}, onFrameUpdate: () => {}, concurrency });
  return fs.readdirSync(dir).filter((f) => f.endsWith(".png")).sort().map((f) => path.join(dir, f));
};

const results = { still: {}, parallel: {} };
const inOrder = {};   // the one-tab, in-order render of each case, shared by both checks
let bad = 0;
for (const plugin of PLUGINS.filter((p) => p.includes(only))) {
  const a = path.join(outDir, `${plugin}-a.png`), b = path.join(outDir, `${plugin}-b.png`);
  for (const f of [a, b]) {
    const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url), "child", serveUrl, plugin, f], { stdio: "inherit" });
    if (r.status !== 0) throw new Error(`${plugin}: child render failed`);
  }
  const seq = inOrder[plugin] = await frames("Proof", { plugin }, path.join(outDir, `${plugin}-c1`), 1);
  const r = results.still[plugin] = { two_processes: same(a, b), still_vs_video_frame: same(a, seq[FRAME]) };
  bad += !r.two_processes + !r.still_vs_video_frame;
  console.log(plugin, JSON.stringify(r));
}

const cases = [...[...PLUGINS, "eases"].map((plugin) => [plugin, "Proof", { plugin }]),
  ...Object.entries({ ...CARDS, ...KINETIC }).map(([name, { edge, ...c }]) => [name, "Preview",
    { width: 1080, height: 1920, ...c, card: { start: 0, end: c.dur, entrance: "pop", ...c.card } }, edge]),
  ["kinetic-kit", "KineticKit", {}],
  ["product-page", "ProductVideo", PRODUCT]].filter(([n]) => n.includes(only));
const t0 = Date.now();
let total = 0, differ = 0;
for (const [name, id, inputProps, edge = { max: 0, px: 0 }] of cases) {
  const one = inOrder[name] ?? await frames(id, inputProps, path.join(outDir, `${name}-c1`), 1);
  const many = await frames(id, inputProps, path.join(outDir, `${name}-c${PARALLEL}`), PARALLEL);
  if (!one.length || one.length !== many.length) throw new Error(`${name}: ${one.length} frames in one tab, ${many.length} in ${PARALLEL}`);
  const all = one.map((f, i) => ({ frame: i, ...delta(f, many[i]) })).filter((d) => d.max > 0);
  const diffs = all.filter((d) => d.max > edge.max || d.px > edge.px || d.px < 0);
  if (all.length > diffs.length) console.log(`${name}: ${all.length - diffs.length} frame(s) within the edge allowance ` +
    `(${edge.px} px at ${edge.max}/255): ` + all.filter((d) => !diffs.includes(d)).map((d) => `${d.frame}:${d.max}/${d.px}px`).join(" "));
  results.parallel[name] = { frames: one.length, differ: diffs.length, max: Math.max(0, ...diffs.map((d) => d.max)), diffs,
    allowed: all.length - diffs.length };
  total += one.length;
  differ += diffs.length;
  console.log(`parallel ${name}: ${diffs.length}/${one.length} frames differ` + (diffs.length
    ? ` (max ${results.parallel[name].max}/255): ` + diffs.map((d) => `${d.frame}:${d.max}/${d.px}px`).join(" ") : ""));
}
results.parallel_total = { frames: total, differ, concurrency: PARALLEL, seconds: Math.round((Date.now() - t0) / 1000) };
console.log(`parallel: ${differ}/${total} frames differ at concurrency ${PARALLEL} (${results.parallel_total.seconds} s)`);
fs.writeFileSync(path.join(outDir, "results.json"), JSON.stringify(results, null, 2));
fs.rmSync(serveUrl, { recursive: true, force: true });
process.exit(bad + differ ? 1 : 0);
