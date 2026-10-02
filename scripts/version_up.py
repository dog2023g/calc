#!/usr/bin/env python3
"""
Определяет тип повышения версии по сообщению последнего коммита
(Используется спецификация Conventional Commits)

Правила:
  "BREAKING CHANGE" / "!" -> major (несовместимое изменение)
  "feat:"                -> minor (новая функциональность)
  "fix:"                 -> patch (исправление)
  всё остальное          -> patch (по умолчанию)
"""
import os
import re
import subprocess
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def last_commit_message() -> str:
    return subprocess.run(
        ["git", "log", "-1", "--pretty=%B"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def bump_type(message: str) -> str:
    first_line = message.splitlines()[0] if message else ""
    if "BREAKING CHANGE" in message or re.match(r"^\w+(\(.+\))?!:", first_line):
        return "major"
    if re.match(r"^feat(\(.+\))?:", first_line):
        return "minor"
    return "patch"


def main() -> None:
    current = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "0.1.0"
    major, minor, patch = (int(p) for p in current.split("."))

    kind = bump_type(last_commit_message())
    if kind == "major":
        major, minor, patch = major + 1, 0, 0
    elif kind == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1

    new_version = f"{major}.{minor}.{patch}"
    VERSION_FILE.write_text(new_version + "\n")

    print(f"Commit type: {kind}")
    print(new_version)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"new_version={new_version}\n")


if __name__ == "__main__":
    main()
