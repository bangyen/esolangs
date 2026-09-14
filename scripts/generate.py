"""Regenerate committed docs, examples, or ZTOALC anchors."""

import argparse
import sys

from esolangs.tools import _generate_docs, _generate_examples, _generate_ztoalc


def main() -> int:
    """Dispatch one generation command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=("docs", "examples", "ztoalc"))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.target == "docs":
        if args.args:
            parser.error("docs takes no arguments")
        return _generate_docs.main()
    if args.target == "examples":
        sys.argv = [sys.argv[0], *args.args]
        return _generate_examples.main()
    if args.target == "ztoalc":
        if any(arg != "--check" for arg in args.args):
            parser.error("ztoalc accepts only --check")
        sys.argv = [sys.argv[0], *args.args]
        return _generate_ztoalc.main()
    raise AssertionError(args.target)


if __name__ == "__main__":
    raise SystemExit(main())
