# Cross-Eval

This directory holds the fixture-driven agent-vs-agent evaluation scaffold for the Daggerheart skills repo.

## What It Does

The cross-eval flow runs a checked-in user request through alternating coding-agent lanes:

- attempt 1: Codex generates and Claude judges
- attempt 2: Claude generates and Codex judges
- attempt 3: Codex generates and Claude judges again

The run stops on the first failure so it does not waste spend once a regression is found.

Each generated output is still checked with the local deterministic validator so the LLM judge is not the only source of truth.

## Fixture Model

Each scenario source file under `scenarios/` defines the case metadata.

Checked-in fixtures under `fixtures/<scenario-id>/` hold:

- `user-request.txt`: the exact user request sent for generation
- `verification-properties.json`: the distilled verification properties used by the judge

Generate or refresh those fixtures with:

```bash
python3 scripts/render_cross_eval_fixtures.py
```

## Local Smoke Test

Use mock mode first to verify the pipeline without calling model APIs:

```bash
scripts/run_cross_eval_local.sh mock
```

That writes per-attempt prompts, outputs, JSON reports, a markdown summary, and JUnit XML under `cross-eval/`.

## Live Local Run

After exporting `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`, run:

```bash
scripts/run_cross_eval_local.sh
```

Useful options:

- `--scenario <path>`
- `--max-attempts 3`

## GitHub-Like Local Flow

If you want to mirror the split GitHub Actions flow locally:

1. Prepare prompts only:

```bash
scripts/run_cross_eval_local.sh prepare --output-root /tmp/cross-eval-local
```

2. Generate outputs however you want into the prepared `attempt-*` folders.

3. Evaluate those existing outputs:

```bash
scripts/run_cross_eval_local.sh evaluate --output-root /tmp/cross-eval-local
```
