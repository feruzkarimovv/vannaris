"""Run the real HTTP/parsing/storage/export pipeline without a network connection.

Every response, score, latency and ledger amount is fabricated. The mock
transport is supplied to every HTTP client; API keys and local measured data are
never read. Outputs live in a separate, explicitly marked demo directory.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import io
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

from . import runner, storage
from .judge.ensemble import FamilyLimiter, JUDGES, median_overall
from .vendors.adapters import ExaAdapter, LinkupAdapter, SerperAdapter

ROOT = Path(__file__).resolve().parent.parent
KIND = "synthetic_offline_demo"
WARNING = "SYNTHETIC — fabricated data; no vendor or judge API was called."
WEEK = "2099-W01"
STARTED_AT = "2099-01-01T06:23:00+00:00"
CATEGORIES = (
    "general_facts", "breaking_news", "local_shopping", "code_technical",
    "multi_hop", "long_tail",
)
QUERIES_PER_CATEGORY = 20
FAKE_KEYS = {family: "SYNTHETIC-NO-NETWORK" for family, _ in JUDGES}


class SyntheticAlpha(SerperAdapter):
    name = "fixture_alpha"


class SyntheticBravo(ExaAdapter):
    name = "fixture_bravo"


class SyntheticDelta(LinkupAdapter):
    name = "fixture_delta"


PROVIDERS = (SyntheticAlpha, SyntheticBravo, SyntheticDelta)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


async def without_progress(awaitable):
    # The walkthrough reports five useful stages. Its durable request trace
    # carries the detail; hundreds of carriage-return updates add no evidence.
    with contextlib.redirect_stdout(io.StringIO()):
        return await awaitable


def build_queries() -> list[dict]:
    return [
        {
            "id": f"fx-demo-{index:03d}", "category": category,
            "text": f"FIXTURE QUERY FX-{index:03d} — synthetic placeholder, not a real question",
            "source": "synthetic_offline_demo", "rotates": 0,
        }
        for index, category in enumerate(
            category for category in CATEGORIES for _ in range(QUERIES_PER_CATEGORY)
        )
    ]


class SyntheticTransport:
    """Strict local replies in each provider's actual API response format."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.requests: list[dict] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        host = request.url.host
        vendor = {
            "google.serper.dev": "fixture_alpha", "api.exa.ai": "fixture_bravo",
            "api.linkup.so": "fixture_delta",
        }.get(host)
        if vendor:
            query = body.get("q") or body.get("query")
            index = int(re.search(r"FX-(\d+)", query).group(1))
            self.requests.append({
                "stage": "fetch", "provider": vendor, "query_id": f"fx-demo-{index:03d}",
                "request_sha256": hashlib.sha256(request.content).hexdigest(),
            })
            # Valid JSON with an invalid provider field exercises the parser
            # exception boundary rather than simulating only transport errors.
            if vendor == "fixture_alpha" and index == 0:
                payload = {"organic": None}
            else:
                rows = [{
                    "url": f"https://example.invalid/{vendor}/fx-{index:03d}/{rank}",
                    "link": f"https://example.invalid/{vendor}/fx-{index:03d}/{rank}",
                    "title": f"SYNTHETIC {vendor} result {rank + 1}",
                    "name": f"SYNTHETIC {vendor} result {rank + 1}",
                    "snippet": f"SYNTHETIC {vendor} FX-{index:03d}. Not retrieved content.",
                    "text": f"SYNTHETIC {vendor} FX-{index:03d}. Not retrieved content.",
                    "content": f"SYNTHETIC {vendor} FX-{index:03d}. Not retrieved content.",
                } for rank in range(10)]
                payload = {
                    "fixture_alpha": {"organic": rows},
                    "fixture_bravo": {"results": rows, "costDollars": {"total": 0.007}},
                    "fixture_delta": {"results": rows},
                }[vendor]
            return httpx.Response(200, request=request, json=payload)

        family = {
            "api.anthropic.com": "anthropic", "api.openai.com": "openai",
            "generativelanguage.googleapis.com": "google",
        }.get(host)
        if family is None:
            raise AssertionError(f"Demo refuses an unrecognised HTTP destination: {host}")
        prompt = (body["contents"][0]["parts"][0]["text"] if family == "google"
                  else body["messages"][0]["content"])
        index = int(re.search(r"FX-(\d+)", prompt).group(1))
        vendor = re.search(r"fixture_(alpha|bravo|delta)", prompt).group(0)
        vendor_index = [provider.name for provider in PROVIDERS].index(vendor)
        family_index = [name for name, _ in JUDGES].index(family)
        # Pure arithmetic instead of shared random state makes async completion
        # order irrelevant to the generated scores.
        noise = ((index * 17 + self.seed * 13) % 19 - 9) / 20
        overall = round(7.2 + vendor_index * 0.35 + family_index * 0.1 + noise, 2)
        text = json.dumps({
            "relevance": overall, "freshness": round(overall - 0.2, 2),
            "citation_quality": round(overall + 0.15, 2), "overall": overall,
            "rationale": "SYNTHETIC fixed score; no model evaluated this response.",
        })
        self.requests.append({
            "stage": "judge", "provider": family, "vendor": vendor,
            "query_id": f"fx-demo-{index:03d}",
            "request_sha256": hashlib.sha256(request.content).hexdigest(),
        })
        returned_model = f"SYNTHETIC-{family}-fixture"
        payload = {
            "anthropic": {"model": returned_model, "content": [{"type": "text", "text": text}],
                          "usage": {"input_tokens": 100, "output_tokens": 30}},
            "openai": {"model": returned_model, "choices": [{"message": {"content": text}}],
                       "usage": {"prompt_tokens": 100, "completion_tokens": 30}},
            "google": {"modelVersion": returned_model,
                       "candidates": [{"content": {"parts": [{"text": text}]}}],
                       "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 30}},
        }[family]
        return httpx.Response(200, request=request, json=payload)


def _export(work: Path) -> subprocess.CompletedProcess:
    return subprocess.run([
        sys.executable, "-m", "src.export", "--db", str(work / "fixture.db"),
        "--queries", str(work / "queries.json"), "--out", str(work / "site"),
        "--heldout-manifest", str(work / "heldout.json"),
        "--labels", str(work / "labels"), "--no-history",
    ], cwd=ROOT, capture_output=True, text=True, check=False)


def _copy_site(work: Path) -> None:
    destination = work / "site"
    destination.mkdir()
    # Measured bundles, exports, and vendor pages are deliberately not copied.
    for source in (ROOT / "site").iterdir():
        if source.is_file() and source.suffix in (".html", ".txt", ".xml"):
            shutil.copy2(source, destination / source.name)
    shutil.copytree(ROOT / "site" / "assets", destination / "assets")


def _mark_synthetic_site(work: Path) -> None:
    data_dir = work / "site" / "data"
    bundle_path = data_dir / "bundle.js"
    text = bundle_path.read_text()
    bundle = json.loads(text[text.index("{"):text.rindex("}") + 1])
    bundle["synthetic"] = True
    bundle["synthetic_warning"] = WARNING
    bundle["vendors"] = [{
        "id": provider.name, "label": f"Synthetic {name}", "docs": "../demo.html",
        "note": f"{provider.__bases__[0].__name__} exercised with fabricated replies.",
    } for provider, name in zip(PROVIDERS, ("Alpha", "Bravo", "Delta"))]
    for vendor in bundle["latest"]["vendors"]:
        vendor["label"] = next(v["label"] for v in bundle["vendors"] if v["id"] == vendor["vendor"])
    bundle_path.write_text("// SYNTHETIC offline demo. Never a measurement.\nwindow.SB_DATA = "
                           + json.dumps(bundle, indent=1, allow_nan=False) + ";\n")
    for path in data_dir.glob("*.json"):
        value = json.loads(path.read_text())
        value.update({"synthetic": True, "synthetic_warning": WARNING})
        write_json(path, value)
    export_manifest = work / "site" / "export" / "manifest.json"
    value = json.loads(export_manifest.read_text())
    value.update({"synthetic": True, "synthetic_warning": WARNING})
    write_json(export_manifest, value)
    subprocess.run([sys.executable, "scripts/make_vendor_pages.py", "--site", str(work / "site")],
                   cwd=ROOT, capture_output=True, text=True, check=True)
    # The generated site is browsable, so every route needs a visible warning,
    # including pages whose normal copy describes the measured benchmark.
    for page in (work / "site").rglob("*.html"):
        html = page.read_text()
        banner = ('<aside role="note" style="padding:12px 24px;background:#ffe9a3;'
                  'color:#342700;font:600 14px/1.6 sans-serif;text-align:center">'
                  + WARNING + ' <a href="/demo.html">View the demo walkthrough</a></aside>')
        html = re.sub(r"(<body\b[^>]*>)", lambda match: match.group(1) + banner, html, count=1)
        html = re.sub(r"<title>(.*?)</title>", r"<title>SYNTHETIC DEMO — \1</title>", html, count=1)
        page.write_text(html)
    (work / "site" / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    (work / "site" / "sitemap.xml").unlink(missing_ok=True)


async def _run(work: Path, seed: int) -> dict:
    queries = build_queries()
    query_set = {"name": "SYNTHETIC OFFLINE DEMO", "version": "fixture-demo-v1", "queries": queries}
    write_json(work / "queries.json", query_set)
    write_json(work / "heldout.json", {"sets": [], "rotate_after_weeks": 4})
    (work / "labels").mkdir()
    _copy_site(work)
    digest = runner.load_queries(work / "queries.json")[1]
    run_id = f"fixture-demo-seed-{seed}"
    conn = storage.connect(work / "fixture.db")
    events: list[dict] = []
    stages: list[dict] = []

    def stage(identifier: str, title: str, detail: str, **metrics) -> None:
        stages.append({"id": identifier, "title": title, "status": "passed",
                       "detail": detail, "metrics": metrics})
        events.append({"at": timestamp(), "stage": identifier, "detail": detail, "metrics": metrics})
        print(f"  {title}: {detail}")

    transport = SyntheticTransport(seed)
    try:
        runner.persist_run(conn, run_id, WEEK, digest, queries, [], STARTED_AT, "manual",
                           provenance={"kind": KIND, "synthetic": True, "seed": seed})
        conn.execute("UPDATE runs SET notes=? WHERE id=?", (WARNING, run_id))
        conn.commit()

        def checkpoint(response) -> None:
            index = int(response.query_id.rsplit("-", 1)[1])
            response.latency_ms = 80 + [p.name for p in PROVIDERS].index(response.vendor) * 35 + index % 15
            runner.persist_response(conn, run_id, response)

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport.handle), trust_env=False) as client:
            responses = await without_progress(runner.fetch_all(
                client, [provider(api_key="SYNTHETIC-NO-NETWORK") for provider in PROVIDERS],
                queries, on_response=checkpoint,
            ))
            runner.mark_retrieval_complete(conn, run_id)
            errors = [response for response in responses if not response.ok]
            if len(errors) != 1 or errors[0].query_id != "fx-demo-000":
                raise AssertionError("The injected malformed vendor response was not isolated.")
            stage("fetch", "Fetch and isolate", "One malformed provider reply became a recorded error; other replies survived.",
                  vendor_calls=len(responses), vendor_errors=len(errors))
            count = conn.execute("SELECT COUNT(*) FROM raw_responses WHERE run_id=?", (run_id,)).fetchone()[0]
            if count != len(responses):
                raise AssertionError("A completed response did not reach its checkpoint.")
            stage("checkpoint", "Persist before judging", "Every provider response is recoverable from SQLite before a judge runs.",
                  responses_on_disk=count, judge_scores_on_disk=0)

            qmap = {query["id"]: query for query in queries}
            first_attempt = runner.begin_judging_attempt(conn, run_id, provenance={"kind": KIND, "seed": seed})
            first = await without_progress(runner.judge_all(
                client, {family: key for family, key in FAKE_KEYS.items() if family != "google"},
                responses, qmap, "01 January 2099",
                conn=conn, run_id=run_id, attempt_id=first_attempt,
                judge_sems={family: FamilyLimiter(16, 0) for family, _ in JUDGES},
            ))
            problems = runner.validity(first, responses)
            if not problems:
                raise AssertionError("An incomplete ensemble was accepted.")
            runner.finish_judging_attempt(conn, first_attempt, status="partial")
            refused = _export(work)
            (work / "export-refusal.log").write_text(refused.stdout + refused.stderr)
            if refused.returncode == 0 or "Nothing exported" not in refused.stderr:
                raise AssertionError("The real exporter did not refuse the incomplete run: " + refused.stderr)
            if (work / "site" / "data" / "bundle.js").exists():
                raise AssertionError("An incomplete run wrote a display bundle.")
            accepted_before = conn.execute("SELECT COUNT(*) FROM judge_scores").fetchone()[0]
            first_calls = sum(row["stage"] == "judge" for row in transport.requests)
            stage("incomplete", "Refuse incomplete ensembles", "Google's mock key is missing. Accepted Anthropic and OpenAI scores survive; publication refuses this run.",
                  accepted_scores=accepted_before, complete_ensembles=0, export_exit_code=refused.returncode)

            cost_before = conn.execute("SELECT SUM(cost_usd) FROM raw_responses WHERE run_id=?", (run_id,)).fetchone()[0]
            prior_ids = {row[0] for row in conn.execute("SELECT id FROM judge_scores")}
            request_boundary = len(transport.requests)
            recovered_queries = runner.load_run_queries(conn, run_id)
            recovered = runner.load_responses(conn, run_id)
            second_attempt = runner.begin_judging_attempt(conn, run_id, provenance={"kind": KIND, "seed": seed})
            complete = await without_progress(runner.judge_all(
                client, FAKE_KEYS, recovered, {q["id"]: q for q in recovered_queries}, "01 January 2099",
                conn=conn, run_id=run_id, attempt_id=second_attempt,
                judge_sems={family: FamilyLimiter(16, 0) for family, _ in JUDGES},
            ))
            if runner.validity(complete, recovered):
                raise AssertionError("Recovery did not restore complete usable ensembles.")
            runner.finish_judging_attempt(conn, second_attempt, status="completed")
            runner.aggregate(conn, WEEK, run_id, recovered, complete,
                             {q["id"]: q for q in recovered_queries})
            cost_after = conn.execute("SELECT SUM(cost_usd) FROM raw_responses WHERE run_id=?", (run_id,)).fetchone()[0]
            recovered_requests = transport.requests[request_boundary:]
            recovered_count = sum(median_overall(scores) is not None for scores in complete.values())
            recovery = {
                "same_run": conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1,
                "same_week": conn.execute("SELECT week FROM runs WHERE id=?", (run_id,)).fetchone()[0] == WEEK,
                "original_cost_preserved": cost_before == cost_after,
                "accepted_scores_reused": prior_ids <= {row[0] for row in conn.execute("SELECT id FROM judge_scores")},
                "vendor_calls_repeated": sum(row["stage"] == "fetch" for row in recovered_requests),
                "judge_calls_first_attempt": first_calls,
                "judge_calls_recovery": len(recovered_requests),
            }
            if (not all(recovery[name] for name in ("same_run", "same_week", "original_cost_preserved", "accepted_scores_reused"))
                    or recovery["vendor_calls_repeated"] != 0
                    or any(row["provider"] != "google" for row in recovered_requests)):
                raise AssertionError("Recovery rewrote evidence or repeated an accepted call.")
            stage("recover", "Resume missing work", "Recovery calls only the missing judge, retaining the original run, date, responses, costs, and accepted scores.",
                  complete_ensembles=recovered_count, repeated_vendor_calls=0,
                  recovery_judge_calls=len(recovered_requests))

        exported = _export(work)
        (work / "export.log").write_text(exported.stdout + exported.stderr)
        if exported.returncode:
            raise AssertionError("Recovered synthetic export failed: " + exported.stderr)
        _mark_synthetic_site(work)
        stage("export", "Export safely", "The real exporter generated derived CSVs and JSON. The separate demo site labels every route as synthetic.",
              complete_ensembles=recovered_count, actual_api_spend_usd=0)
        source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
        manifest = {
            "schema_version": 1, "kind": KIND, "synthetic": True, "warning": WARNING,
            "seed": seed, "generated_at": timestamp(), "run": {
                "id": run_id, "week": WEEK, "query_set_hash": digest,
                "n_queries": len(queries), "n_vendors": len(PROVIDERS),
            }, "stages": stages,
            "injected_failures": [
                {"kind": "malformed_vendor_payload", "provider": "fixture_alpha", "detail": "organic is null for fx-demo-000"},
                {"kind": "missing_judge_key", "provider": "google", "detail": "First attempt has no Google mock key"},
            ], "recovery": recovery,
            "checks": [
                {"id": "isolation", "title": "Malformed reply isolated", "passed": True, "detail": "All 360 response envelopes persisted."},
                {"id": "refusal", "title": "Incomplete export refused", "passed": True, "detail": "No bundle was written after the first attempt."},
                {"id": "resume", "title": "Accepted evidence reused", "passed": True, "detail": "Only 359 missing Google judgements were requested."},
                {"id": "privacy", "title": "Raw content excluded", "passed": True, "detail": "The production export's content guards ran."},
            ], "totals": {
                "vendor_calls": len(responses), "failed_vendor_responses": len(errors),
                "successful_vendor_responses": len(responses) - len(errors),
                "complete_ensembles": recovered_count, "actual_api_spend_usd": 0,
                "simulated_vendor_cost_usd": round(cost_after, 6),
            }, "artifacts": {
                "database": "demo-artifacts/fixture.db", "queries": "demo-artifacts/queries.json", "events": "events.json",
                "requests": "demo-artifacts/requests.jsonl",
                "bundle": "data/bundle.js", "export_manifest": "export/manifest.json",
            }, "provenance": {
                "source_sha": source.stdout.strip() if source.returncode == 0 else None,
                "python_version": platform.python_version(), "transport": "httpx.MockTransport",
                "httpx_version": httpx.__version__,
                "source_files_sha256": {
                    path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                    for path in ("src/demo.py", "src/runner.py", "src/judge/ensemble.py",
                                 "src/vendors/base.py", "src/vendors/adapters.py",
                                 "src/storage/schema.sql", "src/export.py")
                },
                "network": "disabled_by_transport", "latency_kind": "fabricated",
                "cost_kind": "fabricated", "score_kind": "fabricated",
                "determinism": "Query text and scores depend only on seed; execution timestamps and database IDs vary.",
            },
        }
        write_json(work / "site" / "events.json", {"kind": KIND, "synthetic": True, "events": events})
        (work / "requests.jsonl").write_text("".join(json.dumps(row) + "\n" for row in transport.requests))
        # Downloadable recovery evidence is safe only because this entire
        # database is fabricated. Nothing from data/vannaris.db is consulted.
        downloads = work / "site" / "demo-artifacts"
        downloads.mkdir()
        for name in ("fixture.db", "queries.json", "requests.jsonl"):
            shutil.copy2(work / name, downloads / name)
        manifest["hashes"] = {
            path.relative_to(work).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [work / "queries.json", work / "fixture.db", work / "site" / "data" / "latest.json",
                         work / "site" / "export" / "manifest.json", work / "requests.jsonl"]
        }
        write_json(work / "manifest.json", manifest)
        write_json(work / "site" / "demo.json", manifest)
        return manifest
    finally:
        conn.close()


def build_demo(output: Path | str, *, seed: int = 7) -> dict:
    destination = Path(output).resolve()
    measured_site = ROOT / "site"
    protected = ("site", "data", "labels", "src", "tests", "scripts", "docs", "applications",
                 ".github", ".git", ".venv", "node_modules")
    if (destination == ROOT or destination in measured_site.parents
            or any(destination.is_relative_to(ROOT / name) for name in protected)):
        raise ValueError("Demo output must be separate from source files and measured data; use .demo/ or a temporary directory.")
    if destination.exists() and any(destination.iterdir()):
        marker = destination / "manifest.json"
        if not marker.is_file() or json.loads(marker.read_text()).get("kind") != KIND:
            raise ValueError("Refusing to replace a non-demo output directory.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".vannaris-demo-", dir=destination.parent))
    try:
        manifest = asyncio.run(_run(staging, seed))
        if destination.exists():
            shutil.rmtree(destination)
        staging.rename(destination)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", "--output", default=str(ROOT / ".demo"), help="Separate synthetic output directory")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic synthetic score seed")
    args = parser.parse_args()
    print(WARNING)
    manifest = build_demo(args.out, seed=args.seed)
    print(f"\nDemo complete: {manifest['totals']['complete_ensembles']} complete synthetic ensembles; actual API spend $0.")
    print(f"Serve: python -m http.server 8000 --directory {Path(args.out) / 'site'}")
    print("Open: http://localhost:8000/demo.html")


if __name__ == "__main__":
    main()
