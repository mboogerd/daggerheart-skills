---
name: daggerheart-adversary-creation
description: Use this skill when the user wants to create a custom Daggerheart adversary, including a new enemy role, motive, tactics, stat block concept, signature features, or a fresh foe rather than a simple reskin.
---

# Daggerheart Adversary Creation

Use this skill when the user needs a new enemy rather than a reskin.

## Workflow

1. Read `references/core-procedure.md`.
2. Determine the tier and role.
3. If the tier is omitted, default to tier 1.
4. If the role is omitted, default to Standard.
5. If the context makes tier or role materially ambiguous and the best answer is not inferable, ask one short follow-up question instead of guessing.
6. Read `references/role-recipes.md`.
7. Read the exact matching `references/tier-<tier>-<role>.md` file.
8. Read `references/feature-patterns.md` if the adversary needs stronger signature abilities.
9. Read `references/examples.md` for short custom-build models.
10. Read `references/edge-cases.md` if the design is overcomplicated, redundant, or missing a battlefield job.
11. Use `assets/template.md` for stat-block output.
12. Create the stat block concept first, then choose numbers from the matching tier-role reference.
13. Hand off to `daggerheart-adversary-scaling` only if the requested concept must deviate far from the normal tier-role envelope.

## Output

- Name
- Tier
- Role
- Description
- Motives and tactics
- Stat-line guidance
- 1 to 3 features

## Tier-Role Files

Use these role names exactly in file lookups:

- `standard`
- `bruiser`
- `horde`
- `leader`
- `minion`
- `ranged`
- `skulk`
- `social`
- `solo`
- `support`
