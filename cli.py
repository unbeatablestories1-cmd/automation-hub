"""
cli.py — CLI entry point for devctl.

Installed as the `devctl` command via pyproject.toml.
Can also be run directly: python cli.py <command>
"""
import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="devctl",
        description=(
            "Synchronize feature branches across multiple repos."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # ------------------------------------------------------------------
    # devctl init
    # ------------------------------------------------------------------
    subparsers.add_parser(
        "init",
        help="Scan the current directory for git repos and write devctl.yaml",
    )

    # ------------------------------------------------------------------
    # devctl start TICKET [--base BRANCH] [--force]
    # ------------------------------------------------------------------
    start_p = subparsers.add_parser(
        "start",
        help="Create and push a feature branch across all configured repos",
    )
    start_p.add_argument(
        "ticket",
        metavar="TICKET",
        help="Ticket identifier used to name the branch (e.g. ABC-123)",
    )
    start_p.add_argument(
        "--base",
        metavar="BRANCH",
        default=None,
        help="Override the base branch for every repo (default: per-repo 'base' in config)",
    )
    start_p.add_argument(
        "--force",
        action="store_true",
        help="Re-use a branch that already exists locally instead of erroring",
    )
    start_p.add_argument(
        "--repos",
        metavar="REPO",
        nargs="+",
        default=None,
        help="Only operate on these repos (default: all repos in config)",
    )

    # ------------------------------------------------------------------
    # devctl status
    # ------------------------------------------------------------------
    status_p = subparsers.add_parser(
        "status",
        help="Show branch synchronization status for all configured repos",
    )
    status_p.add_argument(
        "--repos",
        metavar="REPO",
        nargs="+",
        default=None,
        help="Only check these repos (default: all repos in config)",
    )

    args = parser.parse_args()

    if args.command == "init":
        from commands.init import cmd_init
        cmd_init(args)
    elif args.command == "start":
        from commands.start import cmd_start
        cmd_start(args)
    elif args.command == "status":
        from commands.status import cmd_status
        cmd_status(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
