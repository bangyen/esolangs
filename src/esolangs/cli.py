"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                         list the supported languages
    esolangs generate <language> <table>  print a program computing a table
                                          (``--width N`` wraps it to N columns)
    esolangs run <language> <file>        run a program through its interpreter
    esolangs debug <language> <file>      run under the breakpoint/watch VM

For anything else, invoke the module directly with ``python -m``.
"""

import sys

from esolangs import generate, list_languages, run
from esolangs.debug import make_debugger
from esolangs.tools.wrap import DEFAULT_WIDTH

USAGE = """usage: esolangs <command> [...]

commands:
  list                        list the supported languages
  generate [--width N] <language> <truth-table>
                              print a program computing a truth table
                              (--width wraps it for readability)
  run <language> <file>       run a program through its interpreter
  debug [--steps N] [--watch-cell I] [--break-on-output S] <language> <file>
                              run under the debugger and report where it
                              stopped, plus any watched cell's history

examples:
  esolangs list
  esolangs generate Circlefuck 0110
  esolangs generate --width Brainfuck 10010110
  esolangs run Circlefuck hello.txt
  esolangs debug --steps 20 --watch-cell 0 brainfuck prog.txt
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


def _pop_options(rest: list[str], names: set[str]) -> tuple[list[str], dict[str, str]]:
    """Split ``--name V`` and ``--name=V`` options out of ``rest``.

    Only the names given are recognized; anything else stays positional, so
    a program file called ``--x`` is still reachable and an unknown option
    is reported by the caller rather than swallowed here.  Every option in
    ``names`` takes a value, which is what lets a missing one be an error
    instead of silently consuming the next positional.
    """
    args: list[str] = []
    found: dict[str, str] = {}
    i = 0
    while i < len(rest):
        arg = rest[i]
        name, sep, inline = arg.partition("=")
        if name not in names:
            args.append(arg)
            i += 1
        elif sep:
            found[name] = inline
            i += 1
        elif i + 1 < len(rest):
            found[name] = rest[i + 1]
            i += 2
        else:
            _fail(f"{name} needs a value")
    return args, found


def _debug(rest: list[str]) -> None:
    """Run a program under the debugger and report where it stopped."""
    rest, options = _pop_options(rest, {"--steps", "--watch-cell", "--break-on-output"})
    if len(rest) < 2:
        _fail("usage: esolangs debug [options] <language> <program-file>")
    language, path = rest[0], rest[1]
    for name in ("--steps", "--watch-cell"):
        if name in options and not _is_int(options[name]):
            _fail(f"{name} must be an integer, got {options[name]!r}")
    try:
        with open(path) as f:
            program = f.read()
    except OSError as exc:
        _fail(f"cannot read {path}: {exc}")

    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        dbg = make_debugger(language, program, stdin)
    except ValueError as exc:
        _fail(str(exc))
    if "--break-on-output" in options:
        dbg.break_on_output(options["--break-on-output"])
    history = (
        dbg.watch_cell(int(options["--watch-cell"]))
        if "--watch-cell" in options
        else None
    )
    steps = int(options["--steps"]) if "--steps" in options else None
    # A debugged program is one the caller is already unsure of, so a raise
    # here is a result to report rather than a crash to propagate: the
    # state up to the fault is the thing they asked to see.
    fault = None
    try:
        dbg.run(steps)
    except Exception as exc:
        fault = f"{type(exc).__name__}: {exc}"

    print(f"halted: {'yes' if dbg.halted else 'no'}")
    print(f"ip: {dbg.ip}")
    print(f"output: {dbg.output!r}")
    if history is not None:
        print(f"cell {options['--watch-cell']}: {history}")
    if fault is not None:
        print(f"raised: {fault}")


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
            _fail("usage: esolangs generate [--width N] <language> <truth-table>")
        try:
            program = generate(rest[0], rest[1], width)
        except ValueError as exc:
            _fail(str(exc))
        print(program)
    elif cmd == "debug":
        _debug(rest)
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
