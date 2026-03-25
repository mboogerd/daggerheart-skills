# Skill Evaluation Scaffolding

This directory holds light evaluation fixtures for the Daggerheart skill suite.

## Trigger Evaluation

Use `trigger-queries.sample.json` as a starting point for should-trigger and should-not-trigger queries. Copy it and expand it per skill.

For adversary creation, use:

- `adversary-creation.trigger.json`

## Output Evaluation

Use `output-rubric.md` to grade skill outputs for:

- correct skill activation
- structure and completeness
- Daggerheart-specific usefulness
- clarity and actionability

For adversary creation, also use:

- `adversary-creation-rubric.md`
- `adversary-creation.output-cases.json`
- `adversary-creation/samples/`

## Suggested Loop

1. choose one skill
2. write 10 to 20 trigger queries
3. run the agent multiple times per query
4. improve the `description`
5. run output-quality cases for the activated skill
6. tighten examples, edge cases, or templates based on failures

## Validator Scripts

- `scripts/validate-adversary-creation.py --case-file skills/evals/adversary-creation.output-cases.json`
- `scripts/validate-adversary-creation.py <markdown-file>`

## Cross-Eval

Use `evals/cross-eval/` for agent-vs-agent evaluations that:

- use checked-in user-request fixtures for generation
- use checked-in verification properties for judging
- validate the generated output deterministically
- alternate generator and judge roles across attempts
- stop early on the first failure
- emit JUnit so GitHub Actions can publish the run as a check

Local smoke test:

- `python3 scripts/run_cross_eval_session.py --mock`
