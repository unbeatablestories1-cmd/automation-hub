# Root conftest.py — adds the project root to sys.path so all test files
# can import config, state, git_ops, github_ops, and commands.* directly.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
