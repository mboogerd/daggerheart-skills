#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from skill_test_suites import build_verification_properties_for_scenario


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO = ROOT / "evals" / "cross-eval" / "scenarios" / "tier1_leader_smoke.json"
FIXTURE_ROOT = ROOT / "evals" / "cross-eval" / "fixtures"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def render_scenario(path: Path) -> tuple[Path, Path]:
    scenario = read_json(path)
    fixture_dir = FIXTURE_ROOT / scenario["id"]
    fixture_dir.mkdir(parents=True, exist_ok=True)

    request_path = fixture_dir / "user-request.txt"
    properties_path = fixture_dir / "verification-properties.json"

    request_path.write_text(scenario["prompt"].rstrip() + "\n")
    properties = build_verification_properties_for_scenario(scenario)
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
