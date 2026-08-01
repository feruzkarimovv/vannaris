# Publish checklist

The site in `site/` is complete and correct. It is **not cleared to go live.** This file is the gate
between "built" and "published", and the items in the first section are founder decisions, not
engineering tasks — none of them should be resolved by whoever happens to be doing the next commit.

---

## 1. Blocking — the name

**"SearchBench" is a working name and has not been cleared.**

- [x] **Registrar check** on the domain family (`.com` / `.ai` / `.dev` / `.io`) — done 2026-08-01
      against registry RDAP records, written up in `docs/10-name-clearance-2026-08-01.md`.
      `searchbench.com` is held by a corporate brand-protection registrar; `searchbench.ai` is parked
      and expires 2026-09-09; `.dev` and `.io` are free. All four `retrievalreferee` TLDs are free.
- [ ] **A real USPTO search** (Trademark Search / TESS), not a general web search. No conflicting
      registration surfaced in general search, which is not the same as clearance. **Still open, and
      it is now the only blocker in this section.** Every programmatic route is closed — see
      `docs/10` §3, which also gives the two ways to close it. Search `SEARCHBENCH`, `SEARCH BENCH`
      and the chosen alternative in classes 009 and 042. A federal search is free.
- [ ] **Decide on the known conflict** — restated 2026-08-01, because it is bigger than `docs/03`
      recorded. Four GitHub projects now carry the exact name in this exact vertical, one of them
      pushed 2026-07-31, and "search benchmark" as a phrase has a 404-star occupant. The dormant
      project `docs/03` names does have a licence (MIT) and is not archived. Still low enforcement
      risk; materially more confusion and SEO risk than when the name was chosen. `docs/10` §2 and §4.
- [ ] Two candidate alternatives are already ruled out as live conflicts — one collides with an
      actively-promoted product from a well-known evaluation project, the other with a live
      database-benchmarking product positioned almost identically. `docs/03` names both, and names
      the zero-conflict fallback it recommends.

Renaming is one command and touches every file that carries the name:

```bash
python scripts/rename.py --dry-run RetrievalReferee   # see what would change
python scripts/rename.py RetrievalReferee
.venv/bin/python -m src.export && node scripts/check-site.mjs
```

Do this **before** buying a domain, filing anything, or putting a public URL anywhere.

## 2. Blocking — legal

- [ ] **An attorney reads the methodology** before launch: what is stored, what is published,
      whether the derived-scores-only boundary holds, and whether BYOK insulates the router layer.
      `docs/03` says explicitly that this is the highest-value dollar spent before going public and
      that it is not a substitute for counsel.
- [ ] **Confirm the vendor set one more time** against each vendor's *current* terms. Terms change,
      and the readings in `docs/03` were taken on 2026-07-30.
- [ ] **Decide on Tavily and Brave.** Approach them for written consent, or launch without them and
      say why. Both run public self-benchmarks of their own, which is real leverage in that
      conversation. Either answer is defensible; leaving it undecided while publishing is not.
- [ ] Confirm the "not affiliated with any vendor" disclaimer is present on every page footer. It is,
      as of this writing — re-check after any footer edit.
- [ ] Set `REPO_URL` in `src/export.py` to the public repository URL and re-export. Until it is set,
      the site's "Source" link renders as inert text reading "not public yet" rather than pointing
      somewhere unhelpful — which is honest, but it is also the single most important link on a site
      whose whole claim is that you can check the work.

## 3. Blocking — don't overclaim

The site currently reports **1 published week** and states in the hero that the weekly schedule has
not started. That is true today, and the site now reads both facts from the data rather than
asserting them: every run records whether a scheduler or a person invoked it, and the cadence
sentences on the landing, results and methodology pages are derived from
`track_record.schedule_started`. They will change on their own the first time the cron fires, and
not before. Before launch:

- [ ] Confirm nothing on the site, in the README, or in any launch post describes the benchmark as
      "continuously", "weekly", or "regularly" run. The site derives that count from the data
      (`track_record.weeks_published`), so it cannot drift on its own — launch copy written elsewhere
      can, and so can the README, which is hand-written.
- [ ] Decide whether to launch at one week of data at all. The alternative is to start the schedule
      first and launch at three or four weeks, when "continuously run" becomes true and the site's
      most-repeated caveat disappears on its own.

## 4. Before the repository goes public

- [ ] `git status` and confirm `.env` is ignored. Verify **before** the first push, not after.
- [ ] `git log -p | grep -i -E "sk-|api[_-]?key"` on the full history. A key committed once and
      deleted later is still in the history and still needs rotating.
- [ ] Move all eight keys into GitHub Actions secrets — `.github/workflows/weekly.yml` reads them
      from there and from nowhere else. See the weekly-run section of `README.md`. Note that arming
      the scheduled runner is **not** gated by this checklist: the runner can start accruing weeks
      while the name and legal questions are still open, and the recommended sequencing is that it
      does.
- [ ] Confirm `data/*.db` is ignored. The database holds raw vendor responses, which are exactly what
      this project's scoping avoids publishing.
- [ ] `node scripts/check-site.mjs` passes.
- [ ] `.venv/bin/python -m src.export` runs clean and the diff to `site/data/` and `site/export/` is
      committed.

## 5. Hosting

`site/` is static with no build step and no external requests, so GitHub Pages serving from the
`site/` directory works with no configuration. Two things to check after the first deploy:

- [ ] The four pages load and every chart renders (a chart that draws nothing still passes a naive
      link check; `scripts/check-site.mjs` catches it, so run it against the deployed HTML too).
- [ ] **Make the `og:image` and `og:url` tags absolute.** They are relative right now because there
      is no canonical domain yet, and most platforms will not resolve a relative `og:image` — the
      link will preview blank. Regenerate the card after any run with
      `python scripts/make_og_image.py`; it is drawn from the current export, so a stale card means
      a stale export.
- [ ] The CSV download links resolve. They are relative paths and will break if the site is deployed
      under a path prefix without the whole `site/` directory moving together.

## 6. Not blocking, but the first thing a reviewer will attack

- [ ] **The human-labelled calibration set.** 100–200 examples labelled by hand, compared against the
      ensemble monthly, rubric refined against the specific disagreements found. The measured
      1.22-point spread between judge families is published on the site precisely because it is the
      largest caveat on every other number — and right now nothing audits it.

---

## What is already done

Recorded so it is not re-litigated:

- The site publishes derived scores only. Retrieved URLs, titles, snippets and synthesized answers
  never reach the export, and `src/export.py` fails the build if they do.
- The published run is chosen by coverage rather than recency, so a smoke test cannot become a
  published result. A previous smoke test did exactly that; the fix is in `src/runner.py`, the
  column that made it detectable is in `src/storage/schema.sql`, and the incident is in the site's
  methodology changelog rather than quietly repaired.
- Every figure on the site is generated from the export, including figures inside sentences.
  `scripts/check-site.mjs` fails on any that does not resolve.
- Data is CC BY 4.0, code is MIT, and both licences are in the repository.
