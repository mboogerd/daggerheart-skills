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

## Roster Resolution Values

Use one of these values for each roster slot:

- `lookup-existing-unnamed`
- `lookup-existing-named`
- `adapt-existing`
- `create-unnamed`
- `create-named`

## Good Behavior

- Prefer lookup or adaptation when the concept clearly sounds reusable or already-established.
- Prefer unnamed creation for faction troops, generic specialists, and first-pass customs.
- Prefer named creation for villains, lieutenants, rivals, and recurring bosses.
- If a leader or support only works because of specific allies, make those dependencies explicit in the handoff notes.

## Bad Behavior

- Filling every slot with `create-unnamed`
- Returning completed stat blocks for multiple enemies instead of a plan
- Treating the environment as a flavor paragraph rather than a scene pressure
