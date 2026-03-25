#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def to_jsonable_band(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, tuple):
        return [to_jsonable_band(item) for item in value]
    return value


def build_verification_properties(scenario: dict[str, Any]) -> dict[str, Any]:
    if scenario["suite"] != "adversary-creation":
        raise ValueError(f"Unsupported suite: {scenario['suite']}")

    expected_tier = int(scenario["expected_tier"])
    expected_role = str(scenario["expected_role"])
    ref_path = VALIDATOR_MODULE.REFS / f"tier-{expected_tier}-{expected_role}.md"
    band = VALIDATOR_MODULE.parse_safe_band(ref_path)

    return {
        "scenario_id": scenario["id"],
        "suite": scenario["suite"],
        "validator": "adversary-creation",
        "skill_access": {
            "skill_path": scenario["skill_path"],
            "references_dir": "daggerheart-adversary-creation/references",
        },
        "expected_role": expected_role,
        "expected_tier": expected_tier,
        "required_fields": REQUIRED_FIELDS,
        "feature_count": {
            "min": 1,
            "max": 3,
        },
        "safe_band": {
            "difficulty": to_jsonable_band(band.difficulty),
            "thresholds": to_jsonable_band(band.thresholds),
            "hp": to_jsonable_band(band.hp),
            "stress": to_jsonable_band(band.stress),
            "atk": to_jsonable_band(band.atk),
            "fixed_damage": to_jsonable_band(band.fixed_damage),
            "damage_avg": to_jsonable_band(band.damage_avg),
        },
        "role_specific_expectations": ROLE_EXPECTATIONS.get(expected_role, []),
        "judge_focus": [
            "Check that the output follows the required structure and field set.",
            "Check that the tier and role match the expected scenario.",
            "Check that numbers and features fit the stated role and battlefield job.",
            "Flag overloaded, generic, or weak feature design."
        ],
    }


def render_scenario(path: Path) -> tuple[Path, Path]:
    scenario = read_json(path)
    fixture_dir = FIXTURE_ROOT / scenario["id"]
    fixture_dir.mkdir(parents=True, exist_ok=True)

    request_path = fixture_dir / "user-request.txt"
    properties_path = fixture_dir / "verification-properties.json"

    request_path.write_text(scenario["prompt"].rstrip() + "\n")
    properties_path.write_text(json.dumps(build_verification_properties(scenario), indent=2) + "\n")
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
