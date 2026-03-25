# Examples

## Example Concept

- Name: Ash Chapel Warden
- Tier: 2
- Role: Standard
- Motives: guard relics, expose intruders, hold the line
- Signature feature: forces trespassers to stop or mark Stress when crossing a consecrated boundary

## Example Support Concept

- Name: Briar Cantor
- Tier: 1
- Role: Support
- Motives: entangle, protect sacred ground, drive out defilers
- Signature feature: marks Stress to overgrow an area and Restrain targets moving through it

## Example With Defaults

Prompt: "Make me a custom Daggerheart enemy for a haunted chapel."

If the user gives no tier or role and nothing else clarifies them, default to:

- Tier: 1
- Role: Standard

Then create a straightforward adversary first instead of inventing a boss, swarm, or specialist.

## Example Final Shape

- Name: Ashen Banner Captain
- Tier: 1
- Type: Leader
- Description: A disciplined battlefield officer in scorched scale armor, carrying a hooked saber and issuing clipped orders through smoke and chaos.
- Motives and tactics: hold the line, punish hesitation, direct allies, seize ground
- Difficulty: 14
- Thresholds: 7/13
- HP: 6
- Stress: 3
- ATK: +3
- Standard attack: Hooked Saber, Melee, 1d10+3 physical
- Experience: Commander +2, Battlefield Awareness +2
- Features:
  - Press Forward - Action: Spend 2 Fear to spotlight the Captain and up to 1d4 allies within Far range. Each spotlighted ally can immediately move within Close range.
  - On My Mark - Reaction: Countdown (5). When the Captain is spotlighted for the first time, activate the countdown. It ticks down when a PC makes an attack roll. When it triggers, up to two allies within Far range make a standard attack with advantage against the nearest target in range. If both attacks hit the same target, combine their damage.
  - Hold Formation - Reaction: When the Captain marks 1 or more HP, mark a Stress to reduce the damage by 1 HP.
