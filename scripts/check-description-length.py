#!/usr/bin/env python3
from pathlib import Path
import re
import sys


def extract_description(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    frontmatter = parts[1]
    match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("skills")
    status = 0
    for skill in sorted(root.glob("daggerheart-*/SKILL.md")):
        description = extract_description(skill.read_text())
        if description is None:
            print(f"Missing description: {skill}")
            status = 1
            continue
        length = len(description)
        if length > 1024:
            print(f"Description too long ({length}): {skill}")
            status = 1
        else:
            print(f"{length:4d} {skill}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
