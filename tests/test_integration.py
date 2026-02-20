"""
Integration tests for devctl.

Creates real git repositories in temporary directories so the full
start → status flow is exercised end-to-end.  Every test case is
isolated in its own directory tree.

Key scenario: branching from a non-main base branch (e.g. 'develop').
"""
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Git helper environment — stable identity so commits always work
# ---------------------------------------------------------------------------
_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "devctl-test",
    "GIT_AUTHOR_EMAIL": "devctl@test.local",
    "GIT_COMMITTER_NAME": "devctl-test",
    "GIT_COMMITTER_EMAIL": "devctl@test.local",
}


def _g(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command, raise on failure."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        env=_GIT_ENV,
        text=True,
    )


def _git_out(cwd: Path, *args: str) -> str:
    return _g(cwd, *args).stdout.strip()


# ---------------------------------------------------------------------------
# Fixture: a complete multi-repo environment
# ---------------------------------------------------------------------------

class RepoEnv:
    """
    A self-contained set of git repositories under a single tmpdir.

    Layout:
        tmpdir/
          <name>.git/     bare remote (origin)
          <name>/         working clone

        tmpdir/devctl.yaml
        tmpdir/.devctl-state.yaml  (written by devctl start)
    """

    def __init__(self, repo_names: list[str], base_branch: str = "main"):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="devctl-integ-"))
        self._orig_cwd = os.getcwd()
        self.repo_names = repo_names
        self.base_branch = base_branch
        self.repos: dict[str, dict[str, Path]] = {}

    # ------------------------------------------------------------------
    def setup(self) -> "RepoEnv":
        for name in self.repo_names:
            self._init_repo(name)
        self._write_config(self.base_branch)
        # cd into tmpdir — devctl looks for devctl.yaml in CWD
        os.chdir(str(self.tmpdir))
        return self

    def _init_repo(self, name: str) -> None:
        bare = self.tmpdir / f"{name}.git"
        work = self.tmpdir / name

        # bare remote
        bare.mkdir()
        _g(bare.parent, "init", "--bare", "-b", "main", str(bare))

        # working clone
        _g(self.tmpdir, "clone", str(bare), str(work))
        _g(work, "config", "user.email", "devctl@test.local")
        _g(work, "config", "user.name", "devctl-test")

        # Initial commit on main
        (work / "README.md").write_text(f"# {name}")
        _g(work, "add", ".")
        _g(work, "commit", "-m", f"init {name}")
        _g(work, "push", "origin", "HEAD:main")
        _g(work, "branch", "--set-upstream-to=origin/main", "main")

        self.repos[name] = {"bare": bare, "work": work}

    def add_develop_branch(self, extra_commit: bool = True) -> None:
        """
        Create a 'develop' branch in every repo, optionally with an extra
        commit so that develop and main have diverged.
        """
        for name, paths in self.repos.items():
            work = paths["work"]
            _g(work, "checkout", "-b", "develop")
            if extra_commit:
                (work / "dev-file.txt").write_text(f"develop work in {name}")
                _g(work, "add", ".")
                _g(work, "commit", "-m", f"develop commit in {name}")
            _g(work, "push", "origin", "develop")
            _g(work, "branch", "--set-upstream-to=origin/develop", "develop")
            # Return to main so repos start in a known state
            _g(work, "checkout", "main")

    def _write_config(self, base: str) -> None:
        lines = ["repos:\n"]
        for name, paths in self.repos.items():
            lines.append(f"  {name}:\n")
            lines.append(f"    path: {paths['work']}\n")
            lines.append(f"    base: {base}\n")
        lines += [
            "github:\n",
            "  owner: test-org\n",
            "  repo: pipeline\n",
            "  workflow_file: caller.yml\n",
        ]
        (self.tmpdir / "devctl.yaml").write_text("".join(lines))

    # ------------------------------------------------------------------
    def teardown(self) -> None:
        os.chdir(self._orig_cwd)
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def work(self, name: str) -> Path:
        return self.repos[name]["work"]

    def current_branch(self, name: str) -> str:
        return _git_out(self.work(name), "rev-parse", "--abbrev-ref", "HEAD")

    def branch_sha(self, name: str, branch: str) -> str:
        return _git_out(self.work(name), "rev-parse", branch)

    def remote_has_branch(self, name: str, branch: str) -> bool:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch],
            cwd=str(self.work(name)),
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())

    def state_file(self) -> Path:
        return self.tmpdir / ".devctl-state.yaml"


@pytest.fixture()
def env2(request):
    """2-repo environment, base=main."""
    e = RepoEnv(["pipeline", "svc"]).setup()
    yield e
    e.teardown()


@pytest.fixture()
def env2_develop(request):
    """2-repo environment with a develop branch (extra commit beyond main)."""
    e = RepoEnv(["pipeline", "svc"], base_branch="develop").setup()
    e.add_develop_branch(extra_commit=True)
    yield e
    e.teardown()


# ---------------------------------------------------------------------------
# Helpers to build Namespace args
# ---------------------------------------------------------------------------

def _start_args(ticket: str, base=None, force=False) -> argparse.Namespace:
    return argparse.Namespace(ticket=ticket, base=base, force=force)


def _status_args() -> argparse.Namespace:
    return argparse.Namespace()


# ---------------------------------------------------------------------------
# 1. Basic start on main
# ---------------------------------------------------------------------------

class TestStartOnMain:
    def test_branches_created_locally(self, env2):
        from commands.start import cmd_start
        cmd_start(_start_args("MAIN-1"))
        assert env2.current_branch("pipeline") == "MAIN-1"
        assert env2.current_branch("svc") == "MAIN-1"

    def test_branches_pushed_to_remote(self, env2):
        from commands.start import cmd_start
        cmd_start(_start_args("MAIN-2"))
        assert env2.remote_has_branch("pipeline", "MAIN-2")
        assert env2.remote_has_branch("svc", "MAIN-2")

    def test_state_file_written(self, env2):
        from commands.start import cmd_start
        cmd_start(_start_args("MAIN-3"))
        assert env2.state_file().exists()
        text = env2.state_file().read_text()
        assert "ticket: MAIN-3" in text
        assert "branch: MAIN-3" in text

    def test_branch_name_matches_ticket(self, env2):
        from commands.start import cmd_start
        cmd_start(_start_args("TST-99"))
        assert env2.current_branch("pipeline") == "TST-99"


# ---------------------------------------------------------------------------
# 2. Start on non-main base branch (--base develop)
# ---------------------------------------------------------------------------

class TestStartOnDevelopViaFlag:
    def test_branches_created_on_develop(self, env2_develop):
        from commands.start import cmd_start
        cmd_start(_start_args("DEV-1", base="develop"))
        assert env2_develop.current_branch("pipeline") == "DEV-1"
        assert env2_develop.current_branch("svc") == "DEV-1"

    def test_feature_branch_has_develop_as_parent(self, env2_develop):
        """
        DEV-2 should point to the same commit as develop (no extra
        commits added), confirming it was branched from develop not main.
        """
        from commands.start import cmd_start
        cmd_start(_start_args("DEV-2", base="develop"))

        for repo in ["pipeline", "svc"]:
            feature_sha = env2_develop.branch_sha(repo, "DEV-2")
            develop_sha = env2_develop.branch_sha(repo, "develop")
            assert feature_sha == develop_sha, (
                f"{repo}: DEV-2 ({feature_sha[:7]}) should point to "
                f"develop ({develop_sha[:7]})"
            )

    def test_feature_branch_not_at_main(self, env2_develop):
        """
        main and develop have diverged — DEV-3 must NOT equal main.
        """
        from commands.start import cmd_start
        cmd_start(_start_args("DEV-3", base="develop"))

        for repo in ["pipeline", "svc"]:
            feature_sha = env2_develop.branch_sha(repo, "DEV-3")
            main_sha    = env2_develop.branch_sha(repo, "main")
            assert feature_sha != main_sha, (
                f"{repo}: DEV-3 should NOT equal main when develop has "
                f"extra commits"
            )

    def test_base_override_written_to_state(self, env2_develop):
        from commands.start import cmd_start
        cmd_start(_start_args("DEV-4", base="develop"))
        text = env2_develop.state_file().read_text()
        assert "base_override: develop" in text


# ---------------------------------------------------------------------------
# 3. Start on non-main base from config (no --base flag)
# ---------------------------------------------------------------------------

class TestStartOnDevelopViaConfig:
    def test_branches_from_config_base(self, env2_develop):
        """devctl.yaml has base: develop — start without --base should honour it."""
        from commands.start import cmd_start
        # env2_develop already has base_branch='develop' in devctl.yaml
        cmd_start(_start_args("CFG-1"))

        for repo in ["pipeline", "svc"]:
            feature_sha = env2_develop.branch_sha(repo, "CFG-1")
            develop_sha = env2_develop.branch_sha(repo, "develop")
            assert feature_sha == develop_sha, (
                f"{repo}: CFG-1 should equal develop SHA when config says develop"
            )

    def test_base_override_is_null_in_state(self, env2_develop):
        from commands.start import cmd_start
        cmd_start(_start_args("CFG-2"))
        text = env2_develop.state_file().read_text()
        assert "base_override: null" in text


# ---------------------------------------------------------------------------
# 4. Status after a successful start
# ---------------------------------------------------------------------------

class TestStatusAfterStart:
    def test_exits_0_when_all_clean(self, env2):
        from commands.start import cmd_start
        from commands.status import cmd_status
        cmd_start(_start_args("STS-1"))
        cmd_status(_status_args())  # must not raise

    def test_exits_1_when_one_repo_dirty(self, env2):
        from commands.start import cmd_start
        from commands.status import cmd_status
        cmd_start(_start_args("STS-2"))
        # Dirty one repo
        (env2.work("svc") / "dirty.txt").write_text("uncommitted")
        with pytest.raises(SystemExit) as exc_info:
            cmd_status(_status_args())
        assert exc_info.value.code == 1

    def test_exits_1_when_on_wrong_branch(self, env2):
        from commands.start import cmd_start
        from commands.status import cmd_status
        cmd_start(_start_args("STS-3"))
        # Manually switch one repo back to main
        _g(env2.work("pipeline"), "checkout", "main")
        with pytest.raises(SystemExit) as exc_info:
            cmd_status(_status_args())
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# 5. Existing branch guards
# ---------------------------------------------------------------------------

class TestExistingBranchGuards:
    def test_error_without_force_if_local_branch_exists(self, env2):
        from commands.start import cmd_start
        cmd_start(_start_args("DUP-1"))
        # Switch back to main so we can try again
        for name in env2.repo_names:
            _g(env2.work(name), "checkout", "main")
        with pytest.raises(SystemExit) as exc_info:
            cmd_start(_start_args("DUP-1"))
        assert exc_info.value.code == 1

    def test_force_flag_succeeds_on_existing_branch(self, env2):
        from commands.start import cmd_start
        cmd_start(_start_args("FRC-1"))
        for name in env2.repo_names:
            _g(env2.work(name), "checkout", "main")
        # Should not raise
        cmd_start(_start_args("FRC-1", force=True))
        assert env2.current_branch("pipeline") == "FRC-1"
        assert env2.current_branch("svc") == "FRC-1"

