# Core Procedure

Every adversary needs:

- Name
- Tier
- Type
- Short description
- Motives and tactics
- Difficulty
- Damage thresholds
- HP
- Stress
- Attack modifier
- Standard attack with range and damage
- Optional Experience
- 1 to 3 features

## Defaults

- Default tier: `1`
- Default role: `standard`

Use those defaults only when the user omitted them and the context does not strongly suggest a better answer.

## Ask Or Infer

- **Infer** when the fiction clearly implies the role or tier. A "boss monster for four level-6 PCs" is not ambiguous.
- **Ask** when the requested enemy could plausibly be built in meaningfully different ways and the choice would change the output. Example: "make me a bandit captain" could be Standard, Leader, Skulk, or Ranged depending on the encounter job.

## Creation Order

1. Decide the adversary's job in the encounter.
2. Choose the role.
3. Choose the tier.
4. Read the exact `tier-role` reference.
5. Pick motives and tactics before writing features.
6. Choose numeric values from the safe band in the matching file.
7. Write one signature feature, then add only what the role still needs.

## What Each Field Is For

- **Name:** the stat block identifier. Multiple story NPCs can use the same stat block.
- **Tier:** which level band the adversary is meant to challenge.
- **Type:** the adversary's role in conflict.
- **Description:** one line that tells the GM how to picture and present the enemy.
- **Motives and tactics:** the default answer to what the enemy tries to do when in doubt.
- **Difficulty:** target number for rolls against the adversary.
- **Thresholds / HP / Stress:** durability model.
- **Attack modifier and standard attack:** the baseline offensive action.
- **Experience:** optional bonus for specialized fictional competence.
- **Features:** the part that makes the enemy feel specific rather than generic.

## Hard Rules

- Do not pick numbers before the role.
- Do not hybridize multiple roles unless the user explicitly wants an unusual design.
- Do not make every stat high. Pick one or two standout stats and keep the rest near the role baseline.
- Do not add extra features just because the stat block looks short.
