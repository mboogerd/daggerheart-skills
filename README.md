# Daggerheart Skill Suite

This suite is intentionally split into small, composable skills. Each skill handles one GM task well and defers adjacent work to a nearby skill when needed.

## Campaign Prep Pipeline

- `daggerheart-campaign-pitch`
- `daggerheart-campaign-frame-selection`
- `daggerheart-session-zero`
- `daggerheart-arc-planning`
- `daggerheart-session-planning`
- `daggerheart-scene-planning`
- `daggerheart-countdowns`

## Combat Prep Pipeline

- `daggerheart-combat-objectives`
- `daggerheart-encounter-budgeting`
- `daggerheart-adversary-selection`
- `daggerheart-adversary-creation`
- `daggerheart-adversary-scaling`
- `daggerheart-environment-design`

## Design Rules

- Every skill is self-contained.
- `SKILL.md` stays short and procedural.
- Reference files contain only the minimum rules needed for that skill.
- Progressive disclosure happens through local files next to each skill, not through citations back to the book.
- Skills should compose by handing off to one another cleanly.
- The suite should contain enough embedded game knowledge that a model can use a skill without prior Daggerheart or tabletop-RPG expertise.

## Content Strategy

- Put trigger and workflow in `SKILL.md`.
- Put core procedures and decision rules in the first reference file.
- Put option sets, examples, and specialized patterns in adjacent secondary references.
- Prefer operational guidance over lore summary.

## Layout Convention

Each skill should ideally follow this shape:

```text
skill-name/
├── SKILL.md
├── references/
│   ├── core-procedure.md
│   ├── examples.md
│   └── edge-cases.md
└── assets/
    └── template.md
```

Not every skill needs more than this, but this is the default.

## Validation

- Use `skills/evals/` for trigger and output-quality fixtures.
- Use `skills/scripts/` for repeatable validation helpers and suite-wide checks.
