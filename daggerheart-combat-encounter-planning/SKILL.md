---
name: daggerheart-combat-encounter-planning
description: Use this skill when the user wants to plan a Daggerheart combat encounter end to end, including narrative function, battle-point budget, role mix, environment pressure, escalation, and which pieces should be looked up, adapted, or created by downstream skills.
---

# Daggerheart Combat Encounter Planning

Use this skill when the user needs a whole combat encounter plan rather than a single adversary, budget calculation, or scene fragment.

## Workflow

1. Read `references/core-procedure.md`.
2. Read `references/delegation.md`.
3. Read `references/encounter-structure.md`.
4. Read `references/examples.md` for compact encounter-plan models.
5. Read `references/edge-cases.md` if the encounter risks becoming flat, overlong, overcomplicated, or disconnected from the story.
6. Use `assets/template.md` for output.
7. Define the encounter's narrative function before choosing enemies.
8. Compute the starting battle-point budget and adjustments.
9. Choose a role mix that creates more than one player-facing pressure.
10. Add environment pressure or explain why the environment is intentionally light.
11. Add escalation, countdowns, or partial-victory conditions if the scene needs them.
12. For each roster slot, decide whether it should be:
    - looked up from an existing adversary source
    - adapted from an existing adversary
    - created as a new unnamed adversary
    - created as a new named adversary
    Include an explicit `Count` for the slot and use `Points` for the total spend of that slot.
13. Hand off creation work instead of inventing finished downstream assets inline.

## Delegation

- Use `daggerheart-encounter-budgeting` if the user only wants battle-point math.
- Use `daggerheart-adversary-selection` if the user only needs role composition.
- Use `daggerheart-environment-design` if the scene pressure is mostly environmental.
- Use `daggerheart-combat-objectives` if the fight mainly needs better stakes or win conditions.
- Use `daggerheart-adversary-creation` when a roster slot calls for a new unnamed adversary.
- Plan for future collaboration with named-adversary creation and adversary-lookup skills when the encounter should reuse or elevate existing foes.

## Output

- Encounter premise
- Party assumptions
- Narrative function
- Enemy motives
- Battle-point budget
- Encounter roster plan
- Environment plan
- Escalation plan
- Victory and failure states
- Dependency handoffs

Always keep the encounter planner at the orchestration layer. Do not silently replace downstream skill work with improvised full stat blocks.
