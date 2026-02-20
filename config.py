"""
config.py — Load and validate devctl.yaml.

Tries PyYAML first; falls back to a minimal built-in parser that handles
the exact nested-dict format used by devctl.yaml.
"""
import sys
from pathlib import Path
from typing import Optional

CONFIG_FILE = "devctl.yaml"


# ---------------------------------------------------------------------------
# Minimal YAML parser (no external dependency)
# ---------------------------------------------------------------------------

def _parse_minimal_yaml(text: str) -> dict:
    """
    Parse simple nested YAML without an external library.

    Supports: nested dicts, scalar strings, integers, floats, null, booleans.
    Does NOT support: lists, multi-line strings, anchors, or tags.
    """
    root: dict = {}
    # Stack entries: (container_dict, indent_level_of_the_key_that_opened_it)
    parents: list[tuple[dict, int]] = []

    for line_raw in text.splitlines():
        line = line_raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if ":" not in stripped:
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        # Strip trailing inline comment
        if " #" in value:
            value = value[: value.index(" #")].rstrip()

        # Pop stack until the top is the parent for this indent level
        while parents and indent <= parents[-1][1]:
            parents.pop()

        target = parents[-1][0] if parents else root

        if not value:
            # Key maps to a nested dict
            new_dict: dict = {}
            target[key] = new_dict
            parents.append((new_dict, indent))
        else:
            # Scalar value
            if value in ("null", "~"):
                target[key] = None
            elif value == "true":
                target[key] = True
            elif value == "false":
                target[key] = False
            else:
                try:
                    target[key] = int(value)
                except ValueError:
                    try:
                        target[key] = float(value)
                    except ValueError:
                        target[key] = value

    return root


def _load_yaml(path: Path) -> dict:
    text = path.read_text()
    try:
        import yaml  # type: ignore

        result = yaml.safe_load(text)
        return result if isinstance(result, dict) else {}
    except ImportError:
        return _parse_minimal_yaml(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None) -> dict:
    """Load and validate devctl.yaml. Exits with an error message on failure."""
    path = Path(config_path or CONFIG_FILE)
    if not path.exists():
        sys.exit(f"Error: Config file not found: {path}")

    try:
        config = _load_yaml(path)
    except Exception as exc:
        sys.exit(f"Error: Failed to parse {path}: {exc}")

    if not config:
        sys.exit(f"Error: {path} is empty or malformed")

    # --- top-level sections ------------------------------------------------
    if "repos" not in config:
        sys.exit("Error: Config missing required section 'repos'")

    # --- repos section ------------------------------------------------------
    repos = config["repos"]
    if not isinstance(repos, dict) or not repos:
        sys.exit("Error: Config 'repos' section is empty or malformed")

    for name, repo_cfg in repos.items():
        if not isinstance(repo_cfg, dict):
            sys.exit(f"Error: Config repo '{name}' must be a mapping")
        for field in ("path", "base"):
            if not repo_cfg.get(field):
                sys.exit(f"Error: Config repos.{name}.{field} is required")

        repo_path = Path(repo_cfg["path"]).resolve()
        if not repo_path.exists():
            sys.exit(f"Error: Repo path does not exist: {name} → {repo_path}")
        if not repo_path.is_dir():
            sys.exit(f"Error: Repo path is not a directory: {name} → {repo_path}")
        if not (repo_path / ".git").exists():
            sys.exit(f"Error: Not a git repository: {name} → {repo_path}")

        # Store resolved absolute path so callers don't have to re-resolve
        repo_cfg["_resolved_path"] = str(repo_path)

    return config
