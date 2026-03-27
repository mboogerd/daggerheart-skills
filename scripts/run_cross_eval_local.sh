#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIO="evals/cross-eval/scenarios/tier1_leader_smoke.json"
OUTPUT_ROOT="$ROOT_DIR/cross-eval"
JUNIT_XML="$ROOT_DIR/test-results/cross-eval.junit.xml"
OPENAI_MODEL="gpt-5.4-nano"
ANTHROPIC_MODEL="claude-haiku-4-5-20251001"
JUDGE_OPENAI_MODEL=""
JUDGE_ANTHROPIC_MODEL=""
EXECUTOR_MODEL=""
EXECUTOR_PROVIDER=""
JUDGE_MODEL=""
JUDGE_PROVIDER=""
MAX_ATTEMPTS="2"
LANE=""
ATTEMPT_NUMBER="1"
MODE="live"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_cross_eval_local.sh [mode] [options]

Modes:
  live       Run one local cross-eval invocation. Prefer --executor and --judge.
  mock       Run the fixture-only mock path.
  prepare    Generate prompt files only, for a GitHub-like local flow.
  evaluate   Evaluate already-generated outputs under the output root.

Options:
  --scenario PATH
  --output-root PATH
  --junit-xml PATH
  --openai-model MODEL
  --anthropic-model MODEL
  --judge-openai-model MODEL
  --judge-anthropic-model MODEL
  --executor MODEL
  --executor-provider PROVIDER
  --judge MODEL
  --judge-provider PROVIDER
  --max-attempts N           Legacy matrix mode.
  --lane openai-by-anthropic|anthropic-by-openai
  --attempt-number N
  -h, --help

Examples:
  scripts/run_cross_eval_local.sh --executor claude-haiku-4-5-20251001 --judge gpt-5.4
  scripts/run_cross_eval_local.sh --executor claude-haiku-4-5-20251001 --judge gpt-5.4 --judge-provider openai
  scripts/run_cross_eval_local.sh --lane anthropic-by-openai --attempt-number 2
  scripts/run_cross_eval_local.sh mock
  scripts/run_cross_eval_local.sh prepare --output-root /tmp/cross-eval-local
  scripts/run_cross_eval_local.sh evaluate --output-root /tmp/cross-eval-local
EOF
}

if [[ $# -gt 0 ]]; then
  case "$1" in
    live|mock|prepare|evaluate)
      MODE="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
  esac
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario)
      SCENARIO="$2"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --junit-xml)
      JUNIT_XML="$2"
      shift 2
      ;;
    --openai-model|--codex-model)
      OPENAI_MODEL="$2"
      shift 2
      ;;
    --anthropic-model|--claude-model)
      ANTHROPIC_MODEL="$2"
      shift 2
      ;;
    --judge-openai-model)
      JUDGE_OPENAI_MODEL="$2"
      shift 2
      ;;
    --judge-anthropic-model)
      JUDGE_ANTHROPIC_MODEL="$2"
      shift 2
      ;;
    --executor)
      EXECUTOR_MODEL="$2"
      shift 2
      ;;
    --executor-provider)
      EXECUTOR_PROVIDER="$2"
      shift 2
      ;;
    --judge)
      JUDGE_MODEL="$2"
      shift 2
      ;;
    --judge-provider)
      JUDGE_PROVIDER="$2"
      shift 2
      ;;
    --max-attempts)
      MAX_ATTEMPTS="$2"
      shift 2
      ;;
    --lane)
      LANE="$2"
      shift 2
      ;;
    --attempt-number)
      ATTEMPT_NUMBER="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

cd "$ROOT_DIR"

COMMON_ARGS=(
  --scenario "$SCENARIO"
  --output-root "$OUTPUT_ROOT"
  --junit-xml "$JUNIT_XML"
  --openai-model "$OPENAI_MODEL"
  --anthropic-model "$ANTHROPIC_MODEL"
)

if [[ -n "$JUDGE_OPENAI_MODEL" ]]; then
  COMMON_ARGS+=(--judge-openai-model "$JUDGE_OPENAI_MODEL")
fi

if [[ -n "$JUDGE_ANTHROPIC_MODEL" ]]; then
  COMMON_ARGS+=(--judge-anthropic-model "$JUDGE_ANTHROPIC_MODEL")
fi

if [[ -n "$EXECUTOR_MODEL" ]]; then
  COMMON_ARGS+=(--executor "$EXECUTOR_MODEL")
fi

if [[ -n "$EXECUTOR_PROVIDER" ]]; then
  COMMON_ARGS+=(--executor-provider "$EXECUTOR_PROVIDER")
fi

if [[ -n "$JUDGE_MODEL" ]]; then
  COMMON_ARGS+=(--judge "$JUDGE_MODEL")
fi

if [[ -n "$JUDGE_PROVIDER" ]]; then
  COMMON_ARGS+=(--judge-provider "$JUDGE_PROVIDER")
fi

if [[ -n "$EXECUTOR_MODEL" || -n "$JUDGE_MODEL" ]]; then
  COMMON_ARGS+=(--attempt-number "$ATTEMPT_NUMBER")
elif [[ -n "$LANE" ]]; then
  COMMON_ARGS+=(--lane "$LANE" --attempt-number "$ATTEMPT_NUMBER")
else
  COMMON_ARGS+=(--max-attempts "$MAX_ATTEMPTS")
fi

case "$MODE" in
  live)
    python3 scripts/run_cross_eval_session.py "${COMMON_ARGS[@]}"
    ;;
  mock)
    python3 scripts/run_cross_eval_session.py "${COMMON_ARGS[@]}" --mock
    ;;
  prepare)
    python3 scripts/run_cross_eval_session.py "${COMMON_ARGS[@]}" --prepare-only
    ;;
  evaluate)
    python3 scripts/run_cross_eval_session.py "${COMMON_ARGS[@]}" --use-existing-outputs
    ;;
  *)
    echo "Unsupported mode: $MODE" >&2
    exit 1
    ;;
esac
