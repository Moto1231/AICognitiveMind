"""Copy canonical mandatory Axiom skills into the existing portable plugin."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REQUIRED_SKILLS = ("axiom-continuity", "axiom-current-state")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def sync_plugin_skills(repository_root: Path, *, check: bool = False) -> list[Path]:
    """Return stale bundle paths, copying them unless running a read-only check."""
    canonical_root = repository_root / "src" / "aicognitive_mind" / "skills"
    bundled_root = repository_root / "plugins" / "axiom-mind" / "skills"
    # Read every source first: a missing required skill must not partially update a bundle.
    sources = [
        (bundled_root / name / "SKILL.md", (canonical_root / name / "SKILL.md").read_bytes())
        for name in REQUIRED_SKILLS
    ]
    stale = [
        destination for destination, content in sources
        if not destination.is_file() or destination.read_bytes() != content
    ]
    if not check:
        for destination, content in sources:
            if destination in stale:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="Fail when bundled skills differ from canonical source; do not write files.",
    )
    args = parser.parse_args(argv)
    try:
        stale = sync_plugin_skills(REPOSITORY_ROOT, check=args.check)
    except OSError as exc:
        print(f"Cannot read or synchronize required plugin skills: {exc}", file=sys.stderr)
        return 2
    if args.check and stale:
        print("Bundled skills differ from canonical source:", file=sys.stderr)
        for path in stale:
            print(f"  {path.relative_to(REPOSITORY_ROOT).as_posix()}", file=sys.stderr)
        print("Run python scripts/sync_plugin_skills.py to synchronize them.", file=sys.stderr)
        return 1
    print(
        "Required plugin skills are synchronized." if args.check
        else f"Updated {len(stale)} required plugin skill(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
