#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import textwrap
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cross_eval_models import load_verification_properties
from skill_test_suites import validate_skill_output


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO = ROOT / "evals" / "cross-eval" / "scenarios" / "tier1_leader_smoke.json"
DEFAULT_OUTPUT_ROOT = ROOT / "cross-eval"
DEFAULT_JUNIT_XML = ROOT / "test-results" / "cross-eval.junit.xml"
FIXTURE_ROOT = ROOT / "evals" / "cross-eval" / "fixtures"


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
    sequence = [("openai", "anthropic"), ("anthropic", "openai")]
    plan: list[tuple[str, str]] = []
    for index in range(max_attempts):
        plan.append(sequence[index % len(sequence)])
    return plan


def parse_lane(value: str) -> tuple[str, str]:
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"openai-by-anthropic", "openai-gen-anthropic-judge", "codex-by-claude", "codex-gen-claude-judge"}:
        return ("openai", "anthropic")
    if normalized in {"anthropic-by-openai", "anthropic-gen-openai-judge", "claude-by-codex", "claude-gen-codex-judge"}:
        return ("anthropic", "openai")
    raise SystemExit(
        "--lane must be one of: openai-by-anthropic, anthropic-by-openai, openai-gen-anthropic-judge, anthropic-gen-openai-judge."
    )


def prepare_attempt_files(
    *,
    attempt_number: int,
    skill_llm_provider: str,
    judge_llm_provider: str,
    request_path: Path,
    properties_path: Path,
    request_text: str,
    properties: dict[str, Any],
    output_root: Path,
) -> dict[str, Path]:
    attempt_dir = output_root / f"attempt-{attempt_number:02d}-{skill_llm_provider}-by-{judge_llm_provider}"
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

    generation_prompt_path = prompts_dir / f"{skill_llm_provider}-generate.txt"
    generated_output_path = outputs_dir / f"{skill_llm_provider}-generated.md"
    judge_prompt_path = prompts_dir / f"{judge_llm_provider}-judge-{skill_llm_provider}.txt"
    judge_output_path = outputs_dir / f"{judge_llm_provider}-judge-{skill_llm_provider}.json"
    judge_metadata_path = outputs_dir / f"{judge_llm_provider}-judge-{skill_llm_provider}.meta.json"

    generation_prompt = build_generation_prompt(properties, request_text)
    write_text(generation_prompt_path, generation_prompt)

    return {
        "attempt_dir": attempt_dir,
        "inputs_dir": inputs_dir,
        "prompts_dir": prompts_dir,
        "outputs_dir": outputs_dir,
        "reports_dir": reports_dir,
        "copied_request_path": copied_request_path,
        "copied_properties_path": copied_properties_path,
        "generation_prompt_path": generation_prompt_path,
        "generated_output_path": generated_output_path,
        "judge_prompt_path": judge_prompt_path,
        "judge_output_path": judge_output_path,
        "judge_metadata_path": judge_metadata_path,
    }


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


def run_openai_generation(prompt: str, *, model: str, output_path: Path, log_prefix: Path) -> CommandResult:
    cmd = ["codex", "exec", "--sandbox", "read-only", "--model", model]
    cmd.extend(["--output-last-message", str(output_path), "-"])
    return run_command(
        cmd,
        cwd=ROOT,
        stdout_path=log_prefix.with_suffix(".stdout.txt"),
        stderr_path=log_prefix.with_suffix(".stderr.txt"),
        stdin_text=prompt,
    )


def run_anthropic_generation(prompt: str, *, model: str, output_path: Path, log_prefix: Path) -> CommandResult:
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


def model_for_provider(provider: str, *, openai_model: str, anthropic_model: str) -> str:
    if provider == "openai":
        return openai_model
    if provider == "anthropic":
        return anthropic_model
    raise ValueError(f"Unsupported provider: {provider}")


def build_generation_prompt(properties: dict[str, Any], user_request: str) -> str:
    skill_access = properties["skill_access"]
    generation_requirements = "\n".join(
        f"- {requirement}" for requirement in properties["generation_requirements"]
    )
    return textwrap.dedent(
        f"""
        Repository grounding:
        - Read and use `{skill_access["skill_path"]}` and the files it references before answering.
        - Read and follow the exact final-output shape in `{skill_access["template_path"]}`.
        - Use that skill as the source of truth for format and content.
        - Do not use any evaluation criteria, expected role metadata, or sample outputs.

        Respond to this user request exactly as the skill should:

        {user_request.rstrip()}

        Output requirements:
        {generation_requirements}
        """
    ).strip() + "\n"


def build_judge_prompt(
    *,
    request_path: Path,
    properties_path: Path,
    request_text: str,
    properties: dict[str, Any],
    candidate_name: str,
    candidate_output: str,
) -> str:
    return textwrap.dedent(
        f"""
        Judge the candidate output for this repository evaluation.

        Use the inline fixtures below as the complete judging context.
        Treat the verification properties as the source of truth.
        Do not invent additional format requirements beyond what is stated here.

        User request fixture (`{display_path(request_path)}`):
        <<<USER_REQUEST
        {request_text.rstrip()}
        USER_REQUEST

        Verification properties (`{display_path(properties_path)}`):
        <<<VERIFICATION_PROPERTIES
        {json.dumps(properties, indent=2)}
        VERIFICATION_PROPERTIES

        Candidate generator: {candidate_name}

        Candidate output:
        <<<CANDIDATE_OUTPUT
        {candidate_output.rstrip()}
        CANDIDATE_OUTPUT

        Return a structured judgment using the provided schema.
        """
    ).strip() + "\n"


def failure_judge_payload(summary: str, issue: str) -> dict[str, Any]:
    return {
        "pass": False,
        "score": 1,
        "summary": summary,
        "strengths": [],
        "issues": [issue],
        "confidence": "low",
    }


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
                name=f"attempt-{attempt['attempt']:02d}-{attempt['skill_llm_provider']}",
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
        "| Attempt | Skill LLM | Judge LLM | Deterministic | Judge | Overall | Stop reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for attempt in report["attempts"]:
        lines.append(
            "| {attempt} | {skill_llm_provider} | {judge_llm_provider} | {det} | {judge_status} | {overall} | {stop_reason} |".format(
                attempt=attempt["attempt"],
                skill_llm_provider=attempt["skill_llm_provider"],
                judge_llm_provider=attempt["judge_llm_provider"],
                det="pass" if attempt["deterministic"]["pass"] else "fail",
                judge_status="skipped" if attempt["judge"]["status"] == "not_run" else ("pass" if attempt["judge"]["pass"] else "fail"),
                overall="pass" if attempt["overall_pass"] else "fail",
                stop_reason=attempt["stop_reason"] or "",
            )
        )
    lines.append("")

    for attempt in report["attempts"]:
        lines.append(
            f"## Attempt {attempt['attempt']}: {attempt['skill_llm_provider']} generated, {attempt['judge_llm_provider']} judged"
        )
        lines.append("")
        lines.append(f"- Skill model: `{attempt['skill_model']}`")
        if attempt.get("judge_model"):
            lines.append(f"- Judge model: `{attempt['judge_model']}`")
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
    skill_llm_provider: str,
    judge_llm_provider: str,
    scenario: dict[str, Any],
    properties: dict[str, Any],
    request_path: Path,
    properties_path: Path,
    request_text: str,
    output_root: Path,
    openai_model: str,
    anthropic_model: str,
    mock: bool,
    mock_fail_attempt: int | None,
    use_existing_outputs: bool,
) -> dict[str, Any]:
    paths = prepare_attempt_files(
        attempt_number=attempt_number,
        skill_llm_provider=skill_llm_provider,
        judge_llm_provider=judge_llm_provider,
        request_path=request_path,
        properties_path=properties_path,
        request_text=request_text,
        properties=properties,
        output_root=output_root,
    )
    outputs_dir = paths["outputs_dir"]
    reports_dir = paths["reports_dir"]
    copied_request_path = paths["copied_request_path"]
    copied_properties_path = paths["copied_properties_path"]
    generation_prompt_path = paths["generation_prompt_path"]
    generated_output_path = paths["generated_output_path"]
    judge_prompt_path = paths["judge_prompt_path"]
    judge_output_path = paths["judge_output_path"]
    judge_metadata_path = paths["judge_metadata_path"]
    generation_prompt = generation_prompt_path.read_text()
    skill_model = model_for_provider(skill_llm_provider, openai_model=openai_model, anthropic_model=anthropic_model)
    judge_model: str | None = None

    if mock:
        materialize_mock_generation(ROOT / scenario["sample_output"], generated_output_path)
        generation_result = None
    elif use_existing_outputs:
        generation_result = None
        if not generated_output_path.exists():
            raise SystemExit(f"Missing pre-generated output for attempt {attempt_number}: {generated_output_path}")
    else:
        if skill_llm_provider == "openai":
            generation_result = run_openai_generation(
                generation_prompt,
                model=skill_model,
                output_path=generated_output_path,
                log_prefix=outputs_dir / f"{skill_llm_provider}-generate",
            )
        else:
            generation_result = run_anthropic_generation(
                generation_prompt,
                model=skill_model,
                output_path=generated_output_path,
                log_prefix=outputs_dir / f"{skill_llm_provider}-generate",
            )
        if generation_result is not None and not generation_result.ok and not generated_output_path.exists():
            generated_output_path.write_text(
                textwrap.dedent(
                    f"""
                    {skill_llm_provider} generation failed.

                    {generation_result.error or "Unknown error"}.
                    See:
                    - stdout: {display_path(generation_result.stdout_path)}
                    - stderr: {display_path(generation_result.stderr_path)}
                    """
                ).strip()
                + "\n"
            )

    generated_text = generated_output_path.read_text()
    errors, warnings = validate_skill_output(properties["suite"], generated_text, properties)
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
            request_text=request_text,
            properties=properties,
            candidate_name=skill_llm_provider,
            candidate_output=generated_text,
        )
        write_text(judge_prompt_path, judge_prompt)

        if mock:
            judge_payload = materialize_mock_judge(
                judge_output_path,
                pass_value=mock_fail_attempt != attempt_number,
            )
            write_text(
                judge_metadata_path,
                json.dumps({"provider": judge_llm_provider, "mode": "mock"}, indent=2) + "\n",
            )
        else:
            from structured_judge import judge_with_pydantic_ai

            judge_model = model_for_provider(judge_llm_provider, openai_model=openai_model, anthropic_model=anthropic_model)
            try:
                judge_payload, judge_metadata = judge_with_pydantic_ai(
                    provider=judge_llm_provider,
                    model=judge_model,
                    prompt=judge_prompt,
                )
                write_text(judge_output_path, json.dumps(judge_payload, indent=2) + "\n")
                write_text(judge_metadata_path, json.dumps(judge_metadata, indent=2) + "\n")
            except Exception as exc:
                judge_payload = failure_judge_payload(
                    f"{judge_llm_provider.title()} judge execution failed.",
                    str(exc),
                )
                write_text(
                    judge_output_path,
                    json.dumps(judge_payload, indent=2) + "\n",
                )
                write_text(
                    judge_metadata_path,
                    json.dumps({"provider": judge_llm_provider, "model": judge_model, "error": str(exc)}, indent=2) + "\n",
                )

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
        "skill_llm_provider": skill_llm_provider,
        "skill_model": skill_model,
        "judge_llm_provider": judge_llm_provider,
        "judge_model": judge_model,
        "generation_prompt_path": display_path(generation_prompt_path),
        "generated_output_path": display_path(generated_output_path),
        "judge_output_path": display_path(judge_output_path),
        "judge_metadata_path": display_path(judge_metadata_path),
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
    parser.add_argument("--openai-model", default="gpt-5.4-nano")
    parser.add_argument("--anthropic-model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--codex-model", dest="openai_model")
    parser.add_argument("--claude-model", dest="anthropic_model")
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--lane")
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--mock-fail-attempt", type=int)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--use-existing-outputs", action="store_true")
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
    properties = load_verification_properties(properties_path)
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    if args.lane and args.max_attempts is not None:
        raise SystemExit("--lane cannot be combined with --max-attempts.")
    if args.attempt_number < 1:
        raise SystemExit("--attempt-number must be at least 1.")

    if args.lane:
        attempt_plan = [parse_lane(args.lane)]
        requested_attempts = 1
        attempt_numbers = [args.attempt_number]
    else:
        requested_attempts = args.max_attempts or int(scenario.get("max_attempts", 3))
        if requested_attempts < 1:
            raise SystemExit("--max-attempts must be at least 1.")
        attempt_plan = build_attempt_plan(requested_attempts)
        attempt_numbers = list(range(1, requested_attempts + 1))

    if args.prepare_only:
        for attempt_number, (skill_llm_provider, judge_llm_provider) in zip(attempt_numbers, attempt_plan, strict=True):
            prepare_attempt_files(
                attempt_number=attempt_number,
                skill_llm_provider=skill_llm_provider,
                judge_llm_provider=judge_llm_provider,
                request_path=request_path,
                properties_path=properties_path,
                request_text=request_text,
                properties=properties,
                output_root=output_root,
            )
        print(f"Prepared {requested_attempts} attempt prompt sets in {output_root}")
        return 0

    if not args.mock and not args.use_existing_outputs:
        if not command_exists("codex"):
            raise SystemExit("`codex` is not available on PATH.")
        if not command_exists("claude"):
            raise SystemExit("`claude` is not available on PATH.")
    if not args.mock:
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is required for live runs.")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY is required for live runs.")

    attempts: list[dict[str, Any]] = []
    stop_reason = "completed_requested_attempts"

    for attempt_number, (skill_llm_provider, judge_llm_provider) in zip(attempt_numbers, attempt_plan, strict=True):
        attempt_report = run_attempt(
            attempt_number=attempt_number,
            skill_llm_provider=skill_llm_provider,
            judge_llm_provider=judge_llm_provider,
            scenario=scenario,
            properties=properties,
            request_path=request_path,
            properties_path=properties_path,
            request_text=request_text,
            output_root=output_root,
            openai_model=args.openai_model,
            anthropic_model=args.anthropic_model,
            mock=args.mock,
            mock_fail_attempt=args.mock_fail_attempt,
            use_existing_outputs=args.use_existing_outputs,
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
