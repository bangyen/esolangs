"""Regenerate committed docs or examples."""

import argparse
import sys

from esolangs.tools import _generate_docs, _generate_examples


def main() -> int:
    """Dispatch one generation command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=("docs", "examples"))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.target == "docs":
        if args.args:
            parser.error("docs takes no arguments")
        return _generate_docs.main()
    if args.target == "examples":
        sys.argv = [sys.argv[0], *args.args]
        return _generate_examples.main()
    raise AssertionError(args.target)


if __name__ == "__main__":
    raise SystemExit(main())
