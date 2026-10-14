// Renders every case in a cases file as stills (4 points) and a short mp4, plus a 1 fps strip per clip.
//   node test/templates.mjs <publicDir> <cases.json | a folder of them> <outDir> [only-name-substring] [--no-video]
// A folder (test/kinetic: one file per kinetic format) runs every *.json in it. test/public (the Lottie fixture) is
// served beside <publicDir>.
// Kinetic cases are first checked as numbers (kinetic/probe.ts, the KineticProbe composition): nothing past the frame,
// nothing drawn on anything else, labels 40 px apart on a row, connectors at their length, a step label inside its well,
// a stamp over at most the foot of its figure, a chain centred on its ink, a count never past its final value (and final on its landing frame),
// tally tiles never before their figure. A case with "expect_error" must throw that message; "probe_only" skips the
// render. Exits 1 on any problem, after rendering the rest.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const [publicDir, casesPath, outDir, only, flag] = process.argv.slice(2);
const files = fs.statSync(casesPath).isDirectory()
  ? fs.readdirSync(casesPath).filter((f) => f.endsWith(".json")).sort().map((f) => path.join(casesPath, f)) : [casesPath];
const cases = files.flatMap((f) => JSON.parse(fs.readFileSync(f, "utf8"))).filter((c) => !only || only === "-" || c.name.includes(only));
fs.mkdirSync(outDir, { recursive: true });
const serveUrl = await bundle({ entryPoint: path.join(HERE, "..", "src", "index.ts"), publicDir: path.resolve(publicDir) });
fs.cpSync(path.join(HERE, "public"), path.join(serveUrl, "public"), { recursive: true });

/** What is wrong with one kinetic case's probe (kinetic/probe.ts), as lines. */
const checkProbe = (res, c) => {
  if (c.expect_error) return res.error?.includes(c.expect_error) ? [] : [`expected it to throw "${c.expect_error}", got ${res.error ? `"${res.error}"` : "a layout"}`];
  if (res.error) return [`threw: ${res.error}`];
  const W = c.width ?? 1080, H = c.height ?? 1920, k = res.k, bad = [];
  const at = (p) => `${p.kind} [${p.r.map((v) => Math.round(v)).join(", ")}]`;
  const ix = (a, b) => [Math.min(a.r[2], b.r[2]) - Math.max(a.r[0], b.r[0]), Math.min(a.r[3], b.r[3]) - Math.max(a.r[1], b.r[1])];
  for (const p of res.parts) {
    if (p.r[0] < 16 * k - 0.5 || p.r[2] > W - 16 * k + 0.5 || p.r[1] < 0.08 * H - 0.5 || p.r[3] > H) bad.push(`${at(p)} is past the frame (or its 16 px gutter, or the header)`);
    if (p.in && (p.r[0] < p.in[0] - 0.5 || p.r[2] > p.in[2] + 0.5 || p.r[1] < p.in[1] - 0.5 || p.r[3] > p.in[3] + 0.5)) bad.push(`${at(p)} is past its well`);
    if (p.min !== undefined && p.r[2] - p.r[0] < p.min - 0.5) bad.push(`${at(p)} is ${Math.round(p.r[2] - p.r[0])} px long, under its ${Math.round(p.min)}`);
  }
  res.parts.forEach((a, i) => res.parts.slice(i + 1).forEach((b) => {
    if ((a.in && a.in.join() === b.r.join()) || (b.in && b.in.join() === a.r.join())) return;   // a label inside its own well
    const [ow, oh] = ix(a, b);
    const st = a.kind === "stamp" ? a : b.kind === "stamp" ? b : null, fg = st && (st === a ? b : a);
    if (st && fg.kind === "figure") {
      if (ow > 0.5 && st.r[1] < fg.r[3] - 0.25 * (fg.r[3] - fg.r[1])) bad.push(`${at(st)} covers more than the foot of ${at(fg)}`);
    } else if (ow > 0.5 && oh > 0.5) bad.push(`${at(a)} overlaps ${at(b)}`);
    if (a.kind === "label" && b.kind === "label" && oh > 0.5 && -ow < 40 * k - 0.5) bad.push(`${at(a)} and ${at(b)} are ${Math.round(-ow)} px apart, under 40`);
  }));
  for (const n of res.counts ?? []) {
    const over = n.shown.findIndex((v) => v > n.final), back = n.shown.findIndex((v, i) => i && v < n.shown[i - 1]);
    if (over >= 0) bad.push(`its count shows ${n.shown[over]} on frame ${over} of the pull, past its final ${n.final}`);
    if (back >= 0) bad.push(`its count goes back from ${n.shown[back - 1]} to ${n.shown[back]} on frame ${back}`);
    if (n.shown[n.land] !== n.final) bad.push(`its count shows ${n.shown[n.land]} on its landing frame, not ${n.final}`);
    if (n.final > 0 && n.shown[0] < Math.floor(0.4 * n.final) - 1) bad.push(`its count starts at ${n.shown[0]}, under 40% of ${n.final}`);
  }
  if (c.card.anim.type === "number_chain") {   // a chain is centred on what it draws, a long outer label included
    const l = Math.min(...res.parts.map((p) => p.r[0])), r = Math.max(...res.parts.map((p) => p.r[2]));
    if (Math.abs((l + r) / 2 - W / 2) > 0.02 * W) bad.push(`its ink (${Math.round(l)}-${Math.round(r)} px) sits ${Math.round((l + r) / 2 - W / 2)} px off centre`);
  }
  if (res.fills && res.fills.first < res.fills.marker - 1e-6) bad.push(`a tile fills at ${res.fills.first.toFixed(2)} s, before its figure has landed (${res.fills.marker.toFixed(2)} s)`);
  return bad;
};

const problems = [];
const anim = cases.filter((c) => c.card?.anim?.type);
if (anim.length) {
  const probeCases = anim.map((c) => ({ name: c.name, type: c.card.anim.type, props: c.card.anim.props ?? {}, width: c.width ?? 1080,
    height: c.height ?? 1920, dur: c.dur ?? 4 }));
  const { props } = await selectComposition({ serveUrl, id: "KineticProbe", inputProps: { cases: probeCases } });
  for (const res of props.results) {
    if (res.error?.startsWith("no probe for")) continue;   // not a kinetic card
    const c = anim.find((x) => x.name === res.name), bad = checkProbe(res, c);
    problems.push(...bad.map((b) => `${res.name}: ${b}`));
    console.log(bad.length ? "PROBLEM" : "probe ok", res.name, bad.length ? `\n  ${bad.join("\n  ")}` : JSON.stringify(res.sizes ?? {}));
  }
}
for (const c of cases.filter((x) => !x.expect_error && !x.probe_only)) {
  const { expect_error, probe_only, ...cc } = c;
  const inputProps = { width: 1080, height: 1920, dur: 4, ...cc, card: { start: 0, end: c.dur ?? 4, entrance: "pop", ...c.card } };
  const composition = await selectComposition({ serveUrl, id: "Preview", inputProps });
  const n = composition.durationInFrames;
  for (const [i, f] of [0.12, 0.3, 0.55, 0.85].entries()) {
    await renderStill({ serveUrl, composition, inputProps, output: path.join(outDir, "stills", `${c.name}-${i}.png`), frame: Math.floor(n * f) });
  }
  if (flag !== "--no-video") {
    const mp4 = path.join(outDir, `${c.name}.mp4`);
    await renderMedia({ serveUrl, composition, inputProps, codec: "h264", outputLocation: mp4, crf: 18 });
    spawnSync("ffmpeg", ["-v", "error", "-y", "-i", mp4, "-vf", `fps=4,scale=${c.width > c.height ? 480 : 270}:-1,tile=8x${Math.ceil((n / 30) * 4 / 8)}`,
      "-frames:v", "1", path.join(outDir, "strips", `${c.name}.png`)]);
  }
  console.log("done", c.name);
}
fs.rmSync(serveUrl, { recursive: true, force: true });
if (problems.length) {
  console.log(`${problems.length} kinetic layout problem(s):\n  ${problems.join("\n  ")}`);
  process.exit(1);
}
