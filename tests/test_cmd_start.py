"""Unit tests for commands/start.py — all git I/O is mocked."""
import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from commands.start import cmd_start
from git_ops import GitError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _args(ticket="TST-1", base=None, force=False, repos=None):
    return argparse.Namespace(ticket=ticket, base=base, force=force, repos=repos)


FAKE_CONFIG = {
    "repos": {
        "repo-a": {"path": "/fake/a", "_resolved_path": "/fake/a", "base": "main"},
        "repo-b": {"path": "/fake/b", "_resolved_path": "/fake/b", "base": "main"},
    },
    "github": {"owner": "org", "repo": "pipeline", "workflow_file": "ci.yml"},
}

FAKE_CONFIG_ONE = {
    "repos": {
        "only": {"path": "/fake/o", "_resolved_path": "/fake/o", "base": "main"},
    },
    "github": {"owner": "o", "repo": "r", "workflow_file": "f.yml"},
}


# ---------------------------------------------------------------------------
# Happy-path: normal branch creation
# ---------------------------------------------------------------------------

class TestHappyPath:
    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.create_branch")
    @patch("commands.start.pull_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.remote_branch_exists", return_value=False)
    @patch("commands.start.local_branch_exists", return_value=False)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG_ONE)
    def test_full_sequence_called(
        self, mock_cfg, mock_fetch, mock_local, mock_remote,
        mock_checkout, mock_pull, mock_create, mock_push, mock_write,
    ):
        cmd_start(_args())

        p = Path("/fake/o")
        mock_fetch.assert_called_once_with(p)
        mock_checkout.assert_called_once_with(p, "main")
        mock_pull.assert_called_once_with(p)
        mock_create.assert_called_once_with(p, "TST-1")
        mock_push.assert_called_once_with(p, "TST-1")
        mock_write.assert_called_once_with("TST-1", "TST-1", None)

    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.create_branch")
    @patch("commands.start.pull_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.remote_branch_exists", return_value=False)
    @patch("commands.start.local_branch_exists", return_value=False)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG)
    def test_all_repos_processed(
        self, mock_cfg, mock_fetch, mock_local, mock_remote,
        mock_checkout, mock_pull, mock_create, mock_push, mock_write,
    ):
        cmd_start(_args())
        assert mock_fetch.call_count == 2
        assert mock_create.call_count == 2
        assert mock_push.call_count == 2

    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.create_branch")
    @patch("commands.start.pull_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.remote_branch_exists", return_value=False)
    @patch("commands.start.local_branch_exists", return_value=False)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG_ONE)
    def test_base_override_used_for_checkout(
        self, mock_cfg, mock_fetch, mock_local, mock_remote,
        mock_checkout, mock_pull, mock_create, mock_push, mock_write,
    ):
        cmd_start(_args(base="develop"))
        mock_checkout.assert_called_once_with(Path("/fake/o"), "develop")
        mock_write.assert_called_once_with("TST-1", "TST-1", "develop")


# ---------------------------------------------------------------------------
# Existing local branch — no --force
# ---------------------------------------------------------------------------

class TestExistingLocalNoForce:
    @patch("commands.start.write_state")
    @patch("commands.start.local_branch_exists", return_value=True)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG_ONE)
    def test_exits_1(self, mock_cfg, mock_fetch, mock_local, mock_write):
        with pytest.raises(SystemExit) as exc_info:
            cmd_start(_args(force=False))
        assert exc_info.value.code == 1

    @patch("commands.start.write_state")
    @patch("commands.start.local_branch_exists", return_value=True)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG_ONE)
    def test_state_not_written_on_error(self, mock_cfg, mock_fetch, mock_local, mock_write):
        with pytest.raises(SystemExit):
            cmd_start(_args(force=False))
        mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# Existing local branch — with --force
# ---------------------------------------------------------------------------

class TestExistingLocalWithForce:
    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.local_branch_exists", return_value=True)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG_ONE)
    def test_checks_out_and_pushes_existing(
        self, mock_cfg, mock_fetch, mock_local, mock_checkout, mock_push, mock_write,
    ):
        cmd_start(_args(force=True))
        mock_checkout.assert_called_once_with(Path("/fake/o"), "TST-1")
        mock_push.assert_called_once_with(Path("/fake/o"), "TST-1")
        mock_write.assert_called_once()

    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.local_branch_exists", return_value=True)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG_ONE)
    def test_does_not_create_new_branch(
        self, mock_cfg, mock_fetch, mock_local, mock_checkout, mock_push, mock_write,
    ):
        with patch("commands.start.create_branch") as mock_create:
            cmd_start(_args(force=True))
            mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# Existing remote branch — warning, but continues
# ---------------------------------------------------------------------------

class TestExistingRemoteBranch:
    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.create_branch")
    @patch("commands.start.pull_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.remote_branch_exists", return_value=True)
    @patch("commands.start.local_branch_exists", return_value=False)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG_ONE)
    def test_does_not_exit(
        self, mock_cfg, mock_fetch, mock_local, mock_remote,
        mock_checkout, mock_pull, mock_create, mock_push, mock_write,
    ):
        cmd_start(_args())  # should NOT raise
        mock_write.assert_called_once()

    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.create_branch")
    @patch("commands.start.pull_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.remote_branch_exists", return_value=True)
    @patch("commands.start.local_branch_exists", return_value=False)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG_ONE)
    def test_still_creates_and_pushes(
        self, mock_cfg, mock_fetch, mock_local, mock_remote,
        mock_checkout, mock_pull, mock_create, mock_push, mock_write,
    ):
        cmd_start(_args())
        mock_create.assert_called_once()
        mock_push.assert_called_once()


# ---------------------------------------------------------------------------
# GitError handling
# ---------------------------------------------------------------------------

class TestGitErrorHandling:
    @patch("commands.start.write_state")
    @patch("commands.start.fetch_origin", side_effect=GitError("network down"))
    @patch("commands.start.load_config", return_value=FAKE_CONFIG_ONE)
    def test_git_error_causes_exit_1(self, mock_cfg, mock_fetch, mock_write):  # noqa: E501
        with pytest.raises(SystemExit) as exc_info:
            cmd_start(_args())
        assert exc_info.value.code == 1

    @patch("commands.start.write_state")
    @patch("commands.start.push_branch", side_effect=[None, GitError("push failed")])
    @patch("commands.start.create_branch")
    @patch("commands.start.pull_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.remote_branch_exists", return_value=False)
    @patch("commands.start.local_branch_exists", return_value=False)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG)
    def test_first_repo_succeeds_second_fails_exits_1(
        self, mock_cfg, mock_fetch, mock_local, mock_remote,
        mock_checkout, mock_pull, mock_create, mock_push, mock_write,
    ):
        with pytest.raises(SystemExit) as exc_info:
            cmd_start(_args())
        assert exc_info.value.code == 1
        mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# --repos filtering
# ---------------------------------------------------------------------------

class TestReposFilter:
    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.create_branch")
    @patch("commands.start.pull_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.remote_branch_exists", return_value=False)
    @patch("commands.start.local_branch_exists", return_value=False)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG)
    def test_only_specified_repos_processed(
        self, mock_cfg, mock_fetch, mock_local, mock_remote,
        mock_checkout, mock_pull, mock_create, mock_push, mock_write,
    ):
        cmd_start(_args(repos=["repo-a"]))
        # fetch only called once (for repo-a), not twice
        assert mock_fetch.call_count == 1
        mock_fetch.assert_called_once_with(Path("/fake/a"))

    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.create_branch")
    @patch("commands.start.pull_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.remote_branch_exists", return_value=False)
    @patch("commands.start.local_branch_exists", return_value=False)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG)
    def test_multiple_repos_filter(
        self, mock_cfg, mock_fetch, mock_local, mock_remote,
        mock_checkout, mock_pull, mock_create, mock_push, mock_write,
    ):
        cmd_start(_args(repos=["repo-a", "repo-b"]))
        assert mock_fetch.call_count == 2

    @patch("commands.start.write_state")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG)
    def test_unknown_repo_exits(self, mock_cfg, mock_write):
        with pytest.raises(SystemExit):
            cmd_start(_args(repos=["nonexistent"]))
        mock_write.assert_not_called()

    @patch("commands.start.write_state")
    @patch("commands.start.push_branch")
    @patch("commands.start.create_branch")
    @patch("commands.start.pull_branch")
    @patch("commands.start.checkout_branch")
    @patch("commands.start.remote_branch_exists", return_value=False)
    @patch("commands.start.local_branch_exists", return_value=False)
    @patch("commands.start.fetch_origin")
    @patch("commands.start.load_config", return_value=FAKE_CONFIG)
    def test_no_filter_processes_all(
        self, mock_cfg, mock_fetch, mock_local, mock_remote,
        mock_checkout, mock_pull, mock_create, mock_push, mock_write,
    ):
        cmd_start(_args(repos=None))
        assert mock_fetch.call_count == 2
