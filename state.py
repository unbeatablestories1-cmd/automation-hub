"""
state.py — Read and write .devctl-state.yaml.

The state file is a flat key:value YAML file.  It is never committed.
It records the current ticket and branch so that `status` and `run`
don't need to guess.
"""
import sys
from pathlib import Path
from typing import Optional

STATE_FILE = ".devctl-state.yaml"


def write_state(
    ticket: str,
    branch: str,
    base_override: Optional[str] = None,
) -> None:
    """Write (or overwrite) the local state file."""
    override_value = base_override if base_override is not None else "null"
    content = (
        f"ticket: {ticket}\n"
        f"branch: {branch}\n"
        f"base_override: {override_value}\n"
    )
    Path(STATE_FILE).write_text(content)


def load_state() -> dict:
    """
    Load the local state file.

    Exits with an informative message when the file is absent or malformed.
    Returns a dict with keys: ticket, branch, base_override.
    """
    path = Path(STATE_FILE)
    if not path.exists():
        sys.exit(
            f"Error: State file not found: {STATE_FILE}\n"
            "Run 'devctl start TICKET-123' first."
        )

    state: dict = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        state[key] = None if value in ("null", "~", "") else value

    for required in ("ticket", "branch"):
        if required not in state:
            sys.exit(
                f"Error: State file {STATE_FILE} is missing field '{required}'.\n"
                "Delete the file and run 'devctl start TICKET-123' again."
            )

    return state
