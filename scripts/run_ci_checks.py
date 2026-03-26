#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from skill_test_suites import (
    list_output_case_suites,
    load_output_cases,
    resolve_sample_output_path,
    validate_skill_output,
)

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CaseResult:
    suite: str
    name: str
    failure: str | None = None
    details: str | None = None
    duration: float = 0.0


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


DESCRIPTION_MODULE = load_module(ROOT / "scripts" / "check-description-length.py", "check_description_length")


def check_skill_layout() -> list[CaseResult]:
    results: list[CaseResult] = []
    for skill_dir in sorted(ROOT.glob("daggerheart-*")):
        missing: list[str] = []
        if not (skill_dir / "SKILL.md").is_file():
            missing.append("SKILL.md")
        if not (skill_dir / "references").is_dir():
            missing.append("references/")
        if not (skill_dir / "assets").is_dir():
            missing.append("assets/")

        results.append(
            CaseResult(
                suite="skill-layout",
                name=skill_dir.name,
                failure=f"Missing required paths: {', '.join(missing)}" if missing else None,
                details=None if not missing else str(skill_dir),
            )
        )
    return results


def check_description_length() -> list[CaseResult]:
    results: list[CaseResult] = []
    for skill_file in sorted(ROOT.glob("daggerheart-*/SKILL.md")):
        description = DESCRIPTION_MODULE.extract_description(skill_file.read_text())
        if description is None:
            results.append(
                CaseResult(
                    suite="description-length",
                    name=skill_file.parent.name,
                    failure="Missing description in frontmatter",
                    details=str(skill_file),
                )
            )
            continue

        length = len(description)
        failure = None
        if length > 1024:
            failure = f"Description length {length} exceeds 1024 characters"

        results.append(
            CaseResult(
                suite="description-length",
                name=skill_file.parent.name,
                failure=failure,
                details=f"length={length}",
            )
        )
    return results


def check_skill_output_cases() -> list[CaseResult]:
    results: list[CaseResult] = []

    for suite in list_output_case_suites():
        for case in load_output_cases(suite.name):
            sample = case.get("sample_output")
            if not sample:
                continue

            sample_path = resolve_sample_output_path(sample)
            errors, warnings = validate_skill_output(
                suite.name,
                sample_path.read_text(),
                case,
            )

            details_parts = [f"sample={sample_path.relative_to(ROOT)}"]
            if warnings:
                details_parts.extend(f"warning: {warning}" for warning in warnings)

            results.append(
                CaseResult(
                    suite=suite.ci_suite_name,
                    name=case["id"],
                    failure="\n".join(errors) if errors else None,
                    details="\n".join(details_parts),
                )
            )
    return results


def time_results(results: list[CaseResult], fn) -> None:
    start = time.perf_counter()
    fn_results = fn()
    elapsed = time.perf_counter() - start
    per_case = elapsed / len(fn_results) if fn_results else 0.0
    for result in fn_results:
        result.duration = per_case
    results.extend(fn_results)


def write_junit_xml(results: list[CaseResult], path: Path) -> None:
    testsuites = ET.Element("testsuites")

    by_suite: dict[str, list[CaseResult]] = {}
    for result in results:
        by_suite.setdefault(result.suite, []).append(result)

    for suite_name, suite_results in sorted(by_suite.items()):
        failures = sum(1 for result in suite_results if result.failure)
        suite = ET.SubElement(
            testsuites,
            "testsuite",
            name=suite_name,
            tests=str(len(suite_results)),
            failures=str(failures),
            errors="0",
            skipped="0",
            time=f"{sum(result.duration for result in suite_results):.6f}",
        )
        for result in suite_results:
            case = ET.SubElement(
                suite,
                "testcase",
                classname=suite_name,
                name=result.name,
                time=f"{result.duration:.6f}",
            )
            if result.failure:
                failure = ET.SubElement(case, "failure", message=result.failure.splitlines()[0])
                failure.text = result.failure
            if result.details:
                system_out = ET.SubElement(case, "system-out")
                system_out.text = result.details

    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(testsuites).write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit-xml", type=Path, default=ROOT / "test-results" / "ci.junit.xml")
    args = parser.parse_args()

    results: list[CaseResult] = []
    time_results(results, check_skill_layout)
    time_results(results, check_description_length)
    time_results(results, check_skill_output_cases)

    write_junit_xml(results, args.junit_xml)

    failures = [result for result in results if result.failure]
    print(f"Recorded {len(results)} checks in {args.junit_xml}")
    for failure in failures:
        print(f"FAIL [{failure.suite}] {failure.name}")
        print(failure.failure)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
