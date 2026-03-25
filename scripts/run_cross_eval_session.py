#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO = ROOT / "evals" / "cross-eval" / "scenarios" / "tier1_leader_smoke.json"
DEFAULT_OUTPUT_ROOT = ROOT / "cross-eval"
DEFAULT_JUNIT_XML = ROOT / "test-results" / "cross-eval.junit.xml"
SCHEMA_PATH = ROOT / "evals" / "cross-eval" / "judge.schema.json"


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR_MODULE = load_module(ROOT / "scripts" / "validate-adversary-creation.py", "validate_adversary_creation")


@dataclass
class CommandResult:
    ok: bool
    returncode: int
    duration: float
    stdout_path: Path
    stderr_path: Path
    error: str | None = None


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    path.write_text(text)


def scenario_label(scenario: dict[str, Any]) -> str:
    return f"{scenario['id']} ({scenario['expected_role']} / tier {scenario['expected_tier']})"


def build_generation_prompt(provider: str, scenario: dict[str, Any]) -> str:
    rubric_lines = "\n".join(f"- {path}" for path in scenario["rubric_paths"])
    return textwrap.dedent(
        f"""
        You are running a repository evaluation for the Daggerheart skill definitions in this checkout.

        Task:
        - Read `{scenario["skill_path"]}` and the relevant files it references.
        - Use the repo's conventions as the source of truth.
        - Handle the user request below exactly as the skill should.

        Scenario:
        - Scenario id: {scenario["id"]}
        - Expected tier: {scenario["expected_tier"]}
        - Expected role: {scenario["expected_role"]}
        - User request: {scenario["prompt"]}

        Supporting rubric files:
        {rubric_lines}

        Output requirements:
        - Return only the final adversary markdown.
        - Do not wrap the answer in code fences.
        - Do not explain your reasoning.
        - Do not modify repository files.
        - Stay within the role and tier implied by the scenario.

        The provider running this prompt is {provider}.
        """
    ).strip() + "\n"


def build_judge_prompt(judge: str, candidate_name: str, scenario: dict[str, Any], candidate_output: str) -> str:
    rubric_lines = "\n".join(f"- {path}" for path in scenario["rubric_paths"])
    return textwrap.dedent(
        f"""
        You are judging a repository eval result for the Daggerheart skill definitions in this checkout.

        Read these files before deciding:
        - `{scenario["skill_path"]}`
        {rubric_lines}

        Scenario:
        - Scenario id: {scenario["id"]}
        - User request: {scenario["prompt"]}
        - Expected tier: {scenario["expected_tier"]}
        - Expected role: {scenario["expected_role"]}
        - Candidate generator: {candidate_name}

        Candidate output:
        <<<CANDIDATE_OUTPUT
        {candidate_output.rstrip()}
        CANDIDATE_OUTPUT

        Return JSON only with the required schema.
        Scoring rules:
        - `pass` should be true only if the output is useful and acceptable for the scenario.
        - `score` is 1 to 5.
        - `strengths` and `issues` should each contain short concrete points.
        - `summary` should be one short paragraph.
        - `confidence` must be one of low, medium, high.

        The provider running this judge prompt is {judge}.
        """
    ).strip() + "\n"


def run_command(cmd: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path, stdin_text: str | None = None, env: dict[str, str] | None = None) -> CommandResult:
    ensure_parent(stdout_path)
    ensure_parent(stderr_path)
    start = time.perf_counter()
    process = subprocess.run(
        cmd,
        cwd=str(cwd),
        input=stdin_text,
        text=True,
        capture_output=True,
        env=env,
    )
    duration = time.perf_counter() - start
    stdout_path.write_text(process.stdout)
    stderr_path.write_text(process.stderr)
    return CommandResult(
        ok=process.returncode == 0,
        returncode=process.returncode,
        duration=duration,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        error=None if process.returncode == 0 else f"Command failed with exit code {process.returncode}",
    )


def run_codex(prompt: str, *, model: str, output_path: Path, log_prefix: Path, schema_path: Path | None = None) -> CommandResult:
    cmd = [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--model",
        model,
    ]
    if schema_path is not None:
        cmd.extend(["--output-schema", str(schema_path)])
    cmd.extend(["--output-last-message", str(output_path), "-"])
    return run_command(
        cmd,
        cwd=ROOT,
        stdout_path=log_prefix.with_suffix(".stdout.txt"),
        stderr_path=log_prefix.with_suffix(".stderr.txt"),
        stdin_text=prompt,
        env=os.environ.copy(),
    )


def run_claude(prompt: str, *, model: str, output_path: Path, log_prefix: Path, schema_text: str | None = None) -> CommandResult:
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "text",
        "--permission-mode",
        "bypassPermissions",
        "--model",
        model,
    ]
    if schema_text is not None:
        cmd.extend(["--json-schema", schema_text])
    cmd.append(prompt)
    result = run_command(
        cmd,
        cwd=ROOT,
        stdout_path=log_prefix.with_suffix(".stdout.txt"),
        stderr_path=log_prefix.with_suffix(".stderr.txt"),
        env=os.environ.copy(),
    )
    if result.stdout_path.exists():
        output_path.write_text(result.stdout_path.read_text())
    return result


def synthesize_error_output(provider: str, command_result: CommandResult, output_path: Path) -> None:
    text = textwrap.dedent(
        f"""
        {provider} run failed.

        {command_result.error or "Unknown error"}.
        See:
        - stdout: {command_result.stdout_path.relative_to(ROOT)}
        - stderr: {command_result.stderr_path.relative_to(ROOT)}
        """
    ).strip() + "\n"
    output_path.write_text(text)


def parse_structured_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in model output")
    return json.loads(stripped[start : end + 1])


def write_failure_judge_payload(path: Path, summary: str, issue: str) -> None:
    path.write_text(
        json.dumps(
            {
                "pass": False,
                "score": 1,
                "summary": summary,
                "strengths": [],
                "issues": [issue],
                "confidence": "low",
            },
            indent=2,
        )
        + "\n"
    )


def validate_candidate(text: str, scenario: dict[str, Any]) -> tuple[list[str], list[str]]:
    return VALIDATOR_MODULE.validate_output(
        text,
        expected_tier=scenario["expected_tier"],
        expected_role=scenario["expected_role"],
    )


def write_junit_xml(path: Path, report: dict[str, Any]) -> None:
    testsuites = ET.Element("testsuites")
    suites: dict[str, list[dict[str, Any]]] = {
        "cross-eval-deterministic": report["deterministic"],
        "cross-eval-judges": report["judges"],
    }

    for suite_name, entries in suites.items():
        suite = ET.SubElement(
            testsuites,
            "testsuite",
            name=suite_name,
            tests=str(len(entries)),
            failures=str(sum(1 for entry in entries if not entry["pass"])),
            errors="0",
            skipped="0",
            time="0.0",
        )
        for entry in entries:
            case = ET.SubElement(
                suite,
                "testcase",
                classname=suite_name,
                name=entry["name"],
                time="0.0",
            )
            if not entry["pass"]:
                failure = ET.SubElement(case, "failure", message=entry["message"].splitlines()[0])
                failure.text = entry["message"]
            if entry.get("details"):
                system_out = ET.SubElement(case, "system-out")
                system_out.text = entry["details"]

    ensure_parent(path)
    ET.ElementTree(testsuites).write(path, encoding="utf-8", xml_declaration=True)


def build_report(scenario: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    generated = {
        "codex": paths["codex_generated"].read_text().strip(),
        "claude": paths["claude_generated"].read_text().strip(),
    }
    judge_payloads = {
        "claude_on_codex": parse_structured_json(paths["claude_judge_codex"].read_text()),
        "codex_on_claude": parse_structured_json(paths["codex_judge_claude"].read_text()),
    }

    deterministic: list[dict[str, Any]] = []
    judges: list[dict[str, Any]] = []
    lanes: list[dict[str, Any]] = []

    for provider, text in generated.items():
        errors, warnings = validate_candidate(text, scenario)
        deterministic.append(
            {
                "name": f"{provider}-generation",
                "pass": not errors,
                "message": "Deterministic validation passed" if not errors else "\n".join(errors),
                "details": "\n".join(f"warning: {warning}" for warning in warnings),
            }
        )

    judge_map = {
        "codex": ("claude_on_codex", "Claude"),
        "claude": ("codex_on_claude", "Codex"),
    }
    deterministic_map = {entry["name"].split("-")[0]: entry for entry in deterministic}

    for provider, (judge_key, judge_name) in judge_map.items():
        judge = judge_payloads[judge_key]
        judges.append(
            {
                "name": f"{provider}-judged-by-{judge_name.lower()}",
                "pass": bool(judge["pass"]),
                "message": judge["summary"] if judge["pass"] else "\n".join([judge["summary"], *judge.get("issues", [])]),
                "details": "\n".join(judge.get("strengths", [])),
            }
        )
        lanes.append(
            {
                "generator": provider,
                "judge": judge_name,
                "deterministic_pass": deterministic_map[provider]["pass"],
                "judge_pass": bool(judge["pass"]),
                "judge_score": judge["score"],
                "confidence": judge["confidence"],
                "summary": judge["summary"],
                "issues": judge.get("issues", []),
                "strengths": judge.get("strengths", []),
                "overall_pass": deterministic_map[provider]["pass"] and bool(judge["pass"]),
            }
        )

    overall_pass = all(entry["pass"] for entry in deterministic) and all(entry["pass"] for entry in judges)
    return {
        "scenario": scenario,
        "overall_pass": overall_pass,
        "deterministic": deterministic,
        "judges": judges,
        "lanes": lanes,
    }


def write_summary(path: Path, report: dict[str, Any]) -> None:
    scenario = report["scenario"]
    lines = [
        f"# Cross-Eval Summary",
        "",
        f"- Scenario: `{scenario['id']}`",
        f"- Prompt: {scenario['prompt']}",
        f"- Expected: tier {scenario['expected_tier']} / {scenario['expected_role']}",
        f"- Overall pass: `{'yes' if report['overall_pass'] else 'no'}`",
        "",
        "| Generator | Judge | Deterministic | Judge | Score | Overall |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for lane in report["lanes"]:
        lines.append(
            "| {generator} | {judge} | {deterministic_pass} | {judge_pass} | {judge_score} | {overall_pass} |".format(
                generator=lane["generator"],
                judge=lane["judge"],
                deterministic_pass="pass" if lane["deterministic_pass"] else "fail",
                judge_pass="pass" if lane["judge_pass"] else "fail",
                judge_score=lane["judge_score"],
                overall_pass="pass" if lane["overall_pass"] else "fail",
            )
        )
    lines.append("")
    for lane in report["lanes"]:
        lines.append(f"## {lane['generator'].title()} generated, {lane['judge']} judged")
        lines.append("")
        lines.append(lane["summary"])
        if lane["strengths"]:
            lines.append("")
            lines.append("Strengths:")
            lines.extend(f"- {item}" for item in lane["strengths"])
        if lane["issues"]:
            lines.append("")
            lines.append("Issues:")
            lines.extend(f"- {item}" for item in lane["issues"])
        lines.append("")
    write_text(path, "\n".join(lines).rstrip() + "\n")


def materialize_mock_outputs(scenario: dict[str, Any], paths: dict[str, Path]) -> None:
    sample_rel = scenario.get("sample_output")
    if not sample_rel:
        raise ValueError("Mock mode requires scenario.sample_output")
    sample_text = (ROOT / sample_rel).read_text()
    paths["codex_generated"].write_text(sample_text)
    paths["claude_generated"].write_text(sample_text)
    canned = {
        "pass": True,
        "score": 4,
        "summary": "The output matches the repository format and is serviceable for the scenario.",
        "strengths": [
            "It follows the expected adversary structure.",
            "The tier and role fit the scenario."
        ],
        "issues": [],
        "confidence": "medium"
    }
    paths["claude_judge_codex"].write_text(json.dumps(canned, indent=2) + "\n")
    paths["codex_judge_claude"].write_text(json.dumps(canned, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--junit-xml", type=Path, default=DEFAULT_JUNIT_XML)
    parser.add_argument("--codex-model", default="gpt-5-codex")
    parser.add_argument("--claude-model", default="claude-sonnet-4-20250514")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    scenario = read_json(args.scenario)
    output_root = args.output_root
    prompts_dir = output_root / "prompts"
    outputs_dir = output_root / "outputs"
    reports_dir = output_root / "reports"
    for directory in [prompts_dir, outputs_dir, reports_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    paths = {
        "codex_generate_prompt": prompts_dir / "codex-generate.txt",
        "claude_generate_prompt": prompts_dir / "claude-generate.txt",
        "claude_judge_prompt": prompts_dir / "claude-judge-codex.txt",
        "codex_judge_prompt": prompts_dir / "codex-judge-claude.txt",
        "codex_generated": outputs_dir / "codex-generated.md",
        "claude_generated": outputs_dir / "claude-generated.md",
        "claude_judge_codex": outputs_dir / "claude-judge-codex.json",
        "codex_judge_claude": outputs_dir / "codex-judge-claude.json",
        "report_json": reports_dir / "cross-eval.json",
        "summary_md": reports_dir / "summary.md",
    }

    write_text(paths["codex_generate_prompt"], build_generation_prompt("Codex", scenario))
    write_text(paths["claude_generate_prompt"], build_generation_prompt("Claude", scenario))

    if args.mock:
        materialize_mock_outputs(scenario, paths)
    else:
        if not command_exists("codex"):
            raise SystemExit("`codex` is not available on PATH.")
        if not command_exists("claude"):
            raise SystemExit("`claude` is not available on PATH.")
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is required for live runs.")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY is required for live runs.")

        codex_result = run_codex(
            paths["codex_generate_prompt"].read_text(),
            model=args.codex_model,
            output_path=paths["codex_generated"],
            log_prefix=outputs_dir / "codex-generate",
        )
        if not codex_result.ok and not paths["codex_generated"].exists():
            synthesize_error_output("Codex generation", codex_result, paths["codex_generated"])

        claude_result = run_claude(
            paths["claude_generate_prompt"].read_text(),
            model=args.claude_model,
            output_path=paths["claude_generated"],
            log_prefix=outputs_dir / "claude-generate",
        )
        if not claude_result.ok and not paths["claude_generated"].exists():
            synthesize_error_output("Claude generation", claude_result, paths["claude_generated"])

    write_text(
        paths["claude_judge_prompt"],
        build_judge_prompt("Claude", "Codex", scenario, paths["codex_generated"].read_text()),
    )
    write_text(
        paths["codex_judge_prompt"],
        build_judge_prompt("Codex", "Claude", scenario, paths["claude_generated"].read_text()),
    )

    if not args.mock:
        claude_judge_result = run_claude(
            paths["claude_judge_prompt"].read_text(),
            model=args.claude_model,
            output_path=paths["claude_judge_codex"],
            log_prefix=outputs_dir / "claude-judge-codex",
            schema_text=SCHEMA_PATH.read_text(),
        )
        if not claude_judge_result.ok:
            write_failure_judge_payload(
                paths["claude_judge_codex"],
                "Claude judge execution failed.",
                claude_judge_result.error or "Unknown Claude judge error",
            )

        codex_judge_result = run_codex(
            paths["codex_judge_prompt"].read_text(),
            model=args.codex_model,
            output_path=paths["codex_judge_claude"],
            log_prefix=outputs_dir / "codex-judge-claude",
            schema_path=SCHEMA_PATH,
        )
        if not codex_judge_result.ok:
            write_failure_judge_payload(
                paths["codex_judge_claude"],
                "Codex judge execution failed.",
                codex_judge_result.error or "Unknown Codex judge error",
            )

    report = build_report(scenario, paths)
    write_text(paths["report_json"], json.dumps(report, indent=2) + "\n")
    write_summary(paths["summary_md"], report)
    write_junit_xml(args.junit_xml, report)

    print(f"Scenario: {scenario_label(scenario)}")
    print(f"Summary: {paths['summary_md']}")
    print(f"JUnit: {args.junit_xml}")
    print(f"Overall pass: {'yes' if report['overall_pass'] else 'no'}")
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
