from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _expect_type(value: Any, expected_type: type | tuple[type, ...], path: str) -> None:
    if not isinstance(value, expected_type):
        expected_name = (
            ", ".join(type_name.__name__ for type_name in expected_type)
            if isinstance(expected_type, tuple)
            else expected_type.__name__
        )
        raise ValueError(f"{path} must be of type {expected_name}")


def _expect_mapping(value: Any, path: str) -> dict[str, Any]:
    _expect_type(value, dict, path)
    return value


def _expect_list_of_strings(value: Any, path: str) -> list[str]:
    _expect_type(value, list, path)
    for index, item in enumerate(value):
        _expect_type(item, str, f"{path}[{index}]")
    return value


def _validate_bound(value: Any, path: str) -> dict[str, int | float] | None:
    if value is None:
        return None
    mapping = _expect_mapping(value, path)
    allowed_keys = {"lower_bound", "upper_bound"}
    unexpected_keys = set(mapping) - allowed_keys
    if unexpected_keys:
        raise ValueError(f"{path} contains unexpected keys: {sorted(unexpected_keys)}")
    if set(mapping) != allowed_keys:
        raise ValueError(f"{path} must contain lower_bound and upper_bound")
    _expect_type(mapping["lower_bound"], (int, float), f"{path}.lower_bound")
    _expect_type(mapping["upper_bound"], (int, float), f"{path}.upper_bound")
    return mapping


def _validate_threshold_bounds(value: Any, path: str) -> dict[str, dict[str, int | float]] | None:
    if value is None:
        return None
    mapping = _expect_mapping(value, path)
    allowed_keys = {"first_threshold", "second_threshold"}
    unexpected_keys = set(mapping) - allowed_keys
    if unexpected_keys:
        raise ValueError(f"{path} contains unexpected keys: {sorted(unexpected_keys)}")
    if set(mapping) != allowed_keys:
        raise ValueError(f"{path} must contain first_threshold and second_threshold")
    _validate_bound(mapping["first_threshold"], f"{path}.first_threshold")
    _validate_bound(mapping["second_threshold"], f"{path}.second_threshold")
    return mapping


def _validate_common_payload(payload: dict[str, Any]) -> None:
    required_keys = {
        "scenario_id",
        "suite",
        "validator",
        "skill_access",
        "judge_focus",
        "generation_requirements",
    }
    missing_keys = required_keys - set(payload)
    if missing_keys:
        raise ValueError(f"verification properties are missing keys: {sorted(missing_keys)}")

    _expect_type(payload["scenario_id"], str, "scenario_id")
    _expect_type(payload["suite"], str, "suite")
    _expect_type(payload["validator"], str, "validator")

    skill_access = _expect_mapping(payload["skill_access"], "skill_access")
    if set(skill_access) != {"skill_path", "references_dir", "template_path"}:
        raise ValueError("skill_access must contain exactly skill_path, references_dir, and template_path")
    _expect_type(skill_access["skill_path"], str, "skill_access.skill_path")
    _expect_type(skill_access["references_dir"], str, "skill_access.references_dir")
    _expect_type(skill_access["template_path"], str, "skill_access.template_path")

    _expect_list_of_strings(payload["judge_focus"], "judge_focus")
    _expect_list_of_strings(payload["generation_requirements"], "generation_requirements")


def _validate_adversary_creation_properties(payload: dict[str, Any]) -> dict[str, Any]:
    required_keys = {
        "scenario_id",
        "suite",
        "validator",
        "skill_access",
        "judge_focus",
        "generation_requirements",
        "expected_role",
        "expected_tier",
        "required_fields",
        "feature_count",
        "safe_band",
        "role_specific_expectations",
    }
    unexpected_keys = set(payload) - required_keys
    missing_keys = required_keys - set(payload)
    if missing_keys:
        raise ValueError(f"verification properties are missing keys: {sorted(missing_keys)}")
    if unexpected_keys:
        raise ValueError(f"verification properties contain unexpected keys: {sorted(unexpected_keys)}")

    _validate_common_payload(payload)

    _expect_type(payload["expected_role"], str, "expected_role")
    _expect_type(payload["expected_tier"], int, "expected_tier")
    if payload["expected_tier"] < 0:
        raise ValueError("expected_tier must be >= 0")

    _expect_list_of_strings(payload["required_fields"], "required_fields")
    _expect_list_of_strings(payload["role_specific_expectations"], "role_specific_expectations")

    feature_count = _expect_mapping(payload["feature_count"], "feature_count")
    if set(feature_count) != {"min", "max"}:
        raise ValueError("feature_count must contain exactly min and max")
    _expect_type(feature_count["min"], int, "feature_count.min")
    _expect_type(feature_count["max"], int, "feature_count.max")
    if feature_count["min"] < 0 or feature_count["max"] < 0:
        raise ValueError("feature_count.min and feature_count.max must be >= 0")

    safe_band = _expect_mapping(payload["safe_band"], "safe_band")
    expected_safe_band_keys = {
        "difficulty",
        "thresholds",
        "hp",
        "stress",
        "atk",
        "fixed_damage",
        "damage_avg",
    }
    if set(safe_band) != expected_safe_band_keys:
        raise ValueError("safe_band must contain exactly the expected numeric fields")
    _validate_bound(safe_band["difficulty"], "safe_band.difficulty")
    _validate_threshold_bounds(safe_band["thresholds"], "safe_band.thresholds")
    _validate_bound(safe_band["hp"], "safe_band.hp")
    _validate_bound(safe_band["stress"], "safe_band.stress")
    _validate_bound(safe_band["atk"], "safe_band.atk")
    _validate_bound(safe_band["fixed_damage"], "safe_band.fixed_damage")
    _validate_bound(safe_band["damage_avg"], "safe_band.damage_avg")

    return payload


def _validate_combat_encounter_planning_properties(payload: dict[str, Any]) -> dict[str, Any]:
    required_keys = {
        "scenario_id",
        "suite",
        "validator",
        "skill_access",
        "judge_focus",
        "generation_requirements",
        "expected_tier",
        "expected_party_size",
        "expected_starting_budget",
        "required_sections",
        "required_resolution_values",
    }
    optional_keys = {
        "allowed_resolution_values",
    }
    unexpected_keys = set(payload) - required_keys - optional_keys
    missing_keys = required_keys - set(payload)
    if missing_keys:
        raise ValueError(f"verification properties are missing keys: {sorted(missing_keys)}")
    if unexpected_keys:
        raise ValueError(f"verification properties contain unexpected keys: {sorted(unexpected_keys)}")

    _validate_common_payload(payload)

    _expect_type(payload["expected_tier"], int, "expected_tier")
    _expect_type(payload["expected_party_size"], int, "expected_party_size")
    _expect_type(payload["expected_starting_budget"], int, "expected_starting_budget")
    if payload["expected_tier"] < 0:
        raise ValueError("expected_tier must be >= 0")
    if payload["expected_party_size"] < 1:
        raise ValueError("expected_party_size must be >= 1")
    if payload["expected_starting_budget"] < 0:
        raise ValueError("expected_starting_budget must be >= 0")

    _expect_list_of_strings(payload["required_sections"], "required_sections")
    _expect_list_of_strings(payload["required_resolution_values"], "required_resolution_values")

    allowed_resolution_values = payload.get("allowed_resolution_values")
    if allowed_resolution_values is not None:
        _expect_list_of_strings(allowed_resolution_values, "allowed_resolution_values")

    return payload


def validate_verification_properties(payload: dict[str, Any]) -> dict[str, Any]:
    suite = payload.get("suite")
    if suite == "adversary-creation":
        return _validate_adversary_creation_properties(payload)
    if suite == "combat-encounter-planning":
        return _validate_combat_encounter_planning_properties(payload)
    raise ValueError(f"Unsupported suite: {suite}")


def load_verification_properties(path: Path) -> dict[str, Any]:
    return validate_verification_properties(json.loads(path.read_text()))
