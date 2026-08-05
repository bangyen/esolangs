"""Command-line interface for running esolang interpreters and compilers.

The ``esolangs`` command runs any interpreter or compiler module the same way
``python -m <module>`` would, so all modules keep a single entry point.
"""

import argparse
import importlib.util
import runpy
import sys


def main() -> None:
    """Parse arguments and execute the requested module as ``__main__``."""
    parser = argparse.ArgumentParser(
        prog="esolangs",
        description="Run an esolang interpreter or compiler on a program file.",
    )
    parser.add_argument(
        "module",
        help="dotted module path, e.g. esolangs.interpreters.tape_based.brainif",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="arguments passed to the interpreter (typically a program file)",
    )
    args = parser.parse_args()

    try:
        spec = importlib.util.find_spec(args.module)
    except (ModuleNotFoundError, ImportError):
        spec = None
    if spec is None:
        parser.error(f"unknown module: {args.module}")

    sys.argv = [args.module, *args.args]
    runpy.run_module(args.module, run_name="__main__")
