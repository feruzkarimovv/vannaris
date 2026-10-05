/* Capture actual rendered synthetic-demo states as a short, silent MP4.
 * This is a still-frame walkthrough, not a timing or performance benchmark.
 * Requires the optional local ffmpeg executable and Playwright Chromium.
 */
import { createServer } from "node:http";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, writeFile, mkdir, mkdtemp, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, resolve, sep, extname } from "node:path";
import { tmpdir } from "node:os";
import { chromium } from "playwright";

const root = resolve(import.meta.dirname, "..");
const site = join(root, ".demo/site");
const output = join(root, ".artifacts/release");
const manifestBytes = await readFile(join(site, "demo.json"));
const manifest = JSON.parse(manifestBytes);
if (manifest.kind !== "synthetic_offline_demo" || manifest.synthetic !== true) throw new Error("Build the isolated synthetic demo first: make demo-build");
execFileSync("ffmpeg", ["-version"], { stdio: "ignore" });
await mkdir(output, { recursive: true });
const frames = await mkdtemp(join(tmpdir(), "vannaris-record-"));
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".woff2": "font/woff2" };
const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    const file = resolve(site, "." + pathname);
    if (!file.startsWith(site + sep)) throw new Error("Outside demo");
    response.setHeader("Content-Type", types[extname(file)] || "application/octet-stream");
    response.end(await readFile(file));
  } catch { response.writeHead(404).end("Not found"); }
});
await new Promise((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", resolve); });
const base = `http://127.0.0.1:${server.address().port}`;
const scenes = [];
let browser;
try {
  browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined), headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  async function capture(title) {
    await page.evaluate(() => document.fonts.ready);
    const file = `scene-${String(scenes.length).padStart(2, "0")}.png`;
    await page.screenshot({ path: join(frames, file) });
    scenes.push({ title, file, duration_seconds: 4 });
  }
  await page.goto(base + "/demo.html", { waitUntil: "networkidle" });
  await page.locator("#demo-evidence").waitFor({ state: "visible" });
  await capture("Clearly labelled offline synthetic demonstration");
  for (const stage of manifest.stages) {
    await page.locator(`#demo-controls button[data-stage="${stage.id}"]`).click();
    await page.evaluate(() => window.scrollTo(0, document.getElementById("demo-controls").getBoundingClientRect().top + scrollY - 120));
    await capture(stage.title);
  }
  await page.goto(base + "/results.html", { waitUntil: "networkidle" });
  await capture("Generated synthetic dashboard");
  await page.locator("#query-table .query-open").first().click();
  await page.locator("#query-dialog").waitFor({ state: "visible" });
  await capture("Inspectable individual judge evidence");
  if (errors.length) throw new Error("Rendered demo errors: " + errors.join(", "));
  await writeFile(join(frames, "scenes.txt"), scenes.map(scene => `file '${scene.file}'\nduration ${scene.duration_seconds}\n`).join("") + `file '${scenes.at(-1).file}'\n`);
  execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "1", "-i", join(frames, "scenes.txt"), "-t", String(scenes.length * 4), "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", join(output, "vannaris-demo.mp4")], { stdio: "inherit" });
  await writeFile(join(output, "capture.json"), JSON.stringify({ kind: "rendered_synthetic_still_frame_walkthrough", synthetic: true, source_run: manifest.run.id, demo_manifest_sha256: createHash("sha256").update(manifestBytes).digest("hex"), actual_api_spend_usd: 0, width: 1440, height: 1000, scenes }, null, 2) + "\n");
  await writeFile(join(output, "demo-evidence.json"), manifestBytes);
  await writeFile(join(output, "demo-cover.png"), await readFile(join(frames, "scene-00.png")));
  console.log(`Captured ${scenes.length * 4}-second walkthrough: ${join(output, "vannaris-demo.mp4")}`);
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
  await rm(frames, { recursive: true, force: true });
}
