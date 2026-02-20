"""Unit tests for commands/status.py — all git I/O is mocked."""
import argparse
import io
import sys
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from commands.status import cmd_status
from git_ops import GitError


def _args(repos=None):
    return argparse.Namespace(repos=repos)


FAKE_CONFIG = {
    "repos": {
        "pipeline": {"path": "/p", "_resolved_path": "/p", "base": "main"},
        "svc":      {"path": "/s", "_resolved_path": "/s", "base": "main"},
    },
    "github": {"owner": "o", "repo": "r", "workflow_file": "f.yml"},
}

FAKE_STATE = {"ticket": "ABC-1", "branch": "feature/ABC-1", "base_override": None}


# ---------------------------------------------------------------------------
# All-good scenario
# ---------------------------------------------------------------------------

class TestAllGood:
    @patch("commands.status.is_working_tree_clean", return_value=True)
    @patch("commands.status.remote_branch_exists", return_value=True)
    @patch("commands.status.get_current_branch", return_value="feature/ABC-1")
    @patch("commands.status.load_state", return_value=FAKE_STATE)
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_exits_0(self, *mocks):
        cmd_status(_args())  # must not raise

    @patch("commands.status.is_working_tree_clean", return_value=True)
    @patch("commands.status.remote_branch_exists", return_value=True)
    @patch("commands.status.get_current_branch", return_value="feature/ABC-1")
    @patch("commands.status.load_state", return_value=FAKE_STATE)
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_check_marks_in_output(self, *mocks):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_status(_args())
        out = buf.getvalue()
        assert "✔" in out
        assert "✘" not in out


# ---------------------------------------------------------------------------
# Dirty working tree
# ---------------------------------------------------------------------------

class TestDirtyWorkingTree:
    @patch("commands.status.is_working_tree_clean", return_value=False)
    @patch("commands.status.remote_branch_exists", return_value=True)
    @patch("commands.status.get_current_branch", return_value="feature/ABC-1")
    @patch("commands.status.load_state", return_value=FAKE_STATE)
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_exits_1(self, *mocks):
        with pytest.raises(SystemExit) as exc_info:
            cmd_status(_args())
        assert exc_info.value.code == 1

    @patch("commands.status.is_working_tree_clean", return_value=False)
    @patch("commands.status.remote_branch_exists", return_value=True)
    @patch("commands.status.get_current_branch", return_value="feature/ABC-1")
    @patch("commands.status.load_state", return_value=FAKE_STATE)
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_x_mark_shown(self, *mocks):
        buf = io.StringIO()
        with redirect_stdout(buf):
            with pytest.raises(SystemExit):
                cmd_status(_args())
        assert "✘" in buf.getvalue()


# ---------------------------------------------------------------------------
# Wrong branch
# ---------------------------------------------------------------------------

class TestWrongBranch:
    @patch("commands.status.is_working_tree_clean", return_value=True)
    @patch("commands.status.remote_branch_exists", return_value=True)
    @patch("commands.status.get_current_branch", return_value="main")  # wrong
    @patch("commands.status.load_state", return_value=FAKE_STATE)
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_exits_1(self, *mocks):
        with pytest.raises(SystemExit) as exc_info:
            cmd_status(_args())
        assert exc_info.value.code == 1

    @patch("commands.status.is_working_tree_clean", return_value=True)
    @patch("commands.status.remote_branch_exists", return_value=True)
    @patch("commands.status.get_current_branch", return_value="main")
    @patch("commands.status.load_state", return_value=FAKE_STATE)
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_expected_branch_shown(self, *mocks):
        buf = io.StringIO()
        with redirect_stdout(buf):
            with pytest.raises(SystemExit):
                cmd_status(_args())
        assert "feature/ABC-1" in buf.getvalue()  # expected branch shown as note


# ---------------------------------------------------------------------------
# Missing remote branch
# ---------------------------------------------------------------------------

class TestMissingRemote:
    @patch("commands.status.is_working_tree_clean", return_value=True)
    @patch("commands.status.remote_branch_exists", return_value=False)
    @patch("commands.status.get_current_branch", return_value="feature/ABC-1")
    @patch("commands.status.load_state", return_value=FAKE_STATE)
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_exits_1(self, *mocks):
        with pytest.raises(SystemExit) as exc_info:
            cmd_status(_args())
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# GitError per repo
# ---------------------------------------------------------------------------

class TestGitError:
    @patch("commands.status.is_working_tree_clean")
    @patch("commands.status.remote_branch_exists")
    @patch("commands.status.get_current_branch", side_effect=GitError("no git"))
    @patch("commands.status.load_state", return_value=FAKE_STATE)
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_exits_1_on_git_error(self, *mocks):
        with pytest.raises(SystemExit) as exc_info:
            cmd_status(_args())
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# --repos filtering
# ---------------------------------------------------------------------------

class TestReposFilter:
    @patch("commands.status.is_working_tree_clean", return_value=True)
    @patch("commands.status.remote_branch_exists", return_value=True)
    @patch("commands.status.get_current_branch", return_value="ABC-1")
    @patch("commands.status.load_state", return_value={"ticket": "ABC-1", "branch": "ABC-1", "base_override": None})
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_only_specified_repo_checked(self, mock_cfg, mock_state, mock_branch, mock_remote, mock_clean):
        cmd_status(_args(repos=["pipeline"]))
        # get_current_branch called once (pipeline only), not twice
        assert mock_branch.call_count == 1

    @patch("commands.status.load_state", return_value={"ticket": "ABC-1", "branch": "ABC-1", "base_override": None})
    @patch("commands.status.load_config", return_value=FAKE_CONFIG)
    def test_unknown_repo_exits(self, mock_cfg, mock_state):
        with pytest.raises(SystemExit):
            cmd_status(_args(repos=["nonexistent"]))
