# Cross-Eval

This directory holds the first agent-vs-agent evaluation scaffold for the Daggerheart skills repo.

## What It Does

The cross-eval flow runs the same scenario through two coding agents:

- Codex generates an output and Claude judges it.
- Claude generates an output and Codex judges it.

Each generated output is also checked with the local deterministic validator so the LLM judge is not the only source of truth.

## Scenario Files

Each scenario is a JSON file under `scenarios/` with:

- the end-user prompt
- the target skill path
- the expected tier and role
- a sample output for mock runs
- the rubric files to use for judging

## Local Smoke Test

Use mock mode first to verify the pipeline without calling model APIs:

```bash
python3 scripts/run_cross_eval_session.py --mock
```

That writes prompts, outputs, a JSON report, a markdown summary, and JUnit XML under `cross-eval/`.

## Live Local Run

After exporting `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`, run:

```bash
python3 scripts/run_cross_eval_session.py
```

You can also point at a different scenario with `--scenario`.
