// The Lottie card (StyleEdit.tsx LottieCard) on public/lottie/title-60fps.json: a 60 fps Lottie, as After Effects
// exports it, with a bar moving 15 px a Lottie frame and a text layer in Montserrat whose weight is only in fStyle
// ("ExtraBold"). Rendered at 30 fps, 1:1 (the card box is the Lottie's 1080x360).   node test/lottie.mjs <outDir>
// Proves: speed (the bar where 60 fps puts it at 30 fps frames, not at half speed), weight (ExtraBold carries far
// more ink than the same file set Regular), texts (the layer's words replaced), and the same frame rendered in two
// processes with the same md5. Look at <outDir>/sheet.png too: Montserrat, never a serif.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOP = 384; // the card's top edge, px (box y 20% of 1920)
const props = (src) => ({ width: 1080, height: 1920, dur: 3, light: true, card: { src, start: 0, end: 3, entrance: "cut",
  box: [0, 20, 100, 18.75], props: { texts: { title: "Lottie at 60" } } } });
const still = async (serveUrl, src, frame, output) => {
  const inputProps = props(src);
  const composition = await selectComposition({ serveUrl, id: "Preview", inputProps });
  await renderStill({ serveUrl, composition, inputProps, output, frame });
};
const [mode, ...args] = process.argv.slice(2);
if (mode === "child") {
  await still(args[0], "lottie/title-60fps.json", Number(args[1]), args[2]);
  process.exit(0);
}

const outDir = path.resolve(mode ?? "out/lottie");
fs.rmSync(outDir, { recursive: true, force: true });
fs.mkdirSync(outDir, { recursive: true });
const serveUrl = await bundle({ entryPoint: path.join(HERE, "..", "src", "index.ts"), publicDir: path.join(HERE, "public") });
// the same file with its font set Regular: the ink to measure ExtraBold against
const fixture = JSON.parse(fs.readFileSync(path.join(HERE, "public", "lottie", "title-60fps.json"), "utf8"));
fixture.fonts.list[0].fStyle = "Regular";
fs.writeFileSync(path.join(serveUrl, "public", "lottie", "title-regular.json"), JSON.stringify(fixture));
// and a family Google Fonts does not have: drawn in Inter (look.tsx FALLBACK), which sets narrower than Montserrat
fixture.fonts.list[0].fStyle = "ExtraBold";
fixture.fonts.list[0].fFamily = "No Such Sans";
fs.writeFileSync(path.join(serveUrl, "public", "lottie", "title-unknown.json"), JSON.stringify(fixture));

const raw = (f) => spawnSync("ffmpeg", ["-v", "error", "-i", f, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], { maxBuffer: 1 << 28 }).stdout;
const md5 = (b) => crypto.createHash("md5").update(b).digest("hex");
const W = 1080;
/** Mean x of the yellow bar's pixels (rows TOP+270..TOP+330), or null when it is not there. */
const barX = (px) => {
  let n = 0, sx = 0;
  for (let y = TOP + 270; y < TOP + 330; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 3;
    if (px[i] > 200 && px[i + 1] > 150 && px[i + 2] < 90) { n++; sx += x; }
  }
  return n ? sx / n : null;
};
/** Dark pixels in the text's rows, and the text's left and right edge. */
const ink = (px) => {
  let n = 0, l = W, r = 0;
  for (let y = TOP + 60; y < TOP + 240; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 3;
    if (px[i] + px[i + 1] + px[i + 2] < 300) { n++; l = Math.min(l, x); r = Math.max(r, x); }
  }
  return { n, l, r };
};

const fails = [];
const results = { bar: {}, ink: {} };
for (const frame of [2, 15, 30, 45]) {
  const f = path.join(outDir, `frame-${frame}.png`);
  await still(serveUrl, "lottie/title-60fps.json", frame, f);
  // Lottie frame = 2 x the 30 fps frame; the bar runs 90 -> 990 px over Lottie frames 0..60, then holds
  const want = Math.min(990, 90 + 15 * 2 * frame), got = barX(raw(f));
  results.bar[frame] = { want, got: got && Math.round(got * 10) / 10 };
  if (got === null || Math.abs(got - want) > 6) fails.push(`bar at frame ${frame}: ${got} px, want ${want} (half speed puts it at ${Math.min(990, 90 + 15 * frame)})`);
}
const bold = ink(raw(path.join(outDir, "frame-30.png")));
await still(serveUrl, "lottie/title-regular.json", 30, path.join(outDir, "regular-30.png"));
const regular = ink(raw(path.join(outDir, "regular-30.png")));
await still(serveUrl, "lottie/title-unknown.json", 30, path.join(outDir, "unknown-30.png"));
const unknown = ink(raw(path.join(outDir, "unknown-30.png")));
const wide = (k) => k.r - k.l;
results.ink = { extrabold: bold, regular, unknown_family: unknown, ratio: Math.round((bold.n / Math.max(1, regular.n)) * 100) / 100 };
if (!(bold.n > 1.5 * regular.n)) fails.push(`ExtraBold ink ${bold.n} is not well over Regular's ${regular.n}: the weight fell back to 400`);
// "Lottie at 60" in Montserrat ExtraBold at 110 px sets about 660 px wide, the same in Inter ExtraBold (the fallback)
// about 600; "{{TITLE}}" (texts not applied) or the browser's serif is narrower still
if (!(wide(bold) > 620)) fails.push(`text is ${wide(bold)} px wide, want over 620 (texts not applied, or not Montserrat)`);
if (!(unknown.n > 0.8 * bold.n && wide(unknown) < wide(bold) - 25)) {
  fails.push(`a family Google Fonts lacks should draw in Inter ExtraBold: ink ${unknown.n}, ${wide(unknown)} px wide`);
}

// the same frame in two separate processes: the same pixels, the same file
const twice = [];
for (const k of ["a", "b"]) {
  const f = path.join(outDir, `twice-${k}.png`);
  const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url), "child", serveUrl, "15", f], { stdio: "inherit" });
  if (r.status !== 0) throw new Error("child render failed");
  twice.push({ file: md5(fs.readFileSync(f)), pixels: md5(raw(f)) });
}
results.twice = twice;
if (twice[0].pixels !== twice[1].pixels) fails.push(`frame 15 differs between two renders: ${twice[0].pixels} vs ${twice[1].pixels}`);

spawnSync("ffmpeg", ["-v", "error", "-y", ...["frame-2", "frame-15", "frame-30", "regular-30", "unknown-30"].flatMap((n) => ["-i", path.join(outDir, `${n}.png`)]),
  "-filter_complex", "[0]crop=1080:400:0:364[a];[1]crop=1080:400:0:364[b];[2]crop=1080:400:0:364[c];[3]crop=1080:400:0:364[d];[4]crop=1080:400:0:364[e];[a][b][c][d][e]vstack=5[v]",
  "-map", "[v]", path.join(outDir, "sheet.png")]);
fs.writeFileSync(path.join(outDir, "results.json"), JSON.stringify(results, null, 2));
fs.rmSync(serveUrl, { recursive: true, force: true });
console.log(JSON.stringify(results));
if (fails.length) {
  console.error("LOTTIE FAIL:\n  " + fails.join("\n  "));
  process.exit(1);
}
console.log(`lottie ok (stills and sheet.png in ${outDir})`);
