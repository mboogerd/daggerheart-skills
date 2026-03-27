from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cross_eval_models import validate_verification_properties


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SkillTestSuite:
    name: str
    case_file: Path
    ci_suite_name: str


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ADVERSARY_VALIDATOR_MODULE = load_module(
    ROOT / "scripts" / "validate-adversary-creation.py",
    "validate_adversary_creation",
)
COMBAT_ENCOUNTER_VALIDATOR_MODULE = load_module(
    ROOT / "scripts" / "validate-combat-encounter-planning.py",
    "validate_combat_encounter_planning",
)

OUTPUT_CASE_SUITES: dict[str, SkillTestSuite] = {
    "adversary-creation": SkillTestSuite(
        name="adversary-creation",
        case_file=ROOT / "evals" / "adversary-creation.output-cases.json",
        ci_suite_name="adversary-creation-evals",
    ),
    "combat-encounter-planning": SkillTestSuite(
        name="combat-encounter-planning",
        case_file=ROOT / "evals" / "combat-encounter-planning.output-cases.json",
        ci_suite_name="combat-encounter-planning-evals",
    ),
}

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
        "Features must include Group Attack.",
    ],
    "horde": [
        "Features must include Horde (X).",
    ],
    "support": [
        "Support/control language should be obvious in the features.",
    ],
    "solo": [
        "Usually needs at least three features.",
        "Should show stronger action economy, reaction pressure, countdowns, or phases.",
    ],
}


def read_json(path: Path) -> Any:
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


def list_output_case_suites() -> list[SkillTestSuite]:
    return [OUTPUT_CASE_SUITES[name] for name in sorted(OUTPUT_CASE_SUITES)]


def get_output_case_suite(name: str) -> SkillTestSuite:
    try:
        return OUTPUT_CASE_SUITES[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported skill test suite: {name}") from exc


def load_output_cases(name: str) -> list[dict[str, Any]]:
    suite = get_output_case_suite(name)
    payload = read_json(suite.case_file)
    if not isinstance(payload, list):
        raise ValueError(f"Output case file for {name} must contain a JSON list.")
    return payload


def resolve_sample_output_path(sample_reference: str) -> Path:
    sample_path = Path(sample_reference)
    if sample_path.parts and sample_path.parts[0] == "skills":
        return ROOT / sample_path.relative_to("skills")
    return ROOT / sample_path


def validate_skill_output(suite_name: str, text: str, expectations: dict[str, Any]) -> tuple[list[str], list[str]]:
    if suite_name == "adversary-creation":
        return ADVERSARY_VALIDATOR_MODULE.validate_output(
            text,
            expected_tier=expectations.get("expected_tier"),
            expected_role=expectations.get("expected_role"),
        )
    if suite_name == "combat-encounter-planning":
        return COMBAT_ENCOUNTER_VALIDATOR_MODULE.validate_output(
            text,
            expectations,
        )
    raise ValueError(f"Unsupported skill test suite: {suite_name}")


def _build_adversary_creation_properties(scenario: dict[str, Any]) -> dict[str, Any]:
    expected_tier = int(scenario["expected_tier"])
    expected_role = str(scenario["expected_role"])
    ref_path = ADVERSARY_VALIDATOR_MODULE.REFS / f"tier-{expected_tier}-{expected_role}.md"
    band = ADVERSARY_VALIDATOR_MODULE.parse_safe_band(ref_path)

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
            "Flag overloaded, generic, or weak feature design.",
        ],
    })


def _build_combat_encounter_planning_properties(scenario: dict[str, Any]) -> dict[str, Any]:
    cases = load_output_cases("combat-encounter-planning")
    case_by_id = {item["id"]: item for item in cases}
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
            "For Role: minion, Count means the number of minion groups, where each group is equal to party size unless you explicitly state otherwise.",
            "Every roster slot must include Adversary requirements that a downstream sourcing skill could use.",
            "If you include Acquisition hint, only use prefer-existing or prefer-new.",
            "Spend the full Final budget exactly unless the scenario explicitly says otherwise.",
            "Keep the encounter at the orchestration layer rather than generating full downstream adversary stat blocks.",
            "Treat lookup versus creation as a downstream sourcing concern rather than the main purpose of this planner.",
            "Do not wrap the answer in code fences.",
            "Do not explain your reasoning.",
            "Do not modify repository files.",
        ],
        "expected_tier": int(scenario_case["expected_tier"]),
        "expected_party_size": int(scenario_case["expected_party_size"]),
        "expected_starting_budget": int(scenario_case["expected_starting_budget"]),
        "required_sections": scenario_case["required_sections"],
        "allowed_acquisition_hints": scenario_case.get("allowed_acquisition_hints", []),
        "judge_focus": [
            "Check that the encounter creates multiple player-facing pressures rather than a flat fight.",
            "Check that the plan gives clear adversary requirements for downstream sourcing without collapsing into full stat blocks.",
            "Check that the environment and escalation create meaningful scene pressure rather than decorative detail.",
            "Check that the roster roles feel purposeful and narratively coherent rather than arbitrary.",
            "Check that any acquisition hint is lightweight and does not dominate the planner output.",
        ],
    })


def build_verification_properties_for_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    suite_name = scenario["suite"]
    if suite_name == "adversary-creation":
        return _build_adversary_creation_properties(scenario)
    if suite_name == "combat-encounter-planning":
        return _build_combat_encounter_planning_properties(scenario)
    raise ValueError(f"Unsupported skill test suite: {suite_name}")
