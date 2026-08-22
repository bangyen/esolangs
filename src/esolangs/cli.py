"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                         list the supported languages
    esolangs generate <language> <text>   print a program that outputs text
    esolangs run <language> <file>        run a program through its interpreter
    esolangs transpile <from> <to> <file> rewrite a program into another language

For anything else (compilers, tools), invoke the module directly with
``python -m``, e.g. ``python -m esolangs.compilers.unsquare``.
"""

import sys

from esolangs import generate, list_languages, run, transpile

USAGE = """usage: esolangs <command> [...]

commands:
  list                        list the supported languages
  generate <language> <text>  print a program that outputs text
  run <language> <file>       run a program through its interpreter
  transpile <from> <to> <file>  rewrite a program into another language

examples:
  esolangs list
  esolangs generate Circlefuck "Hello, World!"
  esolangs run Circlefuck hello.txt
  esolangs transpile brainfuck Circlefuck hello.bf
"""


def _fail(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.exit(2)


def main() -> None:
    """Dispatch the ``esolangs`` subcommands."""
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
    elif cmd == "transpile":
        if len(rest) < 3:
            _fail("usage: esolangs transpile <from> <to> <program-file>")
        source, target, path = rest[0], rest[1], rest[2]
        try:
            with open(path) as f:
                program = f.read()
        except OSError as exc:
            _fail(f"cannot read {path}: {exc}")
        try:
            output = transpile(source, target, program)
        except ValueError as exc:
            _fail(str(exc))
        sys.stdout.write(output)
    else:
        _fail(f"unknown command: {cmd}\n\n{USAGE}")


if __name__ == "__main__":
    main()
