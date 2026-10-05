# Contributing

Vannaris publishes measurements, so a change must preserve the path from a displayed claim to its evidence. The most useful contribution is a reproducible correction: identify a figure, provide the input and recomputation, and explain the effect.

Start with [CURRENT-STATE.md](CURRENT-STATE.md) and the [engineering case study](docs/18-engineering-case-study.md). Dated research, applications, and handoffs are records, not current setup instructions.

## Local development without credentials

Use Python 3.13 and Node 22.

```bash
make setup
make check
make demo
```

`make setup` installs locked dependencies. `make check` runs the offline repository gate. `make demo` generates a synthetic database and site under `.demo/`, then serves http://127.0.0.1:8000/demo.html. It makes no vendor or judge calls. `make serve` serves the measured archive instead. Stop one server before starting the other.

```bash
make setup-browser
make check-browser
make verify
```

The browser checks exercise actual rendering and interaction. `make verify` combines the offline gate, measured-archive browser checks, demo generation, and demo browser checks. If a dependency is absent, install it through the supported setup; do not loosen a gate to turn missing validation into a passing result.

Paid key checks and live evaluation are optional, separate operations. Do not run them as a prerequisite for an ordinary code or site contribution. Never dispatch the weekly workflow, spend another person's API budget, or deploy a change without explicit authorization.

## Evidence required in a PR

One coherent change per PR against `main`. Describe observable behavior, relevant validation, and material limits. Include:

- the problem and expected result;
- the tests or checks that exercised it;
- any changed meaning of a published metric or figure;
- whether real API calls, human studies, or deployment were performed.

Tests should verify meaningful behavior and refusal paths: incomplete ensembles, unsafe export content, recovery metadata, publication eligibility, missing category coverage, and inaccessible interactions. A count of tests is not a substitute for these guarantees.

## Methodology and publication changes

A change to the rubric, judge model pins, aggregation, completeness floors, or uncertainty calculation changes what a published number means. Include a methodology changelog entry and the analysis revision. Preserve run IDs, retrieval timestamps, triggers, and query hashes when recomputing derived results; analysis performed today is not a new benchmark run.

Use the same declared category weights and eligible observations across score, interval, routing, and heldout diagnostics. Unresolved comparisons are not evidence of equivalence. Keep conditional quality, vendor availability, and judge missingness distinct.

Validate a candidate judge with a production-length prompt before suggesting it for a measured run. A short successful probe does not establish reliability on the real rubric. Keep the cross-family ensemble, full-panel rule, bias mitigations, and publication floors intact.

Questions are run inputs. A future query-set change must get a new identity and must not silently relabel historical observations. Candidate questions may be developed separately; registered withheld questions and their commitment lifecycle require the maintainer's decision. Never edit an active commitment or copy withheld question text into Git.

## Adding a vendor

`src/vendors/adapters.py::REGISTRY` controls participation in the public comparison. Before proposing an addition, review the vendor's current terms on benchmarking, comparative publication, storage, and resale. Record primary sources and unresolved terms in a dated research note. Where consent is required, the public adapter remains excluded until the maintainer confirms written permission.

Tavily, Brave, Seltz, and Search Router are not part of the shipped public set. An available API key does not establish permission to publish a benchmark. Read `docs/03-legal-and-vendor-terms.md` and subsequent verification notes before any vendor change.

## Files and data boundaries

- Generated files under `site/data/` and `site/export/` come from supported export or analysis commands. Do not hand-edit measurements or populate numbers in HTML.
- Raw databases, `.env`, calibration tasks containing retrieved content, and active withheld question text stay outside Git and public artifacts.
- Workflow recovery uses sanitized status and, optionally, CMS-encrypted database evidence addressed to an owner-provided public X.509 certificate. Keep the private key outside Actions. This release does not establish that historical remote artifacts were reviewed or deleted.
- Synthetic outputs must be marked as synthetic, live in `.demo/` or a temporary directory, and use their own database. Do not mix them into real runs.
- Preserve existing dated `docs/`, `applications/`, and handoffs. Append dated corrections or create a new current document rather than rewriting the historical record.
- Keep dependencies locked and use `npm ci`; avoid ad hoc installs that prune or bypass the committed toolchain.

## Code and site conventions

Python functions use type hints; comments explain the reason for an unusual choice, especially where a production incident produced it. Keep external calls behind adapters so deterministic offline tests can exercise recovery and error handling.

The site is static HTML/CSS/JavaScript. A framework is not required for its publication workflow. Figures come from generated data, charts have table equivalents, controls work by keyboard, and animation respects reduced motion. Query evidence must match the selected run; if its detail is unavailable, show that state and the matching downloads instead of substituting another run.

## Security

`.env` contains credentials and is ignored. Inspect only the names and presence of injected variables when troubleshooting; never echo values or credential files. A live key check makes API calls and may spend money. If a key leaks, rotate it through the account owner and report the incident without reposting the value.
