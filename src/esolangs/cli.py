"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                         list the supported languages
    esolangs generate <language> <text>   print a program that outputs text
                                          (``--width N`` wraps it to N columns)
    esolangs run <language> <file>        run a program through its interpreter
    esolangs transpile <from> <to> <file> rewrite a program into another language

For anything else (compilers, tools), invoke the module directly with
``python -m``, e.g. ``python -m esolangs.compilers.unsquare``.
"""

import sys

from esolangs import generate, list_languages, run, transpile
from esolangs.tools.wrap import DEFAULT_WIDTH

USAGE = """usage: esolangs <command> [...]

commands:
  list                        list the supported languages
  generate [--width N] <language> <text>
                              print a program that outputs text
                              (--width wraps it for readability)
  run <language> <file>       run a program through its interpreter
  transpile <from> <to> <file>  rewrite a program into another language

examples:
  esolangs list
  esolangs generate Circlefuck "Hello, World!"
  esolangs generate --width Polynomial "Hello, World!"
  esolangs run Circlefuck hello.txt
  esolangs transpile brainfuck Painfuck hello.bf
"""


def _fail(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.exit(2)


def _is_int(value: str) -> bool:
    """Whether ``value`` parses as an integer."""
    try:
        int(value)
    except ValueError:
        return False
    return True


def _pop_width(rest: list[str]) -> tuple[list[str], int | None]:
    """Split a ``--width N`` (or ``--width=N``) option out of ``rest``.

    Returns the remaining positional arguments and the width, or ``None``
    when the option is absent -- which leaves the program on one line, the
    output ``generate`` has always produced.  A bare ``--width`` takes the
    conventional :data:`DEFAULT_WIDTH`, so the common case needs no number;
    an explicit value must be an integer, since silently reading the
    language name as a width would generate the wrong thing.
    """
    args: list[str] = []
    width: int | None = None
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--width":
            following = rest[i + 1] if i + 1 < len(rest) else None
            if following is None or not _is_int(following):
                width = DEFAULT_WIDTH
                i += 1
                continue
            value = following
            i += 2
        elif arg.startswith("--width="):
            value = arg.split("=", 1)[1]
            i += 1
        else:
            args.append(arg)
            i += 1
            continue
        try:
            width = int(value)
        except ValueError:
            _fail(f"--width must be an integer, got {value!r}")
        if width is not None and width <= 0:
            _fail(f"--width must be positive, got {width}")
    return args, width


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
        rest, width = _pop_width(rest)
        if len(rest) < 2:
            _fail("usage: esolangs generate [--width N] <language> <text>")
        try:
            program = generate(rest[0], rest[1], width)
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
