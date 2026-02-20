"""
commands/init.py — devctl init

Scans the current directory for immediate subdirectories that are git
repositories and writes devctl.yaml.  Overwrites any existing config.
"""
import sys
from pathlib import Path

from git_ops import get_default_branch


def cmd_init(args) -> None:
    cwd = Path.cwd()

    repos = sorted(
        entry for entry in cwd.iterdir()
        if entry.is_dir() and (entry / ".git").is_dir()
    )

    if not repos:
        sys.exit("Error: No git repositories found in the current directory.")

    lines = ["repos:\n"]
    for repo_path in repos:
        name = repo_path.name
        base = get_default_branch(repo_path)
        lines.append(f"  {name}:\n")
        lines.append(f"    path: ./{name}\n")
        lines.append(f"    base: {base}\n")

    config_path = cwd / "devctl.yaml"
    config_path.write_text("".join(lines))

    print(f"Wrote {config_path.name} with {len(repos)} repo(s):")
    for repo_path in repos:
        print(f"  {repo_path.name}")
