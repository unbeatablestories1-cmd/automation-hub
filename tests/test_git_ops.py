"""
Unit tests for git_ops.py.

Uses real git repositories created in temporary directories so git behaviour
is exercised exactly as the production code sees it.  Every test is
self-contained and leaves no state outside its tmp_path.
"""
import os
import subprocess
from pathlib import Path

import pytest

from git_ops import (
    GitError,
    checkout_branch,
    create_branch,
    fetch_origin,
    get_current_branch,
    is_working_tree_clean,
    local_branch_exists,
    pull_branch,
    push_branch,
    remote_branch_exists,
)

# ---------------------------------------------------------------------------
# Shared git environment — stable author/committer identity for all test runs
# ---------------------------------------------------------------------------
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@devctl.test",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@devctl.test",
}


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        env=GIT_ENV,
        text=True,
    )


def _make_bare(path: Path) -> Path:
    """Init a bare repo (acts as 'origin')."""
    path.mkdir(parents=True, exist_ok=True)
    _git(path.parent, "init", "--bare", "-b", "main", str(path))
    return path


def _clone(bare: Path, dest: Path) -> Path:
    """Clone bare repo to dest and configure identity."""
    _git(bare.parent, "clone", str(bare), str(dest))
    _git(dest, "config", "user.email", "test@devctl.test")
    _git(dest, "config", "user.name", "Test")
    return dest


def _initial_commit(work: Path, filename: str = "README.md") -> None:
    """Add a file and commit on whatever branch is current."""
    (work / filename).write_text("init")
    _git(work, "add", ".")
    _git(work, "commit", "-m", "init")


@pytest.fixture()
def local_repo(tmp_path: Path) -> Path:
    """A git repo with one commit but NO remote."""
    repo = tmp_path / "local"
    repo.mkdir()
    _git(repo.parent, "init", "-b", "main", str(repo))
    _git(repo, "config", "user.email", "test@devctl.test")
    _git(repo, "config", "user.name", "Test")
    _initial_commit(repo)
    return repo


@pytest.fixture()
def repo_pair(tmp_path: Path):
    """
    Returns (bare_path, work_path).

    bare_path — the bare 'remote' origin
    work_path — a working clone with one commit pushed to origin/main
    """
    bare = _make_bare(tmp_path / "origin.git")
    work = _clone(bare, tmp_path / "work")
    _initial_commit(work)
    _git(work, "push", "origin", "HEAD:main")
    _git(work, "branch", "--set-upstream-to=origin/main", "main")
    return bare, work


# ---------------------------------------------------------------------------
# get_current_branch
# ---------------------------------------------------------------------------

class TestGetCurrentBranch:
    def test_returns_branch_name(self, local_repo):
        assert get_current_branch(local_repo) == "main"

    def test_detached_head_raises(self, local_repo):
        # Detach HEAD by checking out the commit hash directly
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(local_repo), capture_output=True, text=True,
        )
        sha = result.stdout.strip()
        _git(local_repo, "checkout", "--detach", sha)
        with pytest.raises(GitError, match="detached"):
            get_current_branch(local_repo)

    def test_different_branch_name(self, local_repo):
        _git(local_repo, "checkout", "-b", "my-feature")
        assert get_current_branch(local_repo) == "my-feature"


# ---------------------------------------------------------------------------
# local_branch_exists
# ---------------------------------------------------------------------------

class TestLocalBranchExists:
    def test_existing_branch_returns_true(self, local_repo):
        assert local_branch_exists(local_repo, "main") is True

    def test_absent_branch_returns_false(self, local_repo):
        assert local_branch_exists(local_repo, "no-such-branch") is False

    def test_created_branch_found(self, local_repo):
        _git(local_repo, "checkout", "-b", "new-branch")
        assert local_branch_exists(local_repo, "new-branch") is True


# ---------------------------------------------------------------------------
# remote_branch_exists
# ---------------------------------------------------------------------------

class TestRemoteBranchExists:
    def test_pushed_branch_found(self, repo_pair):
        _, work = repo_pair
        assert remote_branch_exists(work, "main") is True

    def test_absent_branch_returns_false(self, repo_pair):
        _, work = repo_pair
        assert remote_branch_exists(work, "no-such-branch") is False

    def test_newly_pushed_branch_found(self, repo_pair):
        bare, work = repo_pair
        _git(work, "checkout", "-b", "feat-x")
        _git(work, "push", "origin", "feat-x")
        assert remote_branch_exists(work, "feat-x") is True


# ---------------------------------------------------------------------------
# is_working_tree_clean
# ---------------------------------------------------------------------------

class TestIsWorkingTreeClean:
    def test_clean_repo(self, local_repo):
        assert is_working_tree_clean(local_repo) is True

    def test_untracked_file_is_dirty(self, local_repo):
        (local_repo / "new.txt").write_text("hello")
        assert is_working_tree_clean(local_repo) is False

    def test_staged_change_is_dirty(self, local_repo):
        (local_repo / "README.md").write_text("changed")
        _git(local_repo, "add", ".")
        assert is_working_tree_clean(local_repo) is False

    def test_modified_tracked_file_is_dirty(self, local_repo):
        (local_repo / "README.md").write_text("changed but not staged")
        assert is_working_tree_clean(local_repo) is False


# ---------------------------------------------------------------------------
# fetch_origin
# ---------------------------------------------------------------------------

class TestFetchOrigin:
    def test_fetch_succeeds(self, repo_pair):
        _, work = repo_pair
        fetch_origin(work)  # should not raise

    def test_fetch_picks_up_new_remote_branch(self, repo_pair):
        bare, work = repo_pair
        # Create a branch directly in the bare repo by pushing from a second clone
        work2 = work.parent / "work2"
        _clone(bare, work2)
        _git(work2, "config", "user.email", "test@devctl.test")
        _git(work2, "config", "user.name", "Test")
        _git(work2, "checkout", "-b", "new-branch")
        (work2 / "f.txt").write_text("hi")
        _git(work2, "add", ".")
        _git(work2, "commit", "-m", "add")
        _git(work2, "push", "origin", "new-branch")

        fetch_origin(work)
        # After fetch, the remote-tracking branch should exist
        result = subprocess.run(
            ["git", "branch", "-r"],
            cwd=str(work), capture_output=True, text=True,
        )
        assert "new-branch" in result.stdout


# ---------------------------------------------------------------------------
# checkout_branch
# ---------------------------------------------------------------------------

class TestCheckoutBranch:
    def test_checkout_existing_branch(self, local_repo):
        _git(local_repo, "checkout", "-b", "other")
        _git(local_repo, "checkout", "main")
        checkout_branch(local_repo, "other")
        assert get_current_branch(local_repo) == "other"

    def test_checkout_nonexistent_raises(self, local_repo):
        with pytest.raises(GitError):
            checkout_branch(local_repo, "no-such-branch")


# ---------------------------------------------------------------------------
# pull_branch
# ---------------------------------------------------------------------------

class TestPullBranch:
    def test_pull_no_op_when_up_to_date(self, repo_pair):
        _, work = repo_pair
        pull_branch(work)  # should not raise

    def test_pull_brings_in_new_commit(self, repo_pair):
        bare, work = repo_pair
        # Push a new commit from a second clone
        work2 = work.parent / "work2"
        _clone(bare, work2)
        _git(work2, "config", "user.email", "t@t.com")
        _git(work2, "config", "user.name", "T")
        (work2 / "extra.txt").write_text("extra")
        _git(work2, "add", ".")
        _git(work2, "commit", "-m", "extra commit")
        _git(work2, "push", "origin", "main")

        fetch_origin(work)
        pull_branch(work)

        result = subprocess.run(
            ["git", "log", "--oneline", "-2"],
            cwd=str(work), capture_output=True, text=True,
        )
        assert "extra commit" in result.stdout


# ---------------------------------------------------------------------------
# create_branch
# ---------------------------------------------------------------------------

class TestCreateBranch:
    def test_creates_and_checks_out_branch(self, local_repo):
        create_branch(local_repo, "feature/new")
        assert get_current_branch(local_repo) == "feature/new"
        assert local_branch_exists(local_repo, "feature/new")

    def test_duplicate_branch_raises(self, local_repo):
        create_branch(local_repo, "dup")
        _git(local_repo, "checkout", "main")
        with pytest.raises(GitError):
            create_branch(local_repo, "dup")


# ---------------------------------------------------------------------------
# push_branch
# ---------------------------------------------------------------------------

class TestPushBranch:
    def test_push_creates_remote_branch(self, repo_pair):
        _, work = repo_pair
        _git(work, "checkout", "-b", "feature/push-test")
        push_branch(work, "feature/push-test")
        assert remote_branch_exists(work, "feature/push-test")

    def test_push_sets_upstream_tracking(self, repo_pair):
        _, work = repo_pair
        _git(work, "checkout", "-b", "feature/track-me")
        push_branch(work, "feature/track-me")
        # After push --set-upstream, git status should not complain about no upstream
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=str(work), capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "origin/feature/track-me" in result.stdout


# ---------------------------------------------------------------------------
# GitError
# ---------------------------------------------------------------------------

class TestGitError:
    def test_bad_checkout_raises_git_error(self, local_repo):
        with pytest.raises(GitError):
            checkout_branch(local_repo, "totally-missing")

    def test_create_duplicate_raises_git_error(self, local_repo):
        create_branch(local_repo, "unique")
        _git(local_repo, "checkout", "main")
        with pytest.raises(GitError):
            create_branch(local_repo, "unique")
