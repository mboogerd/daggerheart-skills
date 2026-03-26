#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from cross_eval_models import validate_verification_properties


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO = ROOT / "evals" / "cross-eval" / "scenarios" / "tier1_leader_smoke.json"
FIXTURE_ROOT = ROOT / "evals" / "cross-eval" / "fixtures"

REQUIRED_FIELDS = [
    "name",
    "tier",
    "type",
    "description",
    "motives and tactics",
    "difficulty",
    "thresholds",
    "hp",
    "stress",
    "atk",
    "standard attack",
    "features",
]

ROLE_EXPECTATIONS = {
    "leader": [
        "Include at least one ally-facing, command, rally, spotlight, reinforcement, or summon feature."
    ],
    "minion": [
        "Thresholds must be None.",
        "HP must be 1.",
        "Stress must be 1.",
        "Features must include Minion (X).",
        "Features must include Group Attack."
    ],
    "horde": [
        "Features must include Horde (X)."
    ],
    "support": [
        "Support/control language should be obvious in the features."
    ],
    "solo": [
        "Usually needs at least three features.",
        "Should show stronger action economy, reaction pressure, countdowns, or phases."
    ],
}


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR_MODULE = load_module(ROOT / "scripts" / "validate-adversary-creation.py", "validate_adversary_creation")
COMBAT_VALIDATOR_MODULE = load_module(
    ROOT / "scripts" / "validate-combat-encounter-planning.py",
    "validate_combat_encounter_planning",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def explicit_bounds(bounds: tuple[int, int] | tuple[float, float] | None) -> dict[str, int | float] | None:
    if bounds is None:
        return None
    lower_bound, upper_bound = bounds
    return {
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
    }


def explicit_threshold_bounds(
    thresholds: tuple[tuple[int, int], tuple[int, int]] | None,
) -> dict[str, dict[str, int]] | None:
    if thresholds is None:
        return None
    first_threshold, second_threshold = thresholds
    return {
        "first_threshold": {
            "lower_bound": first_threshold[0],
            "upper_bound": first_threshold[1],
        },
        "second_threshold": {
            "lower_bound": second_threshold[0],
            "upper_bound": second_threshold[1],
        },
    }


def build_adversary_creation_properties(scenario: dict[str, Any]) -> dict[str, Any]:
    expected_tier = int(scenario["expected_tier"])
    expected_role = str(scenario["expected_role"])
    ref_path = VALIDATOR_MODULE.REFS / f"tier-{expected_tier}-{expected_role}.md"
    band = VALIDATOR_MODULE.parse_safe_band(ref_path)

    return validate_verification_properties({
        "scenario_id": scenario["id"],
        "suite": scenario["suite"],
        "validator": "adversary-creation",
        "skill_access": {
            "skill_path": scenario["skill_path"],
            "references_dir": "daggerheart-adversary-creation/references",
            "template_path": "daggerheart-adversary-creation/assets/template.md",
        },
        "generation_requirements": [
            "Return only the final stat block body.",
            "Do not output YAML frontmatter, tags, metadata fields, or explanatory prose.",
            "Do not wrap the answer in code fences.",
            "Do not explain your reasoning.",
            "Do not modify repository files.",
        ],
        "expected_role": expected_role,
        "expected_tier": expected_tier,
        "required_fields": REQUIRED_FIELDS,
        "feature_count": {
            "min": 1,
            "max": 3,
        },
        "safe_band": {
            "difficulty": explicit_bounds(band.difficulty),
            "thresholds": explicit_threshold_bounds(band.thresholds),
            "hp": explicit_bounds(band.hp),
            "stress": explicit_bounds(band.stress),
            "atk": explicit_bounds(band.atk),
            "fixed_damage": explicit_bounds(band.fixed_damage),
            "damage_avg": explicit_bounds(band.damage_avg),
        },
        "role_specific_expectations": ROLE_EXPECTATIONS.get(expected_role, []),
        "judge_focus": [
            "Check that the output follows the required structure and field set.",
            "Check that the tier and role match the expected scenario.",
            "Check that numbers and features fit the stated role and battlefield job.",
            "Flag overloaded, generic, or weak feature design."
        ],
    })


def build_combat_encounter_planning_properties(scenario: dict[str, Any]) -> dict[str, Any]:
    case = COMBAT_VALIDATOR_MODULE.read_json(ROOT / "evals" / "combat-encounter-planning.output-cases.json")
    case_by_id = {item["id"]: item for item in case}
    scenario_case = case_by_id.get(scenario["id"])
    if scenario_case is None:
        raise ValueError(f"No combat encounter planning case found for scenario id {scenario['id']}")

    return validate_verification_properties({
        "scenario_id": scenario["id"],
        "suite": scenario["suite"],
        "validator": "combat-encounter-planning",
        "skill_access": {
            "skill_path": scenario["skill_path"],
            "references_dir": "daggerheart-combat-encounter-planning/references",
            "template_path": "daggerheart-combat-encounter-planning/assets/template.md",
        },
        "generation_requirements": [
            "Return only the completed encounter plan.",
            "Use the exact section headings and bullet-oriented structure from the template.",
            "Use numeric digits for Tier, Party size, Starting budget, Final budget, and each roster Points value.",
            "Every roster slot must include Count as an integer quantity.",
            "Use legal role costs only: minion/social/support=1, horde/ranged/skulk/standard=2, leader=3, bruiser=4, solo=5.",
            "Use Points for the total spend of that roster slot: Count multiplied by the role cost.",
            "Keep the encounter at the orchestration layer rather than generating full downstream adversary stat blocks.",
            "Make roster resolutions explicit.",
            "Do not wrap the answer in code fences.",
            "Do not explain your reasoning.",
            "Do not modify repository files.",
        ],
        "expected_tier": int(scenario_case["expected_tier"]),
        "expected_party_size": int(scenario_case["expected_party_size"]),
        "expected_starting_budget": int(scenario_case["expected_starting_budget"]),
        "required_sections": scenario_case["required_sections"],
        "required_resolution_values": scenario_case["required_resolution_values"],
        "allowed_resolution_values": list(COMBAT_VALIDATOR_MODULE.ALLOWED_RESOLUTION_VALUES),
        "judge_focus": [
            "Check that the output follows the required encounter-plan structure.",
            "Check that the budget math and role costs are plausible for the stated party and tier.",
            "Check that the encounter creates multiple player-facing pressures rather than a flat fight.",
            "Check that the plan delegates lookup, adaptation, and creation work explicitly instead of collapsing all downstream work inline.",
        ],
    })


def build_verification_properties(scenario: dict[str, Any]) -> dict[str, Any]:
    if scenario["suite"] == "adversary-creation":
        return build_adversary_creation_properties(scenario)
    if scenario["suite"] == "combat-encounter-planning":
        return build_combat_encounter_planning_properties(scenario)
    raise ValueError(f"Unsupported suite: {scenario['suite']}")


def render_scenario(path: Path) -> tuple[Path, Path]:
    scenario = read_json(path)
    fixture_dir = FIXTURE_ROOT / scenario["id"]
    fixture_dir.mkdir(parents=True, exist_ok=True)

    request_path = fixture_dir / "user-request.txt"
    properties_path = fixture_dir / "verification-properties.json"

    request_path.write_text(scenario["prompt"].rstrip() + "\n")
    properties = build_verification_properties(scenario)
    properties_path.write_text(json.dumps(properties, indent=2) + "\n")
    return request_path, properties_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenarios", nargs="*", type=Path)
    args = parser.parse_args()

    scenarios = args.scenarios or [DEFAULT_SCENARIO]
    for scenario_path in scenarios:
        request_path, properties_path = render_scenario(scenario_path)
        print(request_path)
        print(properties_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
