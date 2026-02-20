"""Thin shim so `python __main__.py` still works after cli.py was introduced."""
from cli import main

main()
