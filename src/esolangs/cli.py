"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                         list the supported languages
    esolangs generate <language> <table>  print a program computing a table
                                          (``--width N`` wraps it to N columns)
    esolangs run <language> <file>        run a program through its interpreter
    esolangs debug <language> <file>      run under the breakpoint/watch VM

Every subcommand takes ``--help``.  For anything else, invoke the module
directly with ``python -m``.

Exit codes separate the two kinds of failure a caller handles differently:
**2** is a usage error (an unknown command, option, or language -- nothing
ran), **1** is the program's own failure (it read past its input, halted on
an invalid operation, was a template).  Only an unexpected error still
reaches the terminal as a traceback, which is what a traceback should mean.
"""

import sys

from esolangs import describe, generate, list_languages, run
from esolangs.debug import make_debugger
from esolangs.exceptions import EsolangError
from esolangs.registry import LANGUAGES
from esolangs.tools.wrap import DEFAULT_WIDTH

USAGE = """usage: esolangs <command> [...]

commands:
  list [--details]            list the supported languages
  generate [--width N] <language> <truth-table>
                              print a program computing a truth table
                              (--width wraps it for readability)
  run <language> <file>       run a program through its interpreter
  debug [--steps N] [--watch-cell I] [--break-on-output S] <language> <file>
                              run under the debugger and report where it
                              stopped, plus any watched cell's history

Language names are case-insensitive.  `esolangs <command> --help` describes
one command in full.

examples:
  esolangs list
  esolangs generate Circlefuck 0110
  esolangs generate --width brainfuck 10010110
  esolangs run Circlefuck hello.txt
  esolangs debug --steps 20 --watch-cell 0 brainfuck prog.txt
"""

HELP = {
    "list": """usage: esolangs list [--details]

List the supported languages, one per line.

options:
  --details   add a marker column per language:
                gen    has a boolean generator
                tmpl   that generator returns a {Xi} template rather than a
                       runnable program -- see `esolangs generate --help`
                ex     a committed program in examples/
""",
    "generate": f"""usage: esolangs generate [--width N] <language> <truth-table>

Print a program in <language> computing <truth-table>.

The table is a binary string of length 2**n indexed by the inputs, most
significant first, so its length sets the input count: 0110 is two-input
XOR, 10010110 is three-input.  The program reads one input per line and
prints the result.

Seventeen languages instead return a *template*: their generators embed the
inputs in the code rather than reading them, leaving a {{Xi}} slot per input.
Running one unfilled is refused.  `esolangs list --details` marks them
`tmpl`, and the Python API fills them:

    esolangs.instantiate(language, template, bits)

options:
  --width [N]  wrap the program to N columns (default {DEFAULT_WIDTH}) so it
               is readable in a diff.  Breaks only between whole tokens.
               Grid and newline-sensitive languages keep their own layout
               and ignore it.  A bare --width takes the default, so the next
               word is read as the language, not as a width.
""",
    "run": """usage: esolangs run <language> <program-file>

Run a program through its interpreter and print what it writes.

The program is read from <program-file>; its input is this command's stdin,
one line per read.  A program that reads more than it is given fails with
an input-exhausted error rather than hanging.

Output is written verbatim, with no trailing newline added, so it can be
compared or piped byte for byte.  One is added when stdout is a terminal,
where the alternative is the result running into the next prompt.
""",
    "debug": """usage: esolangs debug [options] <language> <program-file>

Run a program under the breakpoint/watch VM and report where it stopped.

Prints whether the machine halted, its final instruction position, its
output, any watched cell's history, and any error it raised (a debugged
program is one you are already unsure of, so a raise is reported rather
than propagated).

options:
  --steps N            stop after N commands.  The default is unbounded,
                       which hangs on a program that never halts.
  --watch-cell I       record memory cell I after every step and print the
                       history.  A long history is abridged; --steps bounds
                       it exactly.
  --break-on-output S  stop once S has been written, with S still the last
                       thing written.
""",
}

# A watched cell's history longer than this is printed abridged: the whole
# thing was one line of 486 comma-separated values for a 486-step program,
# which buries the ends that are actually read.
_HISTORY_SHOWN = 40


def _fail(message: str, code: int = 2) -> None:
    sys.stderr.write(message + "\n")
    sys.exit(code)


def _is_int(value: str) -> bool:
    """Whether ``value`` parses as an integer."""
    try:
        int(value)
    except ValueError:
        return False
    return True


def _split_positional(rest: list[str], known: set[str]) -> list[str]:
    """Return ``rest``'s positionals, refusing any unrecognized option.

    An unknown ``--option`` used to be kept as a positional, on the reasoning
    that a program file named ``--x`` should stay reachable.  It did, but a
    mistyped option went the same way: ``debug --frobnicate brainfuck p.txt``
    reported ``cannot read brainfuck``, blaming the language name for a typo
    three words earlier.  The file is still reachable, now by the convention
    that says so -- everything after a bare ``--`` is positional whatever it
    looks like.
    """
    args: list[str] = []
    for i, arg in enumerate(rest):
        if arg == "--":
            return args + rest[i + 1 :]
        if arg.startswith("--") and arg.partition("=")[0] not in known:
            _fail(f"unknown option: {arg}")
        args.append(arg)
    return args


def _check_count(
    command: str, args: list[str], wanted: int, *, bare_width: bool = False
) -> None:
    """Refuse a call with the wrong number of positional arguments.

    Extra arguments used to be dropped in silence, which turned a wrong
    command into a confident wrong answer.  It also made the bare-``--width``
    rule unreadable: ``generate --width abc Sophie 0110`` consumed nothing as
    a width, read ``abc`` as the language, and reported *that* as unknown --
    a message pointing at the wrong word entirely.  Saying which argument was
    unexpected, and why the count came out that way, is what turns it back
    into a fixable mistake.
    """
    if len(args) < wanted:
        _fail(HELP[command].splitlines()[0])
    if len(args) > wanted:
        hint = (
            "; a bare --width takes the default width, so the word after it "
            f"was read as the {'language' if command == 'generate' else 'first'} "
            "argument"
            if bare_width
            else ""
        )
        _fail(f"unexpected argument: {args[wanted]!r}{hint}")


def _pop_width(rest: list[str]) -> tuple[list[str], int | None, bool]:
    """Split a ``--width N`` (or ``--width=N``) option out of ``rest``.

    Returns the remaining arguments, the width (``None`` when the option is
    absent -- which leaves the program on one line, the output ``generate``
    has always produced), and whether a bare ``--width`` was taken.  A bare
    ``--width`` uses the conventional :data:`DEFAULT_WIDTH`, so the common
    case needs no number; an explicit value must be an integer, since
    silently reading the language name as a width would generate the wrong
    thing.
    """
    args: list[str] = []
    width: int | None = None
    bare = False
    i = 0
    while i < len(rest):
        arg = rest[i]
        # No ``--`` case here: :func:`_split_positional` has already consumed
        # the separator and passed on what followed it, so this only ever
        # sees positionals and the one option it owns.
        if arg == "--width":
            following = rest[i + 1] if i + 1 < len(rest) else None
            if following is None or not _is_int(following):
                width = DEFAULT_WIDTH
                bare = True
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
    return args, width, bare


def _pop_options(rest: list[str], names: set[str]) -> tuple[list[str], dict[str, str]]:
    """Split ``--name V`` and ``--name=V`` options out of ``rest``.

    Only the names given are recognized; :func:`_split_positional` refuses
    anything else, so what stays here is positional.  Every option in
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


def _abridge(history: list[object]) -> str:
    """Render a watch history, eliding the middle of a long one."""
    if len(history) <= _HISTORY_SHOWN:
        return str(history)
    head = ", ".join(str(v) for v in history[: _HISTORY_SHOWN // 2])
    tail = ", ".join(str(v) for v in history[-_HISTORY_SHOWN // 2 :])
    return f"[{head}, ... {len(history) - _HISTORY_SHOWN} more ..., {tail}]"


def _read_program(path: str) -> str:
    """Return the contents of ``path``, or exit with a usage error."""
    try:
        with open(path) as f:
            return f.read()
    except OSError as exc:
        _fail(f"cannot read {path}: {exc}")
        raise  # pragma: no cover - unreachable; _fail exits


def _list(rest: list[str]) -> None:
    """Print the supported languages, optionally with capability markers."""
    rest = _split_positional(rest, {"--details"})
    details = "--details" in rest
    _check_count("list", [a for a in rest if a != "--details"], 0)
    if not details:
        for name in list_languages():
            print(name)
        return
    width = max(len(name) for name in LANGUAGES)
    for name in list_languages():
        facts = describe(name)
        marks = " ".join(
            filter(
                None,
                (
                    "gen" if facts["boolean_generator"] else "",
                    "tmpl" if facts["parameterized"] else "",
                    "ex" if facts["examples"] else "",
                ),
            )
        )
        print(f"{name.ljust(width)}  {marks}")


def _debug(rest: list[str]) -> None:
    """Run a program under the debugger and report where it stopped."""
    options_taken = {"--steps", "--watch-cell", "--break-on-output"}
    rest = _split_positional(rest, options_taken)
    rest, options = _pop_options(rest, options_taken)
    _check_count("debug", rest, 2)
    language, path = rest[0], rest[1]
    for name in ("--steps", "--watch-cell"):
        if name in options and not _is_int(options[name]):
            _fail(f"{name} must be an integer, got {options[name]!r}")
    program = _read_program(path)

    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        dbg = make_debugger(language, program, stdin)
    except EsolangError as exc:
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
    reason = None
    try:
        reason = dbg.run(steps)
    except Exception as exc:
        fault = f"{type(exc).__name__}: {exc}"

    print(f"halted: {'yes' if dbg.halted else 'no'}")
    if reason is not None:
        print(f"stopped: {reason}")
    print(f"ip: {dbg.ip}")
    print(f"output: {dbg.output!r}")
    if history is not None:
        print(f"cell {options['--watch-cell']}: {_abridge(list(history))}")
    if fault is not None:
        print(f"raised: {fault}")


def _generate(rest: list[str]) -> None:
    """Print a program computing a truth table."""
    rest = _split_positional(rest, {"--width"})
    rest, width, bare = _pop_width(rest)
    _check_count("generate", rest, 2, bare_width=bare)
    try:
        program = generate(rest[0], rest[1], width)
    except EsolangError as exc:
        _fail(str(exc))
    print(program)


def _run(rest: list[str]) -> None:
    """Run a program through its interpreter and write its output."""
    rest = _split_positional(rest, set())
    _check_count("run", rest, 2)
    language, path = rest[0], rest[1]
    program = _read_program(path)
    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        output = run(language, program, stdin)
    except EsolangError as exc:
        # A usage error (an unknown language) is still 2; anything the
        # program itself did is the program's failure, and exits 1.
        _fail(str(exc), 2 if isinstance(exc, ValueError) else 1)
    sys.stdout.write(output)
    # Piped output stays byte-exact -- it gets compared and diffed -- but a
    # result with no trailing newline runs into the next shell prompt.
    if output and not output.endswith("\n") and sys.stdout.isatty():
        sys.stdout.write("\n")


def main() -> None:
    """Dispatch the ``esolangs`` subcommands."""
    argv = sys.argv[1:]
    if not argv:
        sys.stderr.write(USAGE)
        sys.exit(2)

    cmd, rest = argv[0], argv[1:]
    if cmd in ("--help", "-h", "help"):
        sys.stdout.write(HELP[rest[0]] if rest and rest[0] in HELP else USAGE)
        sys.exit(0)
    if cmd not in HELP:
        _fail(f"unknown command: {cmd}\n\n{USAGE}")
    if {"--help", "-h"} & set(rest):
        sys.stdout.write(HELP[cmd])
        sys.exit(0)

    {"list": _list, "generate": _generate, "run": _run, "debug": _debug}[cmd](rest)


if __name__ == "__main__":
    main()
