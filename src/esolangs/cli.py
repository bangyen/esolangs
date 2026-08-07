"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                        list the supported languages
    esolangs generate <language> <text>  print a program that outputs text
    esolangs run <language> <file>       run a program through its interpreter

For anything else (compilers, tools), invoke the module directly with
``python -m``, e.g. ``python -m esolangs.compilers.assembly.unsquare``.
"""

import sys

from esolangs import generate, list_languages, run

USAGE = """usage: esolangs <command> [...]

commands:
  list                        list the supported languages
  generate <language> <text>  print a program that outputs text
  run <language> <file>       run a program through its interpreter

examples:
  esolangs list
  esolangs generate CircleFuck "Hello, World!"
  esolangs run CircleFuck hello.txt
"""


def _fail(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.exit(2)


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        sys.stderr.write(USAGE)
        sys.exit(2)

    cmd, rest = argv[0], argv[1:]
    if cmd == "list":
        for name in list_languages():
            print(name)
    elif cmd == "generate":
        if len(rest) < 2:
            _fail("usage: esolangs generate <language> <text>")
        try:
            program = generate(rest[0], rest[1])
        except ValueError as exc:
            _fail(str(exc))
        print(program)
    elif cmd == "run":
        if len(rest) < 2:
            _fail("usage: esolangs run <language> <program-file>")
        language, path = rest[0], rest[1]
        try:
            with open(path) as f:
                program = f.read()
        except OSError as exc:
            _fail(f"cannot read {path}: {exc}")
        stdin = "" if sys.stdin.isatty() else sys.stdin.read()
        try:
            output = run(language, program, stdin)
        except ValueError as exc:
            _fail(str(exc))
        sys.stdout.write(output)
    else:
        _fail(f"unknown command: {cmd}\n\n{USAGE}")


if __name__ == "__main__":
    main()
