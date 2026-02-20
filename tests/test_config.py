"""Unit tests for config.py."""
import pytest
from pathlib import Path

from config import _parse_minimal_yaml, load_config


# ---------------------------------------------------------------------------
# _parse_minimal_yaml
# ---------------------------------------------------------------------------

class TestMinimalYamlParser:
    def test_flat_string(self):
        assert _parse_minimal_yaml("key: value\n") == {"key": "value"}

    def test_flat_integer(self):
        assert _parse_minimal_yaml("count: 42\n") == {"count": 42}

    def test_flat_float(self):
        assert _parse_minimal_yaml("ratio: 3.14\n") == {"ratio": 3.14}

    def test_null_literal(self):
        assert _parse_minimal_yaml("key: null\n") == {"key": None}

    def test_tilde_null(self):
        assert _parse_minimal_yaml("key: ~\n") == {"key": None}

    def test_bool_true(self):
        assert _parse_minimal_yaml("flag: true\n") == {"flag": True}

    def test_bool_false(self):
        assert _parse_minimal_yaml("flag: false\n") == {"flag": False}

    def test_empty_lines_skipped(self):
        text = "\n\nkey: val\n\n"
        assert _parse_minimal_yaml(text) == {"key": "val"}

    def test_comment_lines_skipped(self):
        text = "# comment\nkey: val\n"
        assert _parse_minimal_yaml(text) == {"key": "val"}

    def test_inline_comment_stripped(self):
        assert _parse_minimal_yaml("key: val # comment\n") == {"key": "val"}

    def test_nested_two_levels(self):
        text = "outer:\n  inner: val\n"
        assert _parse_minimal_yaml(text) == {"outer": {"inner": "val"}}

    def test_nested_three_levels(self):
        text = "a:\n  b:\n    c: deep\n"
        assert _parse_minimal_yaml(text) == {"a": {"b": {"c": "deep"}}}

    def test_multiple_siblings(self):
        text = "repos:\n  alpha:\n    path: /a\n    base: main\n  beta:\n    path: /b\n    base: develop\n"
        result = _parse_minimal_yaml(text)
        assert result["repos"]["alpha"]["path"] == "/a"
        assert result["repos"]["beta"]["base"] == "develop"

    def test_full_devctl_config(self):
        text = (
            "repos:\n"
            "  pipeline:\n"
            "    path: ../pipeline\n"
            "    base: main\n"
            "  svc:\n"
            "    path: ../svc\n"
            "    base: develop\n"
            "github:\n"
            "  owner: my-org\n"
            "  repo: pipeline\n"
            "  workflow_file: caller.yml\n"
        )
        result = _parse_minimal_yaml(text)
        assert result["repos"]["pipeline"]["path"] == "../pipeline"
        assert result["repos"]["svc"]["base"] == "develop"
        assert result["github"]["owner"] == "my-org"
        assert result["github"]["workflow_file"] == "caller.yml"

    def test_hyphenated_key(self):
        text = "python-service:\n  path: /x\n"
        result = _parse_minimal_yaml(text)
        assert result["python-service"]["path"] == "/x"

    def test_empty_string_returns_empty_dict(self):
        assert _parse_minimal_yaml("") == {}

    def test_only_comments_returns_empty_dict(self):
        assert _parse_minimal_yaml("# just a comment\n") == {}


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

def _make_git_dir(base: Path, name: str) -> Path:
    """Create a fake git repository directory."""
    p = base / name
    p.mkdir()
    (p / ".git").mkdir()
    return p


class TestLoadConfig:
    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            load_config(str(tmp_path / "nonexistent.yaml"))

    def test_missing_repos_section_exits(self, tmp_path):
        cfg = tmp_path / "devctl.yaml"
        cfg.write_text("unrelated: value\n")
        with pytest.raises(SystemExit):
            load_config(str(cfg))

    def test_missing_repo_path_field_exits(self, tmp_path):
        cfg = tmp_path / "devctl.yaml"
        cfg.write_text("repos:\n  r:\n    base: main\n")
        with pytest.raises(SystemExit):
            load_config(str(cfg))

    def test_nonexistent_repo_path_exits(self, tmp_path):
        cfg = tmp_path / "devctl.yaml"
        cfg.write_text("repos:\n  r:\n    path: /does/not/exist\n    base: main\n")
        with pytest.raises(SystemExit):
            load_config(str(cfg))

    def test_non_git_dir_exits(self, tmp_path):
        not_git = tmp_path / "notgit"
        not_git.mkdir()
        cfg = tmp_path / "devctl.yaml"
        cfg.write_text(f"repos:\n  r:\n    path: {not_git}\n    base: main\n")
        with pytest.raises(SystemExit):
            load_config(str(cfg))

    def test_valid_config_returns_dict(self, tmp_path):
        repo = _make_git_dir(tmp_path, "myrepo")
        cfg = tmp_path / "devctl.yaml"
        cfg.write_text(f"repos:\n  myrepo:\n    path: {repo}\n    base: main\n")
        config = load_config(str(cfg))
        assert config["repos"]["myrepo"]["base"] == "main"

    def test_resolved_path_is_absolute(self, tmp_path):
        repo = _make_git_dir(tmp_path, "myrepo")
        cfg = tmp_path / "devctl.yaml"
        cfg.write_text(f"repos:\n  myrepo:\n    path: {repo}\n    base: main\n")
        config = load_config(str(cfg))
        resolved = config["repos"]["myrepo"]["_resolved_path"]
        assert Path(resolved).is_absolute()

    def test_multiple_repos(self, tmp_path):
        r1 = _make_git_dir(tmp_path, "r1")
        r2 = _make_git_dir(tmp_path, "r2")
        cfg = tmp_path / "devctl.yaml"
        cfg.write_text(
            f"repos:\n  r1:\n    path: {r1}\n    base: main\n"
            f"  r2:\n    path: {r2}\n    base: develop\n"
        )
        config = load_config(str(cfg))
        assert "r1" in config["repos"]
        assert "r2" in config["repos"]
        assert config["repos"]["r2"]["base"] == "develop"
