/* Real rendered regression checks complement the fast structural/jsdom gates.
 * Serve only the supplied site root, use no API credentials, and fail on
 * accessibility violations, broken interaction, overflow, or JS exceptions.
 */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { chromium } from "playwright";

const require = createRequire(import.meta.url);
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const site = resolve(process.argv[2] || join(root, "site"));
const demo = process.argv.includes("--demo");
const artifacts = join(root, ".artifacts", "browser", demo ? "demo" : "archive");
await mkdir(artifacts, { recursive: true });
const python = process.env.VANNARIS_PYTHON || (existsSync(join(root, ".venv/bin/python")) ? join(root, ".venv/bin/python") : "python3");
const config = JSON.parse(await readFile(join(root, "vercel.json"), "utf8"));
const securityHeaders = Object.fromEntries(config.headers.find(block => block.source === "/(.*)").headers.map(header => [header.key, header.value]));
if (demo) securityHeaders["Content-Security-Policy"] = execFileSync(python, [join(root, "scripts/update_site_headers.py"), "--site", site, "--print-csp"], { encoding: "utf8" }).trim();
else execFileSync(python, [join(root, "scripts/update_site_headers.py"), "--check"], { stdio: "pipe" });
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".csv": "text/csv", ".png": "image/png" };
const server = createServer(async (request, response) => {
  try {
    const path = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    const file = resolve(site, "." + (path === "/" ? "/index.html" : path));
    if (file !== site && !file.startsWith(site + sep)) throw new Error("Outside site root");
    response.setHeader("Content-Type", types[extname(file)] || "application/octet-stream");
    for (const [name, value] of Object.entries(securityHeaders)) response.setHeader(name, value);
    response.end(await readFile(file));
  } catch {
    response.writeHead(404).end("Not found");
  }
});
await new Promise((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", resolve); });
const base = `http://127.0.0.1:${server.address().port}`;
const executable = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined);
let browser;
const failures = [];
let checks = 0;

async function run(name, fn) {
  try { await fn(); checks++; console.log(`PASS ${name}`); }
  catch (error) { failures.push(`${name}: ${error.message}`); console.error(`FAIL ${name}: ${error.message}`); }
}

async function rendered(page, path) {
  const errors = [];
  const onError = error => errors.push(error.message);
  page.on("pageerror", onError);
  await page.addInitScript(() => {
    window.__vannarisPolicyViolations = [];
    document.addEventListener("securitypolicyviolation", event => window.__vannarisPolicyViolations.push(event.violatedDirective));
  });
  try {
    const response = await page.goto(base + path, { waitUntil: "networkidle" });
    assert.equal(response.status(), 200);
    await page.evaluate(() => document.fonts.ready);
    assert.deepEqual(errors, [], "Page raised a JavaScript exception");
    assert.deepEqual(await page.evaluate(() => window.__vannarisPolicyViolations), [], "App violates its security policy");
  } finally { page.off("pageerror", onError); }
}

async function audit(page, name) {
  await page.evaluate(await readFile(require.resolve("axe-core/axe.min.js"), "utf8"));
  const result = await page.evaluate(async () => await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] } }));
  await writeFile(join(artifacts, `axe-${name}.json`), JSON.stringify(result.violations, null, 2));
  assert.deepEqual(result.violations.map(v => ({ id: v.id, nodes: v.nodes.slice(0, 4).map(n => n.target) })), [], "Rendered WCAG violations");
}

// CSV-derived expectations deliberately avoid SB_DETAIL and the chart code:
// a correct run label alone cannot prove that a histogram changed its data.
function expectedDetailEvidence(week) {
  const script = `
import csv, json, pathlib, sys
site, week = pathlib.Path(sys.argv[1]), sys.argv[2]
distribution, complete_keys = {}, set()
for row in csv.DictReader((site / "export" / f"responses-{week}.csv").open()):
    if row["held_out"] != "0" or row["complete_ensemble"] != "1": continue
    score = float(row["median_overall"])
    bins = distribution.setdefault(row["vendor"], [0, 0, 0, 0, 0])
    band = 0 if score < 6 else 1 if score < 7 else 2 if score < 8 else 3 if score < 9 else 4
    bins[band] += 1
    complete_keys.add((row["query_id"], row["vendor"]))
panels = {}
for row in csv.DictReader((site / "export" / f"judge-scores-{week}.csv").open()):
    if row["held_out"] != "0": continue
    key = row["query_id"], row["vendor"]
    if key not in complete_keys: continue
    panel = panels.setdefault(key, {})
    assert row["judge_family"] not in panel, "duplicate judge family in public export"
    panel[row["judge_family"]] = float(row["overall"])
disagreement = [0, 0, 0, 0, 0]
for panel in panels.values():
    assert set(panel) == {"anthropic", "openai", "google"}, "complete response missing a judge family"
    spread = max(panel.values()) - min(panel.values())
    disagreement[min(int(spread), 4)] += 1
print(json.dumps({"distribution": distribution, "disagreement": disagreement}))
`;
  return JSON.parse(execFileSync(python, ["-c", script, site, week], { encoding: "utf8" }));
}

const bundleScript = await readFile(join(site, "data/bundle.js"), "utf8");
const published = JSON.parse(bundleScript.slice(bundleScript.indexOf("{"), bundleScript.lastIndexOf("}") + 1));
let archiveEvidence;
if (!demo) {
  const latestWeek = published.latest.week;
  const latest = expectedDetailEvidence(latestWeek);
  const archived = published.weeks.filter(week => week !== latestWeek).map(week => ({
    week, expected: expectedDetailEvidence(week),
  }));
  archiveEvidence = { latestWeek, latest, archived };
}

async function renderedDetailCounts(page, week) {
  await page.waitForFunction(selected => ["fig-distribution", "fig-disagreement"].every(id => {
    const element = document.getElementById(id)?.closest(".panel");
    return element?.getAttribute("data-detail-run") === selected && element?.getAttribute("data-detail-state") === "ready";
  }), week, { timeout: 10000 });
  const labels = await page.evaluate(() => Object.fromEntries(window.SB_DATA.latest.vendors.map(vendor => [vendor.label, vendor.vendor])));
  const distributionRows = await page.locator("#fig-distribution table tbody tr").evaluateAll(rows => rows.map(row => [...row.cells].map(cell => cell.textContent.trim())));
  const distribution = Object.fromEntries(distributionRows.map(row => [labels[row[0]], row.slice(1, 6).map(value => parseInt(value, 10))]));
  assert.ok(Object.keys(distribution).every(vendor => vendor && vendor !== "undefined"), "A chart vendor label is not part of the selected snapshot");
  const disagreement = await page.locator("#fig-disagreement table tbody tr").evaluateAll(rows => rows.map(row => Number(row.cells[1].textContent.replace(/[^\d]/g, ""))));
  return { distribution, disagreement };
}

async function assertSelectedDetailEvidence(page, week, expected) {
  const actual = await renderedDetailCounts(page, week);
  assert.deepEqual(actual, expected, "Charts disagree with the selected run's public CSVs");
  const distributionMarks = await page.locator("#fig-distribution svg .hit").evaluateAll(nodes => nodes.map(node => node.getAttribute("aria-label")).sort());
  const labels = await page.evaluate(() => Object.fromEntries(window.SB_DATA.latest.vendors.map(vendor => [vendor.vendor, vendor.label])));
  const bands = ["under 6", "6–7", "7–8", "8–9", "9–10"];
  const expectedMarks = Object.entries(expected.distribution).flatMap(([vendor, counts]) => counts.flatMap((count, index) => count ? [`${labels[vendor]}, ${bands[index]}: ${count} queries`] : [])).sort();
  assert.deepEqual(distributionMarks, expectedMarks, "SVG marks borrowed another run's distribution");
  const disagreementMarks = await page.locator("#fig-disagreement svg .hit").evaluateAll(nodes => nodes.map(node => Number(node.getAttribute("aria-label").match(/: ([\d,]+) responses$/)?.[1].replaceAll(",", ""))));
  assert.deepEqual(disagreementMarks, expected.disagreement, "SVG marks borrowed another run's judge disagreement");
  const compared = await page.evaluate(() => window.SB_DATA.latest.judging.n_compared);
  assert.equal(actual.disagreement.reduce((sum, count) => sum + count, 0), compared, "Histogram and published disagreement use different ensembles");
  return actual;
}

try {
  browser = await chromium.launch({ executablePath: executable, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
  const vendorPage = demo ? "vendors/fixture_alpha.html" : "vendors/exa.html";
  for (const path of ["index.html", "results.html", "methodology.html", "data.html", "demo.html", vendorPage]) {
    await run(`${path}: rendered accessibility`, async () => { await rendered(page, "/" + path); await audit(page, path.replaceAll("/", "-")); });
  }
  await run("security policy blocks an unapproved inline script", async () => {
    await rendered(page, "/index.html");
    await page.evaluate(() => {
      const script = document.createElement("script");
      script.textContent = "window.__vannarisUnexpectedScriptExecuted = true;";
      document.head.appendChild(script);
    });
    await page.waitForFunction(() => window.__vannarisPolicyViolations.length > 0);
    assert.equal(await page.evaluate(() => window.__vannarisUnexpectedScriptExecuted), undefined);
  });
  if (!demo) await run("incomplete vendor remains unranked after animation", async () => {
    await rendered(page, "/vendors/perplexity.html?run=2026-W35");
    await page.waitForTimeout(1100);
    assert.equal((await page.locator('[data-val="d.v.score"]').first().innerText()).trim(), "n/a");
    const animated = await browser.newPage({ reducedMotion: "no-preference" });
    await rendered(animated, "/vendors/perplexity.html?run=2026-W35");
    await animated.waitForTimeout(1100);
    assert.equal((await animated.locator('[data-val="d.v.score"]').first().innerText()).trim(), "n/a");
    await animated.close();
  });
  await run("archive selection and shareable URL", async () => {
    await rendered(page, "/results.html");
    const selector = page.locator("#run-select");
    const current = await selector.inputValue();
    const values = await selector.locator("option").evaluateAll(nodes => nodes.filter(n => !n.disabled).map(n => n.value));
    assert.ok(values.length >= 1);
    const chosen = values.find(value => value !== current) || current;
    await selector.selectOption(chosen);
    await page.waitForURL(url => url.searchParams.get("run") === chosen);
    await page.waitForLoadState("networkidle");
    assert.equal(await page.locator("#run-select").inputValue(), chosen);
    assert.equal(await page.locator("main").getAttribute("data-selected-run"), chosen, "Selected evidence belongs to a different run");
    const label = await selector.locator(`option[value="${chosen}"]`).innerText();
    assert.match(label, /\d/, "Archive option has no human-readable date");
    await page.waitForFunction(week => window.SB_DETAIL?.week === week, chosen);
    assert.equal(await page.evaluate(() => window.SB_DETAIL.week), chosen, "Explorer borrowed another run's details");
  });
  if (!demo) await run("archived histograms and SVG marks match their public CSVs", async () => {
    const chosen = archiveEvidence.archived.find(entry =>
      JSON.stringify(entry.expected.distribution) !== JSON.stringify(archiveEvidence.latest.distribution)
      && JSON.stringify(entry.expected.disagreement) !== JSON.stringify(archiveEvidence.latest.disagreement));
    assert.ok(chosen, "The regression needs a real archive with different distributions and disagreement");
    await rendered(page, `/results.html?run=${archiveEvidence.latestWeek}`);
    const latest = await assertSelectedDetailEvidence(page, archiveEvidence.latestWeek, archiveEvidence.latest);
    await page.locator("#run-select").selectOption(chosen.week);
    await page.waitForURL(url => url.searchParams.get("run") === chosen.week);
    await page.waitForLoadState("networkidle");
    const archived = await assertSelectedDetailEvidence(page, chosen.week, chosen.expected);
    assert.notDeepEqual(archived.distribution, latest.distribution, "Archive histogram still displays the latest distribution");
    assert.notDeepEqual(archived.disagreement, latest.disagreement, "Archive histogram still displays the latest judge disagreement");
    assert.equal(await page.locator("main").getAttribute("data-selected-run"), chosen.week);
    const sourceMean = await page.evaluate(() => window.SB_DATA.latest.judging.mean_disagreement);
    const displayedMean = Number((await page.locator('[data-val="latest.judging.mean_disagreement"]').first().innerText()).replace(/[^\d.\-]/g, ""));
    assert.equal(displayedMean, Number(sourceMean.toFixed(2)), "Disagreement headline belongs to another snapshot");
  });
  if (!demo) await run("delayed archive detail never flashes latest histograms", async () => {
    const chosen = archiveEvidence.archived[0];
    assert.ok(chosen, "No archive is available for the detail loading regression");
    const delayed = await browser.newPage({ reducedMotion: "reduce" });
    let release;
    const hold = new Promise(resolve => { release = resolve; });
    await delayed.route(`**/data/detail-${chosen.week}.js`, async route => { await hold; await route.continue(); });
    try {
      const response = await delayed.goto(`${base}/results.html?run=${chosen.week}`, { waitUntil: "domcontentloaded" });
      assert.equal(response.status(), 200);
      for (const id of ["fig-distribution", "fig-disagreement"]) {
        const panel = delayed.locator(`#${id}`).locator("..");
        assert.equal(await panel.getAttribute("data-detail-run"), chosen.week);
        assert.equal(await panel.getAttribute("data-detail-state"), "loading");
        assert.equal(await delayed.locator(`#${id} svg, #${id} table`).count(), 0, "Loading archive detail borrowed a latest-run chart");
      }
      release();
      await delayed.waitForLoadState("networkidle");
      await assertSelectedDetailEvidence(delayed, chosen.week, chosen.expected);
    } finally { release(); await delayed.close(); }
  });
  if (!demo) await run("blocked archive detail shows unavailable histograms without substituting latest", async () => {
    const chosen = archiveEvidence.archived[0];
    assert.ok(chosen, "No archive is available for the unavailable-detail regression");
    const blocked = await browser.newPage({ reducedMotion: "reduce" });
    await blocked.route(`**/data/detail-${chosen.week}.js`, route => route.abort());
    try {
      await rendered(blocked, `/results.html?run=${chosen.week}`);
      assert.equal(await blocked.locator("#run-select").inputValue(), chosen.week);
      assert.equal(await blocked.locator("main").getAttribute("data-selected-run"), chosen.week);
      for (const id of ["fig-distribution", "fig-disagreement"]) {
        const panel = blocked.locator(`#${id}`).locator("..");
        assert.equal(await panel.getAttribute("data-detail-run"), chosen.week);
        assert.equal(await panel.getAttribute("data-detail-state"), "unavailable");
        assert.match(await blocked.locator(`#${id}`).innerText(), /unavailable|could not load/i);
        assert.equal(await blocked.locator(`#${id} svg, #${id} table`).count(), 0, "An unavailable archive retains latest-run evidence");
        assert.ok(await panel.getByRole("button", { name: /retry/i }).count()
          || await panel.getByRole("link", { name: /retry/i }).count());
        const link = panel.getByRole("link", { name: /download|snapshot/i }).first();
        assert.ok((await link.getAttribute("href")).includes(chosen.week), "Recovery link borrows a latest-run download");
      }
      assert.match(await blocked.locator("#q-count").innerText(), /unavailable/i);
      assert.equal(await blocked.locator("#query-table .query-open").count(), 0);
      assert.equal(await blocked.locator("#q-search").isDisabled(), true);
    } finally { await blocked.close(); }
  });
  await run("query filters, empty result and pagination", async () => {
    await rendered(page, "/results.html");
    await page.locator("#q-search").fill("NO_MATCH_EXPECTED_7cd199");
    await page.locator("#query-empty").waitFor({ state: "visible" });
    assert.match(await page.locator("#query-empty").innerText(), /No query matches/i);
    assert.equal(await page.locator("#query-table .query-open").count(), 0);
    assert.ok(new URL(page.url()).searchParams.get("q"));
    await page.locator("#q-search").fill("");
    await page.waitForFunction(() => document.querySelectorAll("#query-table .query-open").length > 0);
    assert.ok(await page.locator("#query-table .query-open").count() <= 25, "Unbounded initial query page");
    if (await page.locator("#q-next").isEnabled()) {
      const first = await page.locator("#query-table .query-open").first().getAttribute("data-query-id");
      await page.locator("#q-next").click();
      assert.notEqual(await page.locator("#query-table .query-open").first().getAttribute("data-query-id"), first);
      await page.locator("#q-prev").click();
    }
  });
  await run("query evidence dialog: keyboard open, Escape and focus return", async () => {
    const opener = page.locator("#query-table .query-open").first();
    await opener.focus();
    await page.keyboard.press("Enter");
    await page.locator("#query-dialog").waitFor({ state: "visible" });
    assert.ok((await page.locator("#query-dialog").innerText()).length > 40);
    await page.keyboard.press("Escape");
    await page.locator("#query-dialog").waitFor({ state: "hidden" });
    assert.equal(await opener.evaluate(element => element === document.activeElement), true, "Focus was not restored");
  });
  await run("missing bundle has a usable recovery state", async () => {
    const failure = await browser.newPage({ reducedMotion: "reduce" });
    await failure.route("**/data/bundle.js", route => route.abort());
    await rendered(failure, "/results.html");
    await failure.getByRole("heading", { name: "Evidence could not load" }).waitFor();
    assert.ok(await failure.getByRole("button", { name: /retry/i }).count() || await failure.getByRole("link", { name: /retry/i }).count());
    await failure.close();
  });
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: "reduce" });
  for (const path of ["index.html", "results.html", "data.html", "demo.html"]) {
    await run(`${path}: mobile width and accessibility`, async () => {
      await rendered(mobile, "/" + path);
      assert.ok(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "Page has horizontal overflow");
      await audit(mobile, "mobile-" + path);
      await mobile.screenshot({ path: join(artifacts, "mobile-" + path + ".png"), fullPage: true });
    });
  }
  await run("mobile query details are usable on touch", async () => {
    await rendered(mobile, "/results.html");
    await mobile.locator("#query-table .query-open").first().tap();
    await mobile.locator("#query-dialog").waitFor({ state: "visible" });
    assert.ok(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await mobile.locator("#query-dialog-close").tap();
    await mobile.locator("#query-dialog").waitFor({ state: "hidden" });
  });
  if (demo) await run("offline demonstration is explicitly synthetic and complete", async () => {
    await rendered(page, "/demo.html");
    const response = await page.request.get(base + "/demo.json");
    assert.ok(response.ok());
    const data = await response.json();
    assert.equal(data.kind, "synthetic_offline_demo");
    assert.ok(data.stages.length >= 4);
    assert.match(await page.locator("main").innerText(), /synthetic/i);
    assert.match(await page.locator("main").innerText(), /recover/i);
  });
  await rendered(page, demo ? "/demo.html" : "/index.html");
  await page.screenshot({ path: join(artifacts, "desktop.png"), fullPage: true });
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
if (failures.length) {
  console.error(`\n${failures.length} browser check(s) failed; ${checks} passed. Diagnostics: ${artifacts}`);
  process.exitCode = 1;
} else console.log(`\n${checks} rendered browser checks passed. Screenshots: ${artifacts}`);
