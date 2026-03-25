#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def extract_text_blocks(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), str):
            return value["content"]
    return ""


def candidate_messages(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ["messages", "events", "entries"]:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def extract_output_text(payload: Any) -> str:
    messages = candidate_messages(payload)
    for item in reversed(messages):
        message = item.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            text = extract_text_blocks(message.get("content"))
            if text:
                return text
        if item.get("role") == "assistant":
            text = extract_text_blocks(item.get("content"))
            if text:
                return text
    if isinstance(payload, dict):
        for key in ["result", "final_message", "content", "text"]:
            text = extract_text_blocks(payload.get(key))
            if text:
                return text
    raise ValueError("Could not find assistant text in Claude action output")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text())
    text = extract_output_text(payload).rstrip() + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
