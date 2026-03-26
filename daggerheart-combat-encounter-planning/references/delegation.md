# Delegation and Composition

Use this skill as the conductor, not the orchestra.

## Existing Skills

- `daggerheart-encounter-budgeting`: use when the request is mostly budget math.
- `daggerheart-adversary-selection`: use when the user needs role mix but not a full encounter brief.
- `daggerheart-environment-design`: use when the scene's main pressure comes from the location or event.
- `daggerheart-combat-objectives`: use when the fight lacks stakes, timers, or partial-victory structure.
- `daggerheart-adversary-creation`: use when a roster slot needs a new unnamed adversary.

## Planned Future Skills

The encounter planner should already support these handoff categories even before the skills exist:

- named adversary creation
- unnamed adversary lookup
- named adversary lookup

## Roster Sourcing Hints

The encounter planner should define the adversary requirements for each roster slot first.

If you include an acquisition preference, use one of these values:

- `prefer-existing`
- `prefer-new`

## Good Behavior

- Define role, count, scene job, and adversary requirements clearly enough that a downstream sourcing skill can act on them.
- Use `prefer-existing` when the concept clearly sounds reusable or already-established.
- Use `prefer-new` when the slot depends on a fresh bespoke concept.
- If a leader or support only works because of specific allies, make those dependencies explicit in the requirements and handoff notes.

## Bad Behavior

- Turning the encounter planner into a disguised adversary-generation step
- Returning completed stat blocks for multiple enemies instead of a plan
- Treating the environment as a flavor paragraph rather than a scene pressure
