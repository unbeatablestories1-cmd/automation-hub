"""
git_ops.py — Thin wrappers around git CLI commands.

All functions operate on an explicit repo_path so the caller never needs
to change the working directory.  Raises GitError on failure; never exits
directly so callers can decide how to handle errors.
"""
import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when a git command returns a non-zero exit code."""


def _run(
    args: list[str],
    cwd: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        msg = (result.stderr.strip() or result.stdout.strip() or
               f"exit code {result.returncode}")
        raise GitError(msg)
    return result


# ---------------------------------------------------------------------------
# Read-only queries
# ---------------------------------------------------------------------------

def get_current_branch(repo_path: Path) -> str:
    """Return the name of the currently checked-out branch."""
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    branch = result.stdout.strip()
    if branch == "HEAD":
        raise GitError("Repository is in detached HEAD state")
    return branch


def local_branch_exists(repo_path: Path, branch: str) -> bool:
    """Return True if the branch exists in the local ref store."""
    result = _run(
        ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
        repo_path,
        check=False,
    )
    return result.returncode == 0


def remote_branch_exists(repo_path: Path, branch: str) -> bool:
    """
    Return True if the branch exists on the 'origin' remote.

    Uses git ls-remote so it does not require a prior fetch.
    """
    result = _run(
        ["git", "ls-remote", "--heads", "origin", branch],
        repo_path,
        check=False,
    )
    # ls-remote exits 0 even when not found; presence in stdout is the signal
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or "ls-remote failed")
    return bool(result.stdout.strip())


def get_default_branch(repo_path: Path) -> str:
    """
    Return the default branch for the repo.

    Tries the origin/HEAD symbolic ref first (set when you clone), falls back
    to the currently checked-out branch, then to 'main'.
    """
    result = _run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "--short"],
        repo_path,
        check=False,
    )
    if result.returncode == 0:
        ref = result.stdout.strip()
        return ref.split("/", 1)[-1]  # "origin/main" → "main"
    try:
        return get_current_branch(repo_path)
    except GitError:
        return "main"


def is_working_tree_clean(repo_path: Path) -> bool:
    """Return True when there are no staged or unstaged changes."""
    result = _run(["git", "status", "--porcelain"], repo_path)
    return result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Mutating operations
# ---------------------------------------------------------------------------

def fetch_origin(repo_path: Path) -> None:
    """Fetch all refs from origin (updates remote-tracking branches)."""
    _run(["git", "fetch", "origin"], repo_path)


def checkout_branch(repo_path: Path, branch: str) -> None:
    """Switch to an existing local branch."""
    _run(["git", "checkout", branch], repo_path)


def pull_branch(repo_path: Path) -> None:
    """
    Fast-forward the current branch from origin.

    Uses --ff-only to refuse merges and surface divergence explicitly.
    """
    _run(["git", "pull", "--ff-only"], repo_path)


def create_branch(repo_path: Path, branch: str) -> None:
    """Create a new branch at the current HEAD and check it out."""
    _run(["git", "checkout", "-b", branch], repo_path)


def push_branch(repo_path: Path, branch: str) -> None:
    """
    Push the branch to origin and configure upstream tracking.

    Never force-pushes.
    """
    _run(["git", "push", "--set-upstream", "origin", branch], repo_path)
