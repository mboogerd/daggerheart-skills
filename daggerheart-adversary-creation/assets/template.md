# Adversary Stat Block Template

If tier or role is omitted and not inferable, default to:

- Tier: 1
- Type: Standard

Use this exact field order and formatting:

- Return plain markdown stat-block content only. Do not add YAML frontmatter, note metadata, tags, or enclosing prose.
- `Thresholds` must be numeric `A/B` or `None` for minions. Do not label them `Major/Severe`, `Guard/Tough`, or anything else in the final field value.
- `Standard attack` must use: `Attack Name, Range, Damage Type and Dice`
  Example: `Hooked Saber, Melee, 1d10+3 physical`
- `Features` must be followed by 1 to 3 indented bullet lines.
- Each feature line must use: `Feature Name - Passive|Action|Reaction: effect text`
- Do not collapse multiple features onto the `Features:` line.

- Name:
- Tier:
- Type:
- Description:
- Motives and tactics:
- Difficulty:
- Thresholds:
- HP:
- Stress:
- ATK:
- Standard attack:
- Experience:
- Features:
  - Signature Feature - Passive:
