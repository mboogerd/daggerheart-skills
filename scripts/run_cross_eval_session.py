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
FIXTURE_ROOT = ROOT / "evals" / "cross-eval" / "fixtures"


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def fixture_dir_for_scenario(scenario_id: str) -> Path:
    return FIXTURE_ROOT / scenario_id


def build_attempt_plan(max_attempts: int) -> list[tuple[str, str]]:
    sequence = [("codex", "claude"), ("claude", "codex")]
    plan: list[tuple[str, str]] = []
    for index in range(max_attempts):
        plan.append(sequence[index % len(sequence)])
    return plan


def run_command(cmd: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path, stdin_text: str | None = None) -> CommandResult:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    process = subprocess.run(
        cmd,
        cwd=str(cwd),
        input=stdin_text,
        text=True,
        capture_output=True,
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
    cmd = ["codex", "exec", "--sandbox", "read-only", "--model", model]
    if schema_path is not None:
        cmd.extend(["--output-schema", str(schema_path)])
    cmd.extend(["--output-last-message", str(output_path), "-"])
    return run_command(
        cmd,
        cwd=ROOT,
        stdout_path=log_prefix.with_suffix(".stdout.txt"),
        stderr_path=log_prefix.with_suffix(".stderr.txt"),
        stdin_text=prompt,
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
    )
    if result.stdout_path.exists():
        output_path.write_text(result.stdout_path.read_text())
    return result


def build_generation_prompt(skill_path: str, user_request: str) -> str:
    return textwrap.dedent(
        f"""
        Repository grounding:
        - Read and use `{skill_path}` and the files it references before answering.
        - Use that skill as the source of truth for format and content.
        - Do not use any evaluation criteria, expected role metadata, or sample outputs.

        Respond to this user request exactly as the skill should:

        {user_request.rstrip()}

        Output requirements:
        - Return only the final answer.
        - Do not wrap the answer in code fences.
        - Do not explain your reasoning.
        - Do not modify repository files.
        """
    ).strip() + "\n"


def build_judge_prompt(*, request_path: Path, properties_path: Path, candidate_name: str, candidate_output: str) -> str:
    return textwrap.dedent(
        f"""
        Judge the candidate output for this repository evaluation.

        Source files to use:
        - User request: `{display_path(request_path)}`
        - Verification properties: `{display_path(properties_path)}`

        Read those files before deciding. Use the verification properties as the source of truth for judging.
        Do not expand the scope by reading the full skill definition unless the verification properties explicitly require it.

        Candidate generator: {candidate_name}

        Candidate output:
        <<<CANDIDATE_OUTPUT
        {candidate_output.rstrip()}
        CANDIDATE_OUTPUT

        Return JSON only with the required schema.
        """
    ).strip() + "\n"


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


def failure_judge_payload(summary: str, issue: str) -> dict[str, Any]:
    return {
        "pass": False,
        "score": 1,
        "summary": summary,
        "strengths": [],
        "issues": [issue],
        "confidence": "low",
    }


def load_judge_payload(path: Path, fallback_summary: str) -> dict[str, Any]:
    try:
        return parse_structured_json(path.read_text())
    except Exception as exc:
        payload = failure_judge_payload(fallback_summary, str(exc))
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return payload


def validate_candidate(text: str, properties: dict[str, Any]) -> tuple[list[str], list[str]]:
    return VALIDATOR_MODULE.validate_output(
        text,
        expected_tier=properties["expected_tier"],
        expected_role=properties["expected_role"],
    )


def materialize_mock_generation(sample_path: Path, output_path: Path) -> None:
    output_path.write_text(sample_path.read_text())


def materialize_mock_judge(output_path: Path, *, pass_value: bool) -> dict[str, Any]:
    payload = {
        "pass": pass_value,
        "score": 4 if pass_value else 2,
        "summary": "Mock judge accepted the output." if pass_value else "Mock judge rejected the output.",
        "strengths": ["Fixture output matches the expected adversary structure."] if pass_value else [],
        "issues": [] if pass_value else ["Injected mock failure for fail-fast verification."],
        "confidence": "medium",
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def write_junit_xml(path: Path, report: dict[str, Any]) -> None:
    testsuites = ET.Element("testsuites")
    suite_specs = [
        ("cross-eval-deterministic", "deterministic"),
        ("cross-eval-judges", "judge"),
    ]

    for suite_name, key in suite_specs:
        entries = [attempt[key] for attempt in report["attempts"]]
        skipped = sum(1 for entry in entries if entry.get("status") == "not_run")
        failures = sum(1 for entry in entries if entry.get("status") != "not_run" and not entry["pass"])
        suite = ET.SubElement(
            testsuites,
            "testsuite",
            name=suite_name,
            tests=str(len(entries)),
            failures=str(failures),
            errors="0",
            skipped=str(skipped),
            time="0.0",
        )
        for attempt, entry in zip(report["attempts"], entries):
            case = ET.SubElement(
                suite,
                "testcase",
                classname=suite_name,
                name=f"attempt-{attempt['attempt']:02d}-{attempt['generator']}",
                time="0.0",
            )
            if entry.get("status") == "not_run":
                skipped_node = ET.SubElement(case, "skipped", message=entry["message"])
                skipped_node.text = entry["message"]
            elif not entry["pass"]:
                failure = ET.SubElement(case, "failure", message=entry["message"].splitlines()[0])
                failure.text = entry["message"]
            if entry.get("details"):
                system_out = ET.SubElement(case, "system-out")
                system_out.text = entry["details"]

    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(testsuites).write(path, encoding="utf-8", xml_declaration=True)


def write_summary(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Cross-Eval Summary",
        "",
        f"- Scenario: `{report['scenario']['id']}`",
        f"- Requested attempts: `{report['requested_attempts']}`",
        f"- Executed attempts: `{len(report['attempts'])}`",
        f"- Overall pass: `{'yes' if report['overall_pass'] else 'no'}`",
        f"- Stop reason: `{report['stop_reason']}`",
        f"- User request fixture: `{report['request_path']}`",
        f"- Verification properties: `{report['properties_path']}`",
        "",
        "| Attempt | Generator | Judge | Deterministic | Judge | Overall | Stop reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for attempt in report["attempts"]:
        lines.append(
            "| {attempt} | {generator} | {judge} | {det} | {judge_status} | {overall} | {stop_reason} |".format(
                attempt=attempt["attempt"],
                generator=attempt["generator"],
                judge=attempt["judge_provider"],
                det="pass" if attempt["deterministic"]["pass"] else "fail",
                judge_status="skipped" if attempt["judge"]["status"] == "not_run" else ("pass" if attempt["judge"]["pass"] else "fail"),
                overall="pass" if attempt["overall_pass"] else "fail",
                stop_reason=attempt["stop_reason"] or "",
            )
        )
    lines.append("")

    for attempt in report["attempts"]:
        lines.append(f"## Attempt {attempt['attempt']}: {attempt['generator']} generated, {attempt['judge_provider']} judged")
        lines.append("")
        lines.append(f"- Prompt source: `{attempt['generation_prompt_path']}`")
        lines.append(f"- Output file: `{attempt['generated_output_path']}`")
        lines.append(f"- Deterministic result: `{'pass' if attempt['deterministic']['pass'] else 'fail'}`")
        if attempt["deterministic"]["warnings"]:
            lines.append("- Warnings:")
            lines.extend(f"  - {warning}" for warning in attempt["deterministic"]["warnings"])
        if attempt["deterministic"]["errors"]:
            lines.append("- Errors:")
            lines.extend(f"  - {error}" for error in attempt["deterministic"]["errors"])
        lines.append(f"- Judge result: `{attempt['judge']['status']}`")
        if attempt["judge"].get("summary"):
            lines.append(f"- Judge summary: {attempt['judge']['summary']}")
        if attempt["judge"].get("issues"):
            lines.append("- Judge issues:")
            lines.extend(f"  - {issue}" for issue in attempt["judge"]["issues"])
        if attempt["judge"].get("strengths"):
            lines.append("- Judge strengths:")
            lines.extend(f"  - {strength}" for strength in attempt["judge"]["strengths"])
        lines.append("")

    write_text(path, "\n".join(lines).rstrip() + "\n")


def run_attempt(
    *,
    attempt_number: int,
    generator: str,
    judge_provider: str,
    scenario: dict[str, Any],
    properties: dict[str, Any],
    request_path: Path,
    properties_path: Path,
    request_text: str,
    output_root: Path,
    codex_model: str,
    claude_model: str,
    mock: bool,
    mock_fail_attempt: int | None,
) -> dict[str, Any]:
    attempt_dir = output_root / f"attempt-{attempt_number:02d}-{generator}-by-{judge_provider}"
    inputs_dir = attempt_dir / "inputs"
    prompts_dir = attempt_dir / "prompts"
    outputs_dir = attempt_dir / "outputs"
    reports_dir = attempt_dir / "reports"
    for directory in [inputs_dir, prompts_dir, outputs_dir, reports_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    copied_request_path = inputs_dir / "user-request.txt"
    copied_properties_path = inputs_dir / "verification-properties.json"
    shutil.copyfile(request_path, copied_request_path)
    shutil.copyfile(properties_path, copied_properties_path)

    generation_prompt_path = prompts_dir / f"{generator}-generate.txt"
    generated_output_path = outputs_dir / f"{generator}-generated.md"
    judge_prompt_path = prompts_dir / f"{judge_provider}-judge-{generator}.txt"
    judge_output_path = outputs_dir / f"{judge_provider}-judge-{generator}.json"

    generation_prompt = build_generation_prompt(properties["skill_access"]["skill_path"], request_text)
    write_text(generation_prompt_path, generation_prompt)

    if mock:
        materialize_mock_generation(ROOT / scenario["sample_output"], generated_output_path)
        generation_result = None
    else:
        if generator == "codex":
            generation_result = run_codex(
                generation_prompt,
                model=codex_model,
                output_path=generated_output_path,
                log_prefix=outputs_dir / f"{generator}-generate",
            )
        else:
            generation_result = run_claude(
                generation_prompt,
                model=claude_model,
                output_path=generated_output_path,
                log_prefix=outputs_dir / f"{generator}-generate",
            )
        if generation_result is not None and not generation_result.ok and not generated_output_path.exists():
            generated_output_path.write_text(
                textwrap.dedent(
                    f"""
                    {generator} generation failed.

                    {generation_result.error or "Unknown error"}.
                    See:
                    - stdout: {display_path(generation_result.stdout_path)}
                    - stderr: {display_path(generation_result.stderr_path)}
                    """
                ).strip()
                + "\n"
            )

    generated_text = generated_output_path.read_text()
    errors, warnings = validate_candidate(generated_text, properties)
    deterministic = {
        "status": "passed" if not errors else "failed",
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "message": "Deterministic validation passed" if not errors else "\n".join(errors),
        "details": "\n".join(f"warning: {warning}" for warning in warnings),
    }

    judge_result: dict[str, Any]
    stop_reason: str | None = None
    overall_pass = False

    if not deterministic["pass"]:
        judge_result = {
            "status": "not_run",
            "pass": False,
            "summary": "",
            "issues": [],
            "strengths": [],
            "message": "Judge not run because deterministic validation failed.",
            "details": "",
        }
        stop_reason = "deterministic_validation_failed"
        overall_pass = False
    else:
        judge_prompt = build_judge_prompt(
            request_path=copied_request_path,
            properties_path=copied_properties_path,
            candidate_name=generator,
            candidate_output=generated_text,
        )
        write_text(judge_prompt_path, judge_prompt)

        if mock:
            judge_payload = materialize_mock_judge(
                judge_output_path,
                pass_value=mock_fail_attempt != attempt_number,
            )
        else:
            if judge_provider == "claude":
                judge_command = run_claude(
                    judge_prompt,
                    model=claude_model,
                    output_path=judge_output_path,
                    log_prefix=outputs_dir / f"{judge_provider}-judge-{generator}",
                    schema_text=SCHEMA_PATH.read_text(),
                )
            else:
                judge_command = run_codex(
                    judge_prompt,
                    model=codex_model,
                    output_path=judge_output_path,
                    log_prefix=outputs_dir / f"{judge_provider}-judge-{generator}",
                    schema_path=SCHEMA_PATH,
                )
            if not judge_command.ok:
                write_text(
                    judge_output_path,
                    json.dumps(
                        failure_judge_payload(
                            f"{judge_provider.title()} judge execution failed.",
                            judge_command.error or "Unknown judge error",
                        ),
                        indent=2,
                    )
                    + "\n",
                )
            judge_payload = load_judge_payload(judge_output_path, f"{judge_provider.title()} judge output was invalid.")

        judge_result = {
            "status": "passed" if judge_payload["pass"] else "failed",
            "pass": bool(judge_payload["pass"]),
            "score": judge_payload["score"],
            "summary": judge_payload["summary"],
            "issues": judge_payload.get("issues", []),
            "strengths": judge_payload.get("strengths", []),
            "confidence": judge_payload["confidence"],
            "message": judge_payload["summary"] if judge_payload["pass"] else "\n".join([judge_payload["summary"], *judge_payload.get("issues", [])]),
            "details": "\n".join(judge_payload.get("strengths", [])),
        }
        overall_pass = deterministic["pass"] and judge_result["pass"]
        if not judge_result["pass"]:
            stop_reason = "judge_failed"

    attempt_report = {
        "attempt": attempt_number,
        "generator": generator,
        "judge_provider": judge_provider,
        "generation_prompt_path": display_path(generation_prompt_path),
        "generated_output_path": display_path(generated_output_path),
        "deterministic": deterministic,
        "judge": judge_result,
        "overall_pass": overall_pass,
        "stop_reason": stop_reason,
    }
    write_text(reports_dir / "attempt.json", json.dumps(attempt_report, indent=2) + "\n")
    return attempt_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--junit-xml", type=Path, default=DEFAULT_JUNIT_XML)
    parser.add_argument("--codex-model", default="gpt-5-codex")
    parser.add_argument("--claude-model", default="claude-sonnet-4-20250514")
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--mock-fail-attempt", type=int)
    args = parser.parse_args()

    scenario = read_json(args.scenario)
    fixture_dir = fixture_dir_for_scenario(scenario["id"])
    request_path = fixture_dir / "user-request.txt"
    properties_path = fixture_dir / "verification-properties.json"
    if not request_path.exists() or not properties_path.exists():
        raise SystemExit(
            f"Missing checked-in fixtures for {scenario['id']}. Run `python3 scripts/render_cross_eval_fixtures.py {args.scenario}` first."
        )

    request_text = request_path.read_text().strip() + "\n"
    properties = read_json(properties_path)
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    requested_attempts = args.max_attempts or int(scenario.get("max_attempts", 3))
    if requested_attempts < 1:
        raise SystemExit("--max-attempts must be at least 1.")

    if not args.mock:
        if not command_exists("codex"):
            raise SystemExit("`codex` is not available on PATH.")
        if not command_exists("claude"):
            raise SystemExit("`claude` is not available on PATH.")
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is required for live runs.")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY is required for live runs.")

    attempts: list[dict[str, Any]] = []
    stop_reason = "completed_requested_attempts"

    for attempt_number, (generator, judge_provider) in enumerate(build_attempt_plan(requested_attempts), start=1):
        attempt_report = run_attempt(
            attempt_number=attempt_number,
            generator=generator,
            judge_provider=judge_provider,
            scenario=scenario,
            properties=properties,
            request_path=request_path,
            properties_path=properties_path,
            request_text=request_text,
            output_root=output_root,
            codex_model=args.codex_model,
            claude_model=args.claude_model,
            mock=args.mock,
            mock_fail_attempt=args.mock_fail_attempt,
        )
        attempts.append(attempt_report)
        if not attempt_report["overall_pass"]:
            stop_reason = attempt_report["stop_reason"] or "attempt_failed"
            break

    report = {
        "scenario": {
            "id": scenario["id"],
            "suite": scenario["suite"],
            "skill_path": scenario["skill_path"],
        },
        "request_path": display_path(request_path),
        "properties_path": display_path(properties_path),
        "requested_attempts": requested_attempts,
        "stop_reason": stop_reason,
        "overall_pass": all(attempt["overall_pass"] for attempt in attempts),
        "attempts": attempts,
    }

    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_text(reports_dir / "cross-eval.json", json.dumps(report, indent=2) + "\n")
    write_summary(reports_dir / "summary.md", report)
    write_junit_xml(args.junit_xml, report)

    print(f"Scenario: {scenario['id']}")
    print(f"Request fixture: {request_path}")
    print(f"Verification properties: {properties_path}")
    print(f"Executed attempts: {len(attempts)} / {requested_attempts}")
    print(f"Stop reason: {stop_reason}")
    print(f"Overall pass: {'yes' if report['overall_pass'] else 'no'}")
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
