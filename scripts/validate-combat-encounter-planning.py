#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

SECTION_HEADERS = [
    "Encounter Premise",
    "Party Assumptions",
    "Narrative Function",
    "Enemy Motives",
    "Battle-Point Budget",
    "Encounter Roster Plan",
    "Environment Plan",
    "Escalation Plan",
    "Victory and Failure States",
    "Dependency Handoffs",
]

ALLOWED_ROLES = {
    "standard",
    "bruiser",
    "leader",
    "support",
    "ranged",
    "skulk",
    "horde",
    "minion",
    "social",
    "solo",
}

ALLOWED_RESOLUTION_VALUES = {
    "lookup-existing-unnamed",
    "lookup-existing-named",
    "adapt-existing",
    "create-unnamed",
    "create-named",
}

ROLE_POINT_COSTS = {
    "minion": 1,
    "social": 1,
    "support": 1,
    "horde": 2,
    "ranged": 2,
    "skulk": 2,
    "standard": 2,
    "leader": 3,
    "bruiser": 4,
    "solo": 5,
}

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def read_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def parse_int(value: str) -> int | None:
    match = re.search(r"-?\d+", value)
    if not match:
        normalized = value.strip().lower().replace("-", " ")
        for token in normalized.split():
            if token in NUMBER_WORDS:
                return NUMBER_WORDS[token]
        return None
    return int(match.group(0))


def parse_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections[current_section] = []
            continue
        if current_section is not None:
            sections[current_section].append(line)
    return sections


def parse_key_values(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^- ([^:]+):\s*(.*)$", stripped)
        if match:
            result[match.group(1).strip().lower()] = match.group(2).strip()
    return result


def parse_roster(lines: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        slot_match = re.match(r"^- Slot:\s*(.*)$", stripped)
        if slot_match:
            if current:
                entries.append(current)
            current = {"slot": slot_match.group(1).strip()}
            continue
        field_match = re.match(r"^([^:]+):\s*(.*)$", stripped)
        if field_match and current is not None:
            current[field_match.group(1).strip().lower()] = field_match.group(2).strip()
    if current:
        entries.append(current)
    return entries


def validate_output(text: str, case: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    case = case or {}
    errors: list[str] = []
    warnings: list[str] = []
    sections = parse_sections(text)

    required_sections = case.get("required_sections", SECTION_HEADERS)
    for section in required_sections:
        if section not in sections:
            errors.append(f"Missing required section: {section}")

    if errors:
        return errors, warnings

    premise = parse_key_values(sections["Encounter Premise"])
    assumptions = parse_key_values(sections["Party Assumptions"])
    budget = parse_key_values(sections["Battle-Point Budget"])
    environment = parse_key_values(sections["Environment Plan"])
    escalation = parse_key_values(sections["Escalation Plan"])
    victory = parse_key_values(sections["Victory and Failure States"])
    handoffs = parse_key_values(sections["Dependency Handoffs"])
    roster_entries = parse_roster(sections["Encounter Roster Plan"])

    expected_tier = case.get("expected_tier")
    if expected_tier is not None:
        tier = parse_int(premise.get("tier", ""))
        if tier is None:
            errors.append("Encounter Premise must include an integer tier.")
        elif tier != expected_tier:
            errors.append(f"Expected tier {expected_tier}, got {tier}.")

    expected_party_size = case.get("expected_party_size")
    if expected_party_size is not None:
        party_size = parse_int(assumptions.get("party size", ""))
        if party_size is None:
            errors.append("Party Assumptions must include an integer party size.")
        elif party_size != expected_party_size:
            errors.append(f"Expected party size {expected_party_size}, got {party_size}.")

    expected_starting_budget = case.get("expected_starting_budget")
    if expected_starting_budget is not None:
        starting_budget = parse_int(budget.get("starting budget", ""))
        if starting_budget is None:
            errors.append("Battle-Point Budget must include a numeric starting budget.")
        elif starting_budget != expected_starting_budget:
            errors.append(f"Expected starting budget {expected_starting_budget}, got {starting_budget}.")

    final_budget = parse_int(budget.get("final budget", ""))
    if final_budget is None:
        errors.append("Battle-Point Budget must include a numeric final budget.")

    if not roster_entries:
        errors.append("Encounter Roster Plan must include at least one roster slot.")

    total_points = 0
    roles_present: list[str] = []
    resolution_values_present: list[str] = []
    for index, entry in enumerate(roster_entries, start=1):
        count = parse_int(entry.get("count", ""))
        if count is None:
            errors.append(f"Roster slot {index} is missing numeric Count.")
            count = 1
        elif count < 1:
            errors.append(f"Roster slot {index} must have Count 1 or greater.")

        role = entry.get("role", "").strip().lower()
        if not role:
            errors.append(f"Roster slot {index} is missing Role.")
            continue
        if role not in ALLOWED_ROLES:
            errors.append(f"Roster slot {index} uses unknown role `{role}`.")
            continue
        roles_present.append(role)

        points = parse_int(entry.get("points", ""))
        if points is None:
            errors.append(f"Roster slot {index} is missing numeric Points.")
        else:
            total_points += points
            expected_cost = ROLE_POINT_COSTS[role] * count
            if points != expected_cost:
                if role == "minion":
                    errors.append(
                        f"Roster slot {index} has {points} points, but role `minion` should cost {expected_cost}. "
                        "For minions, Count is the number of party-sized minion groups."
                    )
                else:
                    errors.append(f"Roster slot {index} has {points} points, but role `{role}` should cost {expected_cost}.")

        resolution = entry.get("resolution", "").strip()
        if not resolution:
            errors.append(f"Roster slot {index} is missing Resolution.")
        elif resolution not in ALLOWED_RESOLUTION_VALUES:
            errors.append(f"Roster slot {index} uses unsupported resolution `{resolution}`.")
        else:
            resolution_values_present.append(resolution)

        if not entry.get("scene job", "").strip():
            warnings.append(f"Roster slot {index} should explain its scene job more clearly.")

    require_full_budget_use = case.get("require_full_budget_use", True)
    if final_budget is not None:
        if require_full_budget_use and total_points != final_budget:
            errors.append(f"Roster plan spends {total_points} points against a final budget of {final_budget}.")
        elif total_points > final_budget:
            errors.append(f"Roster plan spends {total_points} points against a final budget of {final_budget}.")

    allowed_resolution_values = set(case.get("allowed_resolution_values", []))
    if allowed_resolution_values:
        unexpected = set(resolution_values_present) - allowed_resolution_values
        if unexpected:
            errors.append(f"Encounter uses resolution values outside the case allowance: {sorted(unexpected)}")

    required_resolution_values = set(case.get("required_resolution_values", []))
    if required_resolution_values:
        missing = required_resolution_values - set(resolution_values_present)
        if missing:
            errors.append(f"Encounter does not demonstrate all required resolution types: {sorted(missing)}")

    if "leader" in roles_present and len(roster_entries) < 2:
        errors.append("Leader encounters should include meaningful allies or support structure.")

    if "solo" in roles_present:
        active_pressure = environment.get("active pressure", "").strip().lower()
        countdown = escalation.get("countdown or trigger", "").strip().lower()
        what_changes = escalation.get("what changes when it advances", "").strip().lower()
        has_supporting_scene_pressure = bool(active_pressure) or bool(countdown) or bool(what_changes)
        if not has_supporting_scene_pressure:
            errors.append("Solo encounters need explicit environment or escalation support.")

    environment_type = environment.get("environment type", "").strip()
    active_pressure = environment.get("active pressure", "").strip()
    if not environment_type:
        errors.append("Environment Plan must include an environment type.")
    if not active_pressure:
        errors.append("Environment Plan must include active pressure.")

    if not victory.get("full victory", "").strip():
        errors.append("Victory and Failure States must include full victory.")
    if not victory.get("partial victory", "").strip():
        errors.append("Victory and Failure States must include partial victory.")
    if not victory.get("cost of delay or failure", "").strip():
        errors.append("Victory and Failure States must include cost of delay or failure.")

    required_handoffs = [
        "ready for lookup",
        "ready for adaptation",
        "ready for unnamed adversary creation",
        "ready for named adversary creation",
    ]
    for key in required_handoffs:
        if key not in handoffs:
            errors.append(f"Dependency Handoffs must include `{key}`.")

    return errors, warnings


def validate_case_file(path: Path) -> int:
    payload = read_json(path)
    overall_errors = 0
    for case in payload:
        sample = case.get("sample_output")
        if not sample:
            continue
        sample_path = ROOT / Path(sample).relative_to("skills")
        errors, warnings = validate_output(sample_path.read_text(), case)
        if errors or warnings:
            print(f"[{case['id']}] sample={sample_path.relative_to(ROOT)}")
            for error in errors:
                print(f"ERROR: {error}")
            for warning in warnings:
                print(f"WARNING: {warning}")
        if errors:
            overall_errors += 1
    return 1 if overall_errors else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown_file", nargs="?", type=Path)
    parser.add_argument("--case-file", type=Path)
    parser.add_argument("--expected-tier", type=int)
    parser.add_argument("--expected-party-size", type=int)
    parser.add_argument("--expected-starting-budget", type=int)
    args = parser.parse_args()

    if args.case_file:
        return validate_case_file(args.case_file)
    if not args.markdown_file:
        parser.error("Provide a markdown file or --case-file.")

    case = {
        "expected_tier": args.expected_tier,
        "expected_party_size": args.expected_party_size,
        "expected_starting_budget": args.expected_starting_budget,
    }
    errors, warnings = validate_output(args.markdown_file.read_text(), case)
    for error in errors:
        print(f"ERROR: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
