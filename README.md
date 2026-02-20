# devctl

A minimal CLI tool for synchronizing feature branches across multiple
repositories.

devctl does **not** modify workflow YAML, manage secrets, interpret domain
logic, or act as a deployment engine.  It only coordinates branches.

---

## Installation

```bash
# Clone and install (installs the `devctl` command into your PATH)
git clone <repo-url> devctl
pip install -e ./devctl

# Optional: also install PyYAML for more robust YAML parsing
pip install pyyaml
```

Python ≥ 3.10 and git ≥ 2.28 are required.  No other runtime dependencies.

---

## Configuration

devctl reads `devctl.yaml` from the directory you run it in.  The easiest
way to create it is with `devctl init` (see below), but you can also write
it by hand.

```yaml
repos:
  my-repo:
    path: .                  # use "." for the current directory, or any relative/absolute path
    base: main               # branch to create the feature branch from
  another-repo:
    path: ../another-repo
    base: main
  yet-another-repo:
    path: ../yet-another-repo
    base: develop            # each repo can have its own base branch
  # add as many repos as needed...
```

**Rules:**
- `path` must exist and be a git repository
- `base` is the branch that the feature branch is created from
- Paths are relative to the directory where you run devctl (the CWD)

---

## State File

After a successful `start`, devctl writes `.devctl-state.yaml` in the CWD.
**Do not commit this file** — add it to `.gitignore`:

```
.devctl-state.yaml
```

Contents:

```yaml
ticket: ABC-123
branch: feature/ABC-123
base_override: null       # populated when --base was passed to start
```

`status` reads this file to know which branch to check for.

---

## Commands

### `devctl init`

Scans the current directory for immediate subdirectory git repositories and
writes `devctl.yaml`.  The default branch for each repo is auto-detected
from `origin/HEAD`; falls back to the current branch, then `main`.

```bash
cd ~/repos        # directory containing repo-a/, repo-b/, etc.
devctl init
```

**Sample output:**
```
Wrote devctl.yaml with 3 repo(s):
  another-repo
  my-repo
  yet-another-repo
```

Overwrites any existing `devctl.yaml`.  Only scans one level deep.

---

### `devctl start TICKET [--base BRANCH] [--force]`

Creates `feature/TICKET` in every configured repo and pushes it to origin.

```bash
devctl start ABC-123
devctl start ABC-123 --base develop          # override base branch for all repos
devctl start ABC-123 --force                 # re-use an existing local branch
devctl start ABC-123 --repos repo-a repo-b   # only operate on specific repos
```

**Steps per repo:**
1. `git fetch origin`
2. Error if local branch already exists (exit 1 unless `--force`)
3. Warn if remote branch already exists, then continue
4. Checkout the base branch and `git pull --ff-only`
5. `git checkout -b feature/ABC-123`
6. `git push --set-upstream origin feature/ABC-123`

**Sample output:**
```
  ✔ my-repo → feature/ABC-123 created & pushed
  ✔ another-repo → feature/ABC-123 created & pushed
  ✔ yet-another-repo → feature/ABC-123 created & pushed

Branch synchronization complete.
```

Exits 0 on success, 1 if any repo fails.  All repos are attempted; errors
are collected and reported together before exiting.

---

### `devctl status`

Reads `.devctl-state.yaml` and prints the synchronization table.

```bash
devctl status
devctl status --repos repo-a repo-b   # only check specific repos
```

```
Repo                 Local Branch               Remote   Clean
--------------------------------------------------------------
my-repo              ABC-123                    ✔        ✔
another-repo         ABC-123                    ✔        ✘
yet-another-repo     ABC-123                    ✔        ✔
```

Exits 1 if any repo is on the wrong branch, its remote branch is missing,
or its working tree is dirty.

---

## Typical Developer Flow

```bash
# 0. One-time setup: generate devctl.yaml from your repos directory
devctl init

# 1. Create feature branches across all repos
devctl start ABC-123

# 2. Edit code in each repo, then push
#    (git add / git commit / git push in each repo)

# 3. Verify everything is in sync
devctl status
```

---

## Safety Guarantees

| What devctl never does | Why |
|---|---|
| Auto-commit uncommitted changes | Developers decide what to commit |
| Force-push | Only `--set-upstream`, never `--force` |
| Guess the current branch | Always reads via `git rev-parse --abbrev-ref HEAD` |
| Guess the ticket | Always reads `.devctl-state.yaml` |
| Modify `.github/workflows/*.yml` | Out of scope |

---

## Running Tests

```bash
pip install -r requirements-dev.txt

# All tests
pytest

# Unit tests only (no real git I/O)
pytest tests/ -k "not integration"

# Integration tests (creates real git repos under /tmp)
pytest tests/test_integration.py -v
```

---

## Project Layout

```
__main__.py          CLI entry point (argparse dispatch)
config.py            Load and validate devctl.yaml
state.py             Read and write .devctl-state.yaml
git_ops.py           Git primitives (always use explicit repo_path)
commands/
  init.py            devctl init
  start.py           devctl start
  status.py          devctl status
tests/
  test_config.py     Unit tests for config.py
  test_state.py      Unit tests for state.py
  test_git_ops.py    Unit tests for git_ops.py (real temp repos)
  test_cmd_init.py   Unit tests for commands/init.py
  test_cmd_start.py  Unit tests for commands/start.py (mocked git)
  test_cmd_status.py Unit tests for commands/status.py (mocked git)
  test_integration.py End-to-end with real git repositories
```
