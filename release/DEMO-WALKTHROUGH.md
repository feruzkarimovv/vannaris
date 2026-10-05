# Vannaris: a 90-second local demo

Demonstrate backend/AI evaluation engineering with a synthetic, credential-free pipeline separate from the measured archive. This is not a new vendor benchmark or human-validation study.

## Prepare

```bash
make setup
make setup-browser
make verify
make demo
```

Open **http://127.0.0.1:8000/demo.html**. `make demo` generates `.demo/` and serves `.demo/site` on port 8000. `make demo-build` generates artifacts without starting a server. Run setup and verification before recording; a planned check is not a passed check.

The scenario uses 120 synthetic questions and three mock vendor paths. One deliberately invalid response is recorded as a vendor error. The first judging attempt has no Google key and cannot publish a complete ensemble. Recovery reuses accepted Anthropic/OpenAI scores and calls the missing Google judge only; it makes no additional vendor calls. The generated manifest and events record the actual mock work and zero API spend.

The default scenario shows 360 persisted mock responses, 718 accepted scores before recovery, 359 recovery judge calls, and 359 complete panels afterward. Describe these as synthetic scenario counts. The database and request log downloads under `demo-artifacts/` contain fabricated data only.

To show the real archive afterward, stop the server with Ctrl+C and run `make serve`, then open http://127.0.0.1:8000/results.html. Both servers use the same port.

## Storyboard

| Time | Show | Say |
| --- | --- | --- |
| 0–15 seconds | Problem statement and persistent synthetic label | “Vannaris evaluates search APIs for AI agents. The hard part is preserving evidence when retrieval succeeds but judging fails. This demo uses mock APIs and never changes the real archive.” |
| 15–35 seconds | Run stages and interrupted judging | “The runner stores the exact questions and responses before judging. Accepted judge calls are checkpointed. A failed stage leaves a recoverable run.” |
| 35–55 seconds | Recovery evidence, stable identity, completed/missing work | “Recovery fills missing judge work from the original responses. It preserves the run identity and reuses accepted work instead of retrieving everything again.” |
| 55–75 seconds | Publication refusal, subsequent export, provenance | “Incomplete ensembles cannot publish. Only derived measurements leave the pipeline. Recomputed statistics have input hashes; they are not a new live experiment.” |
| 75–90 seconds | Limits and measured-archive entry | “The real archive is dated. One human pass supports a limited ordering finding; independent validation remains open. Those limits are visible beside the implementation.” |

Use the actual generated values. Do not invent speeds, call counts, cost savings, or human-label results during narration.

## Optional measured-archive extension

After switching to `make serve`:

1. Open Results, choose W31 then W35 using **Run**, and show the URL's selected run.
2. Show the retrieval date, archive age, incomplete panels, and category coverage.
3. Search a public query and use **Inspect query** to open **Query evidence**. Show vendor/judge data for that run; close with Escape and show focus returning.
4. Open Data and identify matching CSVs. Explain that public recomputation starts there; raw retrieved content remains private.

If an old run lacks detailed evidence, show the unavailable state and matching downloads. Do not present another week's evidence as the selected run.

## Optional rendered video

With the supported Chromium browser and `ffmpeg` installed:

```bash
make demo-video
```

Outputs:

- `.artifacts/release/vannaris-demo.mp4`
- `.artifacts/release/demo-cover.png`
- `.artifacts/release/capture.json`

The 32-second clip assembles actual browser-rendered still frames from the synthetic walkthrough. It is a shareable view of recorded stage evidence, not a real-time recording of API calls, interaction performance, or recovery duration. The narration above is a separate 90-second live presentation outline. Keep synthetic labels intact and review the captured frames before publishing.

## Before publishing

- Record integrated validation results; the earlier onboarding test count is not this release's evidence.
- Keep credentials, private vendor response text, and active withheld questions off screen.
- Keep synthetic labels and historical dates visible.
- Distinguish local release changes from the previously deployed website.
- Deployment, a recording upload, and a release post are separate owner actions. This task prepares reviewable files.
