"""
commands/status.py — devctl status

Checks every repo in devctl.yaml and prints a table:

  Repo               Local Branch            Remote   Clean
  -----------------------------------------------------------
  pipeline           feature/ABC-123         ✔        ✔
  python-service     feature/ABC-123         ✔        ✘

Exits with code 1 if any repo has a mismatch, dirty tree, or missing remote.
"""
import argparse
import sys
from pathlib import Path

from config import load_config
from git_ops import (
    GitError,
    get_current_branch,
    is_working_tree_clean,
    remote_branch_exists,
)
from state import load_state

# Column widths
_W_REPO = 20
_W_BRANCH = 26
_W_REMOTE = 8
_W_CLEAN = 6


def cmd_status(args: argparse.Namespace) -> None:
    config = load_config()
    state = load_state()
    expected_branch: str = state["branch"]
    repos_filter: list[str] | None = getattr(args, "repos", None)

    if repos_filter is not None:
        unknown = [r for r in repos_filter if r not in config["repos"]]
        if unknown:
            sys.exit(f"Error: Unknown repo(s): {', '.join(unknown)}")
        repos = {k: v for k, v in config["repos"].items() if k in repos_filter}
    else:
        repos = config["repos"]

    header = (
        f"{'Repo':<{_W_REPO}} "
        f"{'Local Branch':<{_W_BRANCH}} "
        f"{'Remote':<{_W_REMOTE}} "
        f"{'Clean':<{_W_CLEAN}}"
    )
    separator = "-" * len(header)
    print(header)
    print(separator)

    any_issue = False

    for name, repo_cfg in repos.items():
        repo_path = Path(repo_cfg["_resolved_path"])

        try:
            current = get_current_branch(repo_path)
            has_remote = remote_branch_exists(repo_path, current)
            clean = is_working_tree_clean(repo_path)
        except GitError as exc:
            print(f"  \u2718 {name}: git error: {exc}", file=sys.stderr)
            any_issue = True
            continue

        branch_ok = current == expected_branch

        remote_sym = "\u2714" if has_remote else "\u2718"
        clean_sym = "\u2714" if clean else "\u2718"

        # Append a note when the branch doesn't match the state file
        note = "" if branch_ok else f"  \u2190 expected {expected_branch}"

        if not branch_ok or not has_remote or not clean:
            any_issue = True

        print(
            f"{name:<{_W_REPO}} "
            f"{current:<{_W_BRANCH}} "
            f"{remote_sym:<{_W_REMOTE}} "
            f"{clean_sym:<{_W_CLEAN}}"
            f"{note}"
        )

    if any_issue:
        sys.exit(1)
