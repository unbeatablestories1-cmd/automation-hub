"""Unit tests for commands/init.py."""
import argparse
import os
import pytest
from pathlib import Path
from unittest.mock import patch


def _args():
    return argparse.Namespace()


def _make_git_repo(parent: Path, name: str) -> Path:
    repo = parent / name
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_writes_config_file(self, tmp_path):
        from commands.init import cmd_init
        _make_git_repo(tmp_path, "repo-a")
        _make_git_repo(tmp_path, "repo-b")

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch("commands.init.get_default_branch", return_value="main"):
                cmd_init(_args())
        finally:
            os.chdir(orig)

        assert (tmp_path / "devctl.yaml").exists()

    def test_all_repos_included(self, tmp_path):
        from commands.init import cmd_init
        _make_git_repo(tmp_path, "repo-a")
        _make_git_repo(tmp_path, "repo-b")
        _make_git_repo(tmp_path, "repo-c")

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch("commands.init.get_default_branch", return_value="main"):
                cmd_init(_args())
        finally:
            os.chdir(orig)

        content = (tmp_path / "devctl.yaml").read_text()
        assert "repo-a:" in content
        assert "repo-b:" in content
        assert "repo-c:" in content

    def test_uses_detected_base_branch(self, tmp_path):
        from commands.init import cmd_init
        _make_git_repo(tmp_path, "my-repo")

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch("commands.init.get_default_branch", return_value="develop"):
                cmd_init(_args())
        finally:
            os.chdir(orig)

        content = (tmp_path / "devctl.yaml").read_text()
        assert "base: develop" in content

    def test_path_uses_relative_dotslash(self, tmp_path):
        from commands.init import cmd_init
        _make_git_repo(tmp_path, "my-repo")

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch("commands.init.get_default_branch", return_value="main"):
                cmd_init(_args())
        finally:
            os.chdir(orig)

        content = (tmp_path / "devctl.yaml").read_text()
        assert "path: ./my-repo" in content

    def test_each_repo_can_have_different_base(self, tmp_path):
        from commands.init import cmd_init
        _make_git_repo(tmp_path, "repo-a")
        _make_git_repo(tmp_path, "repo-b")

        def fake_default(repo_path):
            return "develop" if repo_path.name == "repo-a" else "main"

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch("commands.init.get_default_branch", side_effect=fake_default):
                cmd_init(_args())
        finally:
            os.chdir(orig)

        content = (tmp_path / "devctl.yaml").read_text()
        assert "develop" in content
        assert "main" in content


# ---------------------------------------------------------------------------
# No repos found
# ---------------------------------------------------------------------------

class TestNoReposFound:
    def test_exits_when_no_git_dirs(self, tmp_path):
        from commands.init import cmd_init
        (tmp_path / "not-a-repo").mkdir()

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(SystemExit):
                cmd_init(_args())
        finally:
            os.chdir(orig)

    def test_ignores_plain_files(self, tmp_path):
        from commands.init import cmd_init
        (tmp_path / "README.md").write_text("hello")

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(SystemExit):
                cmd_init(_args())
        finally:
            os.chdir(orig)

    def test_ignores_dirs_without_dot_git(self, tmp_path):
        from commands.init import cmd_init
        (tmp_path / "some-dir").mkdir()

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(SystemExit):
                cmd_init(_args())
        finally:
            os.chdir(orig)


# ---------------------------------------------------------------------------
# Overwrite
# ---------------------------------------------------------------------------

class TestOverwrite:
    def test_overwrites_existing_config(self, tmp_path):
        from commands.init import cmd_init
        (tmp_path / "devctl.yaml").write_text("old: content\n")
        _make_git_repo(tmp_path, "repo-a")

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch("commands.init.get_default_branch", return_value="main"):
                cmd_init(_args())
        finally:
            os.chdir(orig)

        content = (tmp_path / "devctl.yaml").read_text()
        assert "old: content" not in content
        assert "repo-a" in content


# ---------------------------------------------------------------------------
# Config is valid after init (round-trip with load_config)
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_generated_config_is_loadable(self, tmp_path):
        """Config written by init must be parseable by load_config."""
        from commands.init import cmd_init
        from config import load_config

        _make_git_repo(tmp_path, "repo-a")
        _make_git_repo(tmp_path, "repo-b")

        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch("commands.init.get_default_branch", return_value="main"):
                cmd_init(_args())
            config = load_config(str(tmp_path / "devctl.yaml"))
        finally:
            os.chdir(orig)

        assert "repo-a" in config["repos"]
        assert "repo-b" in config["repos"]
        assert config["repos"]["repo-a"]["base"] == "main"
