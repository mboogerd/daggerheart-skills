#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "daggerheart-adversary-creation" / "references"

ROLE_NAMES = {
    "standard",
    "bruiser",
    "horde",
    "leader",
    "minion",
    "ranged",
    "skulk",
    "social",
    "solo",
    "support",
}


@dataclass
class ReferenceBand:
    difficulty: tuple[int, int]
    thresholds: tuple[tuple[int, int], tuple[int, int]] | None
    hp: tuple[int, int]
    stress: tuple[int, int]
    atk: tuple[int, int]
    fixed_damage: tuple[int, int] | None
    damage_avg: tuple[float, float] | None


def normalize_role(value: str) -> str:
    value = value.strip().lower()
    return value


def average_damage(expr: str) -> float | None:
    expr = expr.strip()
    m = re.fullmatch(r"(\d+)d(\d+)\+(\d+)", expr)
    if m:
        n, d, bonus = map(int, m.groups())
        return n * (d + 1) / 2 + bonus
    m = re.fullmatch(r"(\d+)", expr)
    if m:
        return float(m.group(1))
    return None


def parse_range(text: str, signed: bool = False) -> tuple[int, int]:
    sign = r"[+-]?" if signed else r""
    text = text.strip().replace("–", "-")
    m = re.fullmatch(rf"({sign}\d+)", text)
    if m:
        value = int(m.group(1))
        return value, value
    m = re.fullmatch(rf"({sign}\d+)\s*(?:to|-)\s*({sign}\d+)", text)
    if not m:
        raise ValueError(f"cannot parse range: {text}")
    return int(m.group(1)), int(m.group(2))


def parse_safe_band(path: Path) -> ReferenceBand:
    text = path.read_text()
    line = next((ln for ln in text.splitlines() if ln.startswith("- Safe band: ")), None)
    if not line:
        raise ValueError(f"missing safe band in {path}")
    payload = line.removeprefix("- Safe band: ").strip()

    parts = [part.strip() for part in payload.split("; ")]
    fields: dict[str, str] = {}
    for part in parts:
        lower = part.lower()
        for key in ["difficulty", "thresholds", "hp", "stress", "atk", "fixed damage", "damage"]:
            if lower.startswith(key):
                fields[key] = part[len(key):].strip()
                break

    thresholds_text = fields.get("thresholds")
    thresholds = None
    if thresholds_text and thresholds_text.lower() != "none":
        lo, hi = thresholds_text.split(" to ", 1)
        lo_a, lo_b = [int(x) for x in lo.split("/")]
        hi_a, hi_b = [int(x) for x in hi.split("/")]
        thresholds = ((lo_a, hi_a), (lo_b, hi_b))

    fixed_damage = None
    damage_avg = None
    if "fixed damage" in fields:
        fixed_damage = parse_range(fields["fixed damage"])
    elif "damage" in fields:
        lo, hi = fields["damage"].split(" to ", 1)
        lo_avg = average_damage(lo)
        hi_avg = average_damage(hi)
        if lo_avg is None or hi_avg is None:
            raise ValueError(f"cannot parse damage range in {path}")
        damage_avg = (lo_avg, hi_avg)

    return ReferenceBand(
        difficulty=parse_range(fields["difficulty"]),
        thresholds=thresholds,
        hp=parse_range(fields["hp"]),
        stress=parse_range(fields["stress"]),
        atk=parse_range(fields["atk"], signed=True),
        fixed_damage=fixed_damage,
        damage_avg=damage_avg,
    )


def parse_output(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    features: list[str] = []
    in_features = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "name" not in result and ":" not in line and not in_features:
            heading = None
            if line.startswith("#"):
                heading = line.lstrip("#").strip()
            elif line.startswith("**") and line.endswith("**") and len(line) > 4:
                heading = line[2:-2].strip()
            if heading:
                result["name"] = heading
                continue
        if line.startswith("- Features:") or line.startswith("Features:"):
            in_features = True
            result["features"] = features
            continue
        if in_features:
            if line.startswith("- ") or line.startswith("* "):
                features.append(line[2:].strip())
                continue
            if re.match(r"^\d+\.", line):
                features.append(re.sub(r"^\d+\.\s*", "", line))
                continue
        m = re.match(r"^(?:[-*]\s*)?([^:]+):\s*(.+)$", line)
        if m:
            key = m.group(1).strip().lower()
            result[key] = m.group(2).strip()
            continue
    return result


def parse_attack_damage(attack: str) -> float | None:
    m = re.search(r"(\d+d\d+\+\d+|\d+)\s+[A-Za-z]+$", attack)
    if not m:
        return None
    return average_damage(m.group(1))


def parse_int_field(data: dict[str, Any], key: str) -> int:
    return int(str(data[key]).strip().lstrip("+"))


def validate_role_specific(role: str, data: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    features = [f.lower() for f in data.get("features", [])]
    joined = " ".join(features)

    if role == "minion":
        if str(data.get("thresholds", "")).lower() != "none":
            errors.append("Minion must use `Thresholds: None`.")
        if str(data.get("hp", "")).strip() != "1":
            errors.append("Minion must use `HP: 1`.")
        if str(data.get("stress", "")).strip() != "1":
            errors.append("Minion must use `Stress: 1`.")
        if "minion (" not in joined:
            errors.append("Minion is missing `Minion (X)` feature.")
        if "group attack" not in joined:
            errors.append("Minion is missing `Group Attack` feature.")
    elif role == "horde":
        if "horde (" not in joined:
            errors.append("Horde is missing `Horde (X)` feature.")
    elif role == "leader":
        if not any(word in joined for word in ["ally", "allies", "spotlight", "reinforcement", "summon", "command", "rally"]):
            errors.append("Leader needs at least one ally-facing or command feature.")
    elif role == "support":
        if not any(word in joined for word in ["ally", "protect", "restrain", "vulnerable", "condition", "clear", "heal", "support"]):
            warnings.append("Support does not clearly show support/control language.")
    elif role == "solo":
        if len(features) < 3:
            warnings.append("Solo usually wants at least three features.")
        if not any(word in joined for word in ["relentless", "countdown", "reaction", "phase"]):
            warnings.append("Solo may need stronger action-economy or reaction pressure.")


def validate_output(text: str, expected_tier: int | None = None, expected_role: str | None = None) -> tuple[list[str], list[str]]:
    data = parse_output(text)
    errors: list[str] = []
    warnings: list[str] = []

    required = [
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
    for key in required:
        if key not in data:
            errors.append(f"Missing required field: {key}")

    if errors:
        return errors, warnings

    try:
        tier = int(str(data["tier"]).strip())
    except ValueError:
        errors.append("Tier must be an integer 1-4.")
        return errors, warnings

    role = normalize_role(str(data["type"]))
    if role not in ROLE_NAMES:
        errors.append(f"Unknown role/type: {data['type']}")
        return errors, warnings

    if expected_tier is not None and tier != expected_tier:
        errors.append(f"Expected tier {expected_tier}, got {tier}.")
    if expected_role is not None and role != expected_role:
        errors.append(f"Expected role {expected_role}, got {role}.")

    ref_path = REFS / f"tier-{tier}-{role}.md"
    if not ref_path.exists():
        errors.append(f"Missing reference file: {ref_path.name}")
        return errors, warnings

    band = parse_safe_band(ref_path)

    difficulty = parse_int_field(data, "difficulty")
    hp = parse_int_field(data, "hp")
    stress = parse_int_field(data, "stress")
    atk = parse_int_field(data, "atk")

    if not (band.difficulty[0] <= difficulty <= band.difficulty[1]):
        errors.append(f"Difficulty {difficulty} outside safe band {band.difficulty}.")
    if not (band.hp[0] <= hp <= band.hp[1]):
        errors.append(f"HP {hp} outside safe band {band.hp}.")
    if not (band.stress[0] <= stress <= band.stress[1]):
        errors.append(f"Stress {stress} outside safe band {band.stress}.")
    if not (band.atk[0] <= atk <= band.atk[1]):
        errors.append(f"ATK {atk} outside safe band {band.atk}.")

    thresholds_text = str(data["thresholds"]).strip()
    if band.thresholds is None:
        if thresholds_text.lower() != "none":
            errors.append("Thresholds should be `None` for this role/tier.")
    else:
        try:
            first, second = [int(x) for x in thresholds_text.split("/")]
        except Exception:
            errors.append(f"Thresholds must be `A/B`, got `{thresholds_text}`.")
        else:
            first_band, second_band = band.thresholds
            if not (first_band[0] <= first <= first_band[1]):
                errors.append(f"First threshold {first} outside safe band {first_band}.")
            if not (second_band[0] <= second <= second_band[1]):
                errors.append(f"Second threshold {second} outside safe band {second_band}.")

    damage_avg = parse_attack_damage(str(data["standard attack"]))
    if damage_avg is None:
        warnings.append("Could not parse standard attack damage expression.")
    elif band.fixed_damage is not None:
        if float(band.fixed_damage[0]) <= damage_avg <= float(band.fixed_damage[1]):
            pass
        else:
            errors.append(f"Fixed damage average {damage_avg:g} outside safe band {band.fixed_damage}.")
    elif band.damage_avg is not None:
        lo, hi = band.damage_avg
        if not (lo <= damage_avg <= hi):
            errors.append(f"Damage average {damage_avg:.1f} outside safe band ({lo:.1f}, {hi:.1f}).")

    features = data.get("features", [])
    if not isinstance(features, list) or not (1 <= len(features) <= 3):
        errors.append("Features must contain between 1 and 3 entries.")

    validate_role_specific(role, data, errors, warnings)
    return errors, warnings


def validate_case_file(path: Path) -> int:
    payload = json.loads(path.read_text())
    failures = 0
    for case in payload:
        sample = case.get("sample_output")
        if not sample:
            continue
        sample_path = ROOT.parent / sample if not Path(sample).is_absolute() else Path(sample)
        errors, warnings = validate_output(
            sample_path.read_text(),
            expected_tier=case.get("expected_tier"),
            expected_role=case.get("expected_role"),
        )
        status = "PASS" if not errors else "FAIL"
        print(f"{status} {case['id']}")
        for msg in errors:
            print(f"  error: {msg}")
        for msg in warnings:
            print(f"  warn:  {msg}")
        if errors:
            failures += 1
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", help="Markdown output files to validate.")
    parser.add_argument("--expected-tier", type=int)
    parser.add_argument("--expected-role")
    parser.add_argument("--case-file", type=Path, help="JSON case file with sample_output entries.")
    args = parser.parse_args()

    failures = 0

    if args.case_file:
        failures += validate_case_file(args.case_file)

    for raw_path in args.paths:
        path = Path(raw_path)
        errors, warnings = validate_output(
            path.read_text(),
            expected_tier=args.expected_tier,
            expected_role=args.expected_role,
        )
        status = "PASS" if not errors else "FAIL"
        print(f"{status} {path}")
        for msg in errors:
            print(f"  error: {msg}")
        for msg in warnings:
            print(f"  warn:  {msg}")
        if errors:
            failures += 1

    if not args.case_file and not args.paths:
        parser.error("Provide at least one path or --case-file.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
