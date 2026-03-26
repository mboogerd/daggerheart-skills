# Cross-Eval

This directory holds the fixture-driven agent-vs-agent evaluation scaffold for the Daggerheart skills repo.

## What It Does

The cross-eval flow runs a checked-in user request through alternating provider lanes:

- attempt 1: OpenAI generates and Anthropic judges
- attempt 2: Anthropic generates and OpenAI judges
The run stops on the first failure so it does not waste spend once a regression is found.

Each generated output is still checked with the local deterministic validator so the LLM judge is not the only source of truth.

## Fixture Model

Each scenario source file under `scenarios/` defines the case metadata.

Checked-in fixtures under `fixtures/<scenario-id>/` hold:

- `user-request.txt`: the exact user request sent for generation
- `verification-properties.json`: the distilled verification properties used by the judge
- `verification-properties.schema.json`: the contract for the verification properties format

The verification properties have a suite-specific body inside a common envelope:

- common fields: scenario id, suite, validator, skill grounding, judge focus, generation requirements
- adversary creation adds explicit numeric bands and role expectations
- combat encounter planning adds required sections, party/budget expectations, and optional acquisition-hint expectations

For adversary creation, the numeric bands use explicit bound objects, for example:

```json
{
  "difficulty": {
    "lower_bound": 13,
    "upper_bound": 15
  }
}
```

Threshold bands are named explicitly as `first_threshold` and `second_threshold`.

For combat encounter planning, the verification properties instead express structural expectations such as:

```json
{
  "required_sections": [
    "Encounter Premise",
    "Battle-Point Budget",
    "Encounter Roster Plan"
  ],
  "allowed_acquisition_hints": [
    "prefer-existing",
    "prefer-new"
  ]
}
```

Generate or refresh those fixtures with:

```bash
python3 scripts/render_cross_eval_fixtures.py
```

## Local Smoke Test

Use mock mode first to verify the pipeline without calling model APIs:

```bash
bash scripts/run_cross_eval_local.sh mock
```

That writes per-attempt prompts, outputs, JSON reports, a markdown summary, and JUnit XML under `cross-eval/`.

## Live Local Run

After exporting `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`, run:

```bash
bash scripts/run_cross_eval_local.sh
```

Useful options:

- `--scenario <path>`
- `--max-attempts 2`
- `--openai-model gpt-5.4-nano`
- `--anthropic-model claude-haiku-4-5-20251001`
- `--lane anthropic-by-openai --attempt-number 2`

If one lane is failing and you want to rerun only that lane locally, use:

```bash
bash scripts/run_cross_eval_local.sh --scenario evals/cross-eval/scenarios/tier1_bridge_defense.json --lane anthropic-by-openai --attempt-number 2
```

Accepted lane names are:

- `openai-by-anthropic`
- `anthropic-by-openai`
- `openai-gen-anthropic-judge`
- `anthropic-gen-openai-judge`

The older `codex-*` and `claude-*` lane aliases still work for compatibility, but provider names are preferred.

## GitHub-Like Local Flow

If you want to mirror the split GitHub Actions flow locally:

1. Prepare prompts only:

```bash
bash scripts/run_cross_eval_local.sh prepare --output-root /tmp/cross-eval-local
```

2. Generate outputs however you want into the prepared `attempt-*` folders.

3. Evaluate those existing outputs:

```bash
bash scripts/run_cross_eval_local.sh evaluate --output-root /tmp/cross-eval-local
```
