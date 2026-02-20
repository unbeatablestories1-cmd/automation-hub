"""
commands/start.py — devctl start TICKET [--base BRANCH] [--force]

For every repo in devctl.yaml:
  1. git fetch origin
  2. Error if branch already exists locally (unless --force)
  3. Warn if branch already exists on remote
  4. Checkout base branch and pull
  5. Create the feature branch
  6. Push with upstream tracking

Writes .devctl-state.yaml on success.
"""
import argparse
import sys
from pathlib import Path

from config import load_config
from git_ops import (
    GitError,
    checkout_branch,
    create_branch,
    fetch_origin,
    local_branch_exists,
    pull_branch,
    push_branch,
    remote_branch_exists,
)
from state import write_state


def cmd_start(args: argparse.Namespace) -> None:
    ticket: str = args.ticket
    base_override: str | None = getattr(args, "base", None)
    force: bool = getattr(args, "force", False)
    repos_filter: list[str] | None = getattr(args, "repos", None)

    config = load_config()
    branch = f"{ticket}"

    if repos_filter is not None:
        unknown = [r for r in repos_filter if r not in config["repos"]]
        if unknown:
            sys.exit(f"Error: Unknown repo(s): {', '.join(unknown)}")
        repos = {k: v for k, v in config["repos"].items() if k in repos_filter}
    else:
        repos = config["repos"]

    successes: list[str] = []
    errors: list[str] = []

    for name, repo_cfg in repos.items():
        repo_path = Path(repo_cfg["_resolved_path"])
        base = base_override or repo_cfg["base"]

        try:
            # Always sync remote state first so ls-remote is accurate
            fetch_origin(repo_path)

            # ----------------------------------------------------------------
            # Guard: local branch already exists
            # ----------------------------------------------------------------
            if local_branch_exists(repo_path, branch):
                if not force:
                    errors.append(
                        f"  \u2718 {name}: branch '{branch}' already exists locally "
                        f"(use --force to check it out and re-push)"
                    )
                    continue

                # --force: check out and push whatever is there
                checkout_branch(repo_path, branch)
                push_branch(repo_path, branch)
                successes.append(f"  \u2714 {name} \u2192 {branch} (existing branch re-pushed)")
                continue

            # ----------------------------------------------------------------
            # Warn if remote already has the branch (don't abort)
            # ----------------------------------------------------------------
            if remote_branch_exists(repo_path, branch):
                print(
                    f"  ! {name}: remote branch '{branch}' already exists \u2014 "
                    "will create local branch and push"
                )

            # ----------------------------------------------------------------
            # Prepare base branch
            # ----------------------------------------------------------------
            checkout_branch(repo_path, base)
            pull_branch(repo_path)

            # ----------------------------------------------------------------
            # Create and push feature branch
            # ----------------------------------------------------------------
            create_branch(repo_path, branch)
            push_branch(repo_path, branch)

            successes.append(f"  \u2714 {name} \u2192 {branch} created & pushed")

        except GitError as exc:
            errors.append(f"  \u2718 {name}: {exc}")

    # Print results
    for line in successes:
        print(line)
    for line in errors:
        print(line, file=sys.stderr)

    if errors:
        print("\nBranch synchronization incomplete.", file=sys.stderr)
        sys.exit(1)

    write_state(ticket, branch, base_override)
    print(f"\nBranch synchronization complete.")
