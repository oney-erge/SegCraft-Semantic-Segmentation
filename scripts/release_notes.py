"""Build user-facing release notes from the canonical changelog."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def release_notes(changelog: str, version: str) -> str:
    version = version.removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[a-zA-Z0-9.]+)?", version):
        raise ValueError("expected a package version such as 0.1.7")
    heading = re.compile(rf"^## \[?{re.escape(version)}\]?(?:\s+-\s+.*)?\s*$", re.MULTILINE)
    match = heading.search(changelog)
    if match is None:
        raise ValueError(f"CHANGELOG.md has no section for {version}")
    remaining = changelog[match.end():]
    next_heading = re.search(r"^##\s+", remaining, re.MULTILINE)
    body = remaining[: next_heading.start() if next_heading else None].strip()
    if not body:
        raise ValueError(f"CHANGELOG.md has an empty section for {version}")
    return (
        "## Get started\n\n"
        "```bash\npip install \"segcraft[web]\"\nsegcraft-web\n```\n\n"
        "## What changed for users\n\n" + body + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Package version or v-prefixed release tag")
    args = parser.parse_args()
    try:
        print(release_notes(Path("CHANGELOG.md").read_text(encoding="utf-8"), args.version))
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
