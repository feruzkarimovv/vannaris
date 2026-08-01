/* Structural regression gate for the published site.
 *
 * check-site.mjs answers "did every generated figure resolve?" and
 * check-quality.mjs answers "is the page accessible and self-contained?".
 * Neither notices if a page quietly loses a section, a chart, a table column or
 * a data-bound slot — the page would still resolve every remaining figure and
 * still pass axe, and the gate would report ok on a page that had lost a third
 * of itself. On a box with no browser and no root, "I looked at it and it
 * seemed fine" was the only thing standing in that gap. This closes it.
 *
 * It is not pixel diffing and cannot become it. What it snapshots is the shape
 * of the document: landmarks, heading outline, sections, chart mounts, table
 * headers, form controls, the names of every data-bound slot, and the internal
 * link graph. Values are deliberately excluded — the numbers change with every
 * export, and a snapshot that churned weekly would be updated without being
 * read, which is worse than no snapshot at all.
 *
 * Run:  node scripts/check-structure.mjs [site-root]
 *       node scripts/check-structure.mjs --update    (after an intended change)
 *
 * --update rewrites the committed snapshot. That is not a way to make a failure
 * go away: the rewritten snapshot lands in the diff, where the structural change
 * is reviewed alongside the markup change that caused it. A snapshot updated in
 * a commit that does not explain why is the tell.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2).filter((a) => !a.startsWith("--"));
const SITE = args[0] ? resolve(args[0]) : join(ROOT, "site");
const SNAPSHOT = join(ROOT, "tests", "snapshots", "site-structure.json");
const PAGES = ["index.html", "results.html", "methodology.html", "data.html"];

const UPDATE = process.argv.includes("--update");
const STRICT = process.env.CHECK_STRICT === "1" || process.argv.includes("--strict");

let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch {
  if (STRICT) {
    console.error("jsdom is not installed and CHECK_STRICT is set — refusing to report a pass");
    console.error("  npm install");
    process.exit(2);
  }
  console.log("jsdom not installed — skipping structure checks (npm install to enable)");
  process.exit(0);
}

// ------------------------------------------------------------- serialisation

const norm = (s) => s.replace(/\s+/g, " ").trim();

/* Text content with data-bound slots rendered as `{name}` rather than descended
 * into. Two things fall out of that: the snapshot records *where* a generated
 * figure belongs without recording what it currently says, and a heading like
 * "Results, {latest.week}" stays stable across every weekly export while still
 * failing loudly if the binding is removed or renamed. */
function slotText(el) {
  let out = "";
  for (const node of el.childNodes) {
    if (node.nodeType === 3) { out += node.textContent; continue; }
    if (node.nodeType !== 1) continue;
    const v = node.getAttribute("data-val");
    out += v ? `{${v}}` : slotText(node);
  }
  return norm(out);
}

function label(el) {
  const own = el.getAttribute("data-val");
  if (own) return `{${own}}`;
  return slotText(el);
}

/* The accessible name, by the two mechanisms this site actually uses. Landmarks
 * are only distinguishable to a screen reader by their name, so a nav that
 * loses its aria-label is a real regression that looks like nothing. */
function accName(el, doc) {
  const direct = el.getAttribute("aria-label");
  if (direct) return norm(direct);
  const by = el.getAttribute("aria-labelledby");
  if (by) {
    const target = doc.getElementById(by);
    if (target) return slotText(target);
  }
  return "";
}

function describe(el, doc) {
  const tag = el.tagName.toLowerCase();
  const id = el.id ? `#${el.id}` : "";
  const role = el.getAttribute("role");
  const name = accName(el, doc);
  return tag + id + (role ? `[role=${role}]` : "") + (name ? ` "${name}"` : "");
}

function capture(doc) {
  const all = (sel) => [...doc.querySelectorAll(sel)];

  // Landmarks, in document order. `section` is included only when it carries an
  // id or a name, because a bare <section> is a styling wrapper rather than a
  // structure a reader can navigate to.
  const landmarks = all("header, nav, main, footer, aside, form, section, [role]")
    .filter((el) => {
      const tag = el.tagName.toLowerCase();
      if (tag !== "section") return true;
      return Boolean(el.id || el.getAttribute("aria-label") || el.getAttribute("aria-labelledby"));
    })
    .map((el) => describe(el, doc));

  const outline = all("h1, h2, h3, h4, h5, h6")
    .map((h) => `${h.tagName.toLowerCase()} ${label(h)}`);

  const figures = all('[id^="fig-"]').map((el) => `#${el.id}`);

  const tables = all("table").map((t) => {
    const id = t.id ? `#${t.id}` : "table";
    const caption = t.querySelector("caption");
    const heads = [...t.querySelectorAll("thead th, tr:first-child th")]
      .map((th) => label(th) || th.getAttribute("aria-label") || "?");
    return `${id}${caption ? ` "${slotText(caption)}"` : ""} [${[...new Set(heads)].join(" | ")}]`;
  });

  const controls = all("button, select, input, textarea, details > summary").map((el) => {
    const tag = el.tagName.toLowerCase();
    const id = el.id ? `#${el.id}` : "";
    const type = el.getAttribute("type") ? `[type=${el.getAttribute("type")}]` : "";
    // Attribute hooks are how the page's own JavaScript finds its controls, so
    // losing one is a broken feature that renders perfectly.
    const hooks = [...el.attributes].map((a) => a.name)
      .filter((n) => n.startsWith("data-") && n !== "data-val" && n !== "data-fmt")
      .sort().map((n) => `[${n}]`).join("");
    const name = accName(el, doc) || el.getAttribute("placeholder") || label(el);
    return `${tag}${id}${type}${hooks}${name ? ` "${name}"` : ""}`;
  });

  // Every data-bound slot the page expects the export to fill, with its
  // formatter and how many times it appears. check-site.mjs proves the ones
  // present resolve; this proves the set of them has not silently shrunk —
  // deleting a sentence with a figure in it passes every other gate.
  const slots = new Map();
  for (const el of all("[data-val]")) {
    const key = el.getAttribute("data-val") +
      (el.getAttribute("data-fmt") ? `|${el.getAttribute("data-fmt")}` : "");
    slots.set(key, (slots.get(key) || 0) + 1);
  }

  const links = [...new Set(all("a[href]")
    .map((a) => a.getAttribute("href"))
    .filter((h) => h && !/^(https?:|mailto:|tel:|data:)/i.test(h)))].sort();

  return {
    title: norm(doc.querySelector("title")?.textContent || ""),
    landmarks,
    outline,
    figures,
    tables,
    controls,
    slots: [...slots.entries()].sort(([a], [b]) => a.localeCompare(b))
      .map(([k, n]) => (n > 1 ? `${k} ×${n}` : k)),
    links,
  };
}

// ------------------------------------------------------------------- compare

const captured = {};
let missing = 0;
for (const page of PAGES) {
  const file = join(SITE, page);
  if (!existsSync(file)) {
    console.error(`  FAIL  ${page}: missing`);
    missing++;
    continue;
  }
  // Scripts are deliberately not run. This gate is about the structure the
  // markup asserts, which is the thing a person edits; the post-JavaScript DOM
  // is check-site.mjs's job and carries values that change every week.
  const dom = new JSDOM(readFileSync(file, "utf8"), { url: "http://localhost/" + page });
  captured[page] = capture(dom.window.document);
  dom.window.close();
}

if (UPDATE) {
  mkdirSync(dirname(SNAPSHOT), { recursive: true });
  writeFileSync(SNAPSHOT, JSON.stringify(captured, null, 2) + "\n");
  console.log(`  snapshot rewritten: ${SNAPSHOT.replace(ROOT + "/", "")}`);
  console.log("  review it in the diff — an unexplained update is the failure this gate exists to catch");
  process.exit(missing ? 1 : 0);
}

if (!existsSync(SNAPSHOT)) {
  console.error(`no snapshot at ${SNAPSHOT.replace(ROOT + "/", "")}`);
  console.error("  node scripts/check-structure.mjs --update   to record the current structure");
  process.exit(1);
}

const expected = JSON.parse(readFileSync(SNAPSHOT, "utf8"));
const drift = [];

/* Ordered lists are compared as sets *and* as sequences: a reordered heading
 * outline is a different document even when nothing was added or removed. */
function compare(page, key, want, got) {
  const w = Array.isArray(want) ? want : [want];
  const g = Array.isArray(got) ? got : [got];
  const removed = w.filter((x) => !g.includes(x));
  const added = g.filter((x) => !w.includes(x));
  if (!removed.length && !added.length) {
    if (Array.isArray(want) && w.join(" ") !== g.join(" ")) {
      drift.push({ page, key, reordered: true, removed: [], added: [] });
    }
    return;
  }
  drift.push({ page, key, removed, added });
}

for (const page of PAGES) {
  if (!captured[page]) continue;
  if (!expected[page]) {
    drift.push({ page, key: "page", removed: [], added: ["not in the snapshot"] });
    continue;
  }
  for (const key of Object.keys(expected[page])) {
    compare(page, key, expected[page][key], captured[page][key] ?? []);
  }
}
for (const page of Object.keys(expected)) {
  if (!captured[page] && !PAGES.includes(page)) {
    drift.push({ page, key: "page", removed: ["in the snapshot but no longer checked"], added: [] });
  }
}

for (const page of PAGES) {
  if (captured[page]) {
    const c = captured[page];
    console.log(`  ${drift.some((d) => d.page === page) ? "drift" : "ok   "} ${page.padEnd(18)}` +
      `${c.landmarks.length} landmarks · ${c.outline.length} headings · ` +
      `${c.figures.length} figures · ${c.slots.length} slots`);
  }
}

if (missing || drift.length) {
  console.error("\nstructure drifted from tests/snapshots/site-structure.json:\n");
  let last = "";
  for (const d of drift) {
    if (d.page !== last) { console.error(`  ${d.page}`); last = d.page; }
    if (d.reordered) {
      console.error(`    ${d.key}: same entries, different order`);
      continue;
    }
    for (const r of d.removed) console.error(`    ${d.key}  - ${r}`);
    for (const a of d.added) console.error(`    ${d.key}  + ${a}`);
  }
  console.error("\nIf the change was intended, re-record it and let the diff show what moved:");
  console.error("  node scripts/check-structure.mjs --update");
  process.exit(1);
}

console.log("\nstructure checks passed");
