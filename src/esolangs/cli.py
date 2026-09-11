"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                         list the supported languages
    esolangs encode <language> <bits>     print the stdin those bits need
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
from collections.abc import Sequence

from esolangs import (
    __version__,
    check_runnable,
    describe,
    encode_inputs,
    generate,
    instantiate,
    list_languages,
    run,
)
from esolangs.debugger import make_debugger
from esolangs.exceptions import EsolangError, TemplateError
from esolangs.registry import LANGUAGES
from esolangs.tools.wrap import DEFAULT_WIDTH

USAGE = """usage: esolangs <command> [...]

commands:
  list [--details]            list the supported languages
  encode <language> <bits>    print the stdin that feeds those bits
  generate [--width [N]] [--bits BITS] <language> <truth-table>
                              print a program computing a truth table
                              (--width wraps it; --bits fills a template)
  run [--timeout S] <language> <file>
                              run a program through its interpreter
  debug [--steps N] [--watch-cell I] [--break-on-output S] <language> <file>
                              run under the debugger and report where it
                              stopped, plus any watched cell's history

Language names are case-insensitive.  `esolangs <command> --help` describes
one command in full; `--version` prints the version.

examples:
  esolangs list
  esolangs encode Grapheme 10
  esolangs generate Circlefuck 0110
  esolangs generate --width brainfuck 10010110
  esolangs generate --bits 10 Minifuck 0110
  esolangs run Circlefuck hello.txt
  esolangs debug --steps 20 --watch-cell 0 brainfuck prog.txt
"""

HELP = {
    "encode": """usage: esolangs encode <language> <bits>

Print the stdin that feeds <bits> to a <language> program, so it can be
piped straight into `esolangs run`:

    esolangs encode Taglate 101 | esolangs run Taglate prog.txt

Most languages read one 0/1 line per bit and this is no more than what you
would have typed.  Four are not most languages, and each fails silently if
you guess: Grapheme spells its bits %/A, Clockwise and Fargo want them all
on one line, and Taglate pads an odd input count with a leading zero line.
The Input column of examples/boolean/MANIFEST.md lists every language's.

A language whose generator embeds the inputs in the program reads no stdin
at all; `esolangs generate --bits` builds those.
""",
    "list": """usage: esolangs list [--details]

List the supported languages, one per line.

options:
  --details   add a marker column per language:
                gen    has a boolean generator
                tmpl   that generator returns a {Xi} template rather than a
                       runnable program -- see `esolangs generate --help`
                ex     a committed program in examples/
""",
    "generate": f"""usage: esolangs generate [--width N] [--bits BITS] <language>
                         <truth-table>

Print a program in <language> computing <truth-table>.

The table is a binary string of length 2**n indexed by the inputs, most
significant first, so its length sets the input count: 0110 is two-input
XOR, 10010110 is three-input.  The program reads one input per line and
prints the result.

Seventeen languages instead return a *template*: their generators embed the
inputs in the code rather than reading them, leaving a {{Xi}} slot per input.
Running one unfilled is refused.  `esolangs list --details` marks them
`tmpl`; pass --bits to get a runnable program instead of the template.

options:
  --bits BITS  fill a template's input slots with these bits, one character
               per input, and print the runnable program.  Substituting them
               by hand does not work: each language spells a set-input its
               own way, and a 0/1 in the slot is a different program.
  --width [N]  wrap the program to N columns (default {DEFAULT_WIDTH}) so it
               is readable in a diff.  Breaks only between whole tokens.
               Newline-sensitive languages ignore it, and the generators
               that lay out their own shape (LaserFuck, Streetcode) build a
               narrower shape rather than reflowing one.  A template is
               wrapped only once --bits has filled its slots.  A bare
               --width takes the default, so the next word is read as the
               language, not as a width.

examples:
  esolangs generate brainfuck 0110
  esolangs generate --bits 10 Minifuck 0110
""",
    "run": """usage: esolangs run <language> <program-file>

Run a program through its interpreter and print what it writes.

The program is read from <program-file>; its input is this command's stdin.
Most languages read one line per input bit, but four do not: Grapheme reads
%/A rather than 0/1, Clockwise and Fargo take every bit on one line, and
Taglate pads an odd input count with a leading zero line, so its 3-input
programs read four.  Feeding the wrong encoding is answered with a wrong
result, not an error, so check the Input column of
examples/boolean/MANIFEST.md -- or have `esolangs encode` spell it for you:

    esolangs encode Taglate 101 | esolangs run Taglate prog.txt

A program that reads more than it is given fails with an input-exhausted
error rather than hanging.

Output is written verbatim, with no trailing newline added, so it can be
compared or piped byte for byte.  One is added when stdout is a terminal,
where the alternative is the result running into the next prompt.

options:
  --timeout SECONDS  stop the run after this long and fail, rather than
                     hanging.  There is no bound by default, and three
                     languages answer a 1 by *not* terminating -- 123,
                     ArrowQueue and Point Break halt for a 0 and loop
                     forever for a 1, so a timeout there is the answer.
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
  --timeout SECONDS    stop the run after this long, reporting
                       `stopped: timeout`.  Like --steps this bounds a
                       program that never halts, which is what the three
                       terminate-as-answer languages are.
""",
}

# A watched cell's history longer than this is printed abridged: the whole
# thing was one line of 486 comma-separated values for a 486-step program,
# which buries the ends that are actually read.
_HISTORY_SHOWN = 40


def _template_hint(exc: TemplateError, language: str) -> str:
    """Re-point a template refusal at the CLI flag that fills the slots.

    The library's message names ``esolangs.instantiate(...)``, which is the
    right answer for a Python caller and a dead end for someone who has
    only ever typed ``esolangs``.
    """
    message = str(exc)
    pointer = "fill them with esolangs.instantiate("
    if pointer not in message:
        return message
    head = message.split(pointer)[0]
    return f"{head}fill them with: esolangs generate --bits <bits> {language} <table>"


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
        # Any leading dash is an option, not a positional.  A single-dash
        # ``-w`` used to be kept as one, so the error named whichever word
        # then landed in the wrong slot.  A leading digit is exempt so a
        # negative number can still be an argument.
        looks_like_option = len(arg) > 1 and arg[0] == "-" and not arg[1].isdigit()
        if looks_like_option and arg.partition("=")[0] not in known:
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
        # The whole synopsis, not its first line: ``generate``'s wraps onto
        # a second, so a missing truth table was reported with a usage
        # string that did not mention the truth table.
        synopsis = HELP[command].split("\n\n", 1)[0]
        _fail(synopsis)
    if len(args) > wanted:
        hint = (
            f"; --width took no value here (only an integer counts as one), so "
            f"it used the default width and {args[0]!r} was read as the language"
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
    seen: dict[str, str] = {}
    i = 0
    while i < len(rest):
        arg = rest[i]
        # No ``--`` case here: :func:`_split_positional` has already consumed
        # the separator and passed on what followed it, so this only ever
        # sees positionals and the one option it owns.
        if arg == "--width":
            _refuse_repeat(seen, "--width")
            seen["--width"] = arg
            following = rest[i + 1] if i + 1 < len(rest) else None
            if following is None or not _is_int(following):
                width = DEFAULT_WIDTH
                bare = True
                i += 1
                continue
            value = following
            i += 2
        elif arg.startswith("--width="):
            _refuse_repeat(seen, "--width")
            seen["--width"] = arg
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


def _refuse_repeat(found: dict[str, str], name: str) -> None:
    """Refuse a second copy of an option that takes a value.

    Last-wins is the common convention, but this CLI refuses nearly every
    other ambiguity, so silently dropping the first of two ``--bits`` was
    the outlier -- and the one that quietly emits a program for the wrong
    input row.
    """
    if name in found:
        _fail(f"{name} given more than once (first was {found[name]!r})")


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
            _refuse_repeat(found, name)
            found[name] = inline
            i += 1
        elif i + 1 < len(rest):
            _refuse_repeat(found, name)
            found[name] = rest[i + 1]
            i += 2
        else:
            _fail(f"{name} needs a value")
    return args, found


def _abridge(history: Sequence[object]) -> str:
    """Render a watch history, eliding the middle of a long one."""
    if len(history) <= _HISTORY_SHOWN:
        return str(history)
    head = ", ".join(str(v) for v in history[: _HISTORY_SHOWN // 2])
    tail = ", ".join(str(v) for v in history[-_HISTORY_SHOWN // 2 :])
    return f"[{head}, ... {len(history) - _HISTORY_SHOWN} more ..., {tail}]"


def _timeout_of(options: dict[str, str]) -> float | None:
    """Return the ``--timeout`` seconds, or None, refusing a bad value."""
    if "--timeout" not in options:
        return None
    try:
        seconds = float(options["--timeout"])
    except ValueError:
        _fail(f"--timeout must be a number, got {options['--timeout']!r}")
    if seconds != seconds or seconds in (float("inf"), float("-inf")):
        _fail(f"--timeout must be finite, got {options['--timeout']!r}")
    if seconds <= 0:
        _fail(f"--timeout must be positive, got {options['--timeout']}")
    return seconds


def _read_program(path: str) -> str:
    """Return the program in ``path``, or exit with a usage error.

    The trailing newline is the *file's*, not the program's, and three
    interpreters (CV(N)(C), Grapheme, NoComment) reject one as an unknown
    command.  Since ``esolangs generate ... > prog.txt`` writes that newline,
    keeping it meant this tool produced programs its own ``run`` refused,
    and the three committed examples could not be run at all.
    """
    try:
        with open(path) as f:
            return f.read().rstrip("\n")
    except OSError as exc:
        _fail(f"cannot read {path}: {exc}")
        raise  # pragma: no cover - unreachable; _fail exits


def _encode(rest: list[str]) -> None:
    """Print the stdin that feeds a language its input bits."""
    rest = _split_positional(rest, set())
    _check_count("encode", rest, 2)
    language, bits = rest[0], rest[1]
    if set(bits) - {"0", "1"} or not bits:
        _fail(f"bits must be a string of 0s and 1s, got {bits!r}")
    try:
        sys.stdout.write(encode_inputs(language, [int(bit) for bit in bits]))
    except EsolangError as exc:
        _fail(str(exc))


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
    options_taken = {"--steps", "--watch-cell", "--break-on-output", "--timeout"}
    # Options first, then the stray-flag check: a *value* can begin with a
    # dash (``--timeout -inf``), and a check that runs before the pairs are
    # consumed cannot tell one from a flag -- it answered that with
    # "unknown option: -inf" instead of "must be finite".
    rest, options = _pop_options(rest, options_taken)
    rest = _split_positional(rest, set())
    _check_count("debug", rest, 2)
    language, path = rest[0], rest[1]
    for name in ("--steps", "--watch-cell"):
        if name in options and not _is_int(options[name]):
            _fail(f"{name} must be an integer, got {options[name]!r}")
    # A negative cell index is Python list indexing leaking through: it
    # printed cell 0's history under the name -1, which is a wrong answer
    # rather than an empty one.  Every other negative here is refused.
    if "--watch-cell" in options and int(options["--watch-cell"]) < 0:
        _fail(f"--watch-cell must not be negative, got {options['--watch-cell']}")
    # A negative bound is not a smaller bound, it is no bound: the run went
    # unbounded, which is the one thing --steps exists to prevent.
    if "--steps" in options and int(options["--steps"]) < 0:
        _fail(f"--steps must not be negative, got {options['--steps']}")
    program = _read_program(path)

    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    # The same two refusals ``run`` makes.  Debugging a program is no reason
    # to skip them: an unfilled template stepped confidently to `output: '0'`
    # and reported a wrong answer with no warning at all, and a load error
    # escaped as a traceback from the one command whose whole promise is to
    # report a fault rather than propagate it.
    try:
        check_runnable(language, program)
        dbg = make_debugger(language, program, stdin)
    except TemplateError as exc:
        _fail(_template_hint(exc, language))
    except EsolangError as exc:
        _fail(str(exc))
    except ValueError as exc:
        _fail(f"{language}: {exc}")
    if "--break-on-output" in options:
        if not options["--break-on-output"]:
            _fail("--break-on-output needs some text; every output contains ''")
        dbg.break_on_output(options["--break-on-output"])
    history = (
        dbg.watch_cell(int(options["--watch-cell"]))
        if "--watch-cell" in options
        else None
    )
    steps = int(options["--steps"]) if "--steps" in options else None
    limit = _timeout_of(options)
    # A debugged program is one the caller is already unsure of, so a raise
    # here is a result to report rather than a crash to propagate: the
    # state up to the fault is the thing they asked to see.
    fault = None
    reason = None
    try:
        reason = dbg.run(steps, limit)
    except Exception as exc:
        fault = f"{type(exc).__name__}: {exc}"

    print(f"halted: {'yes' if dbg.halted else 'no'}")
    # Always printed, so a script reading fixed field positions does not
    # break on the one case it most wants to parse.
    print(f"stopped: {reason if reason is not None else 'raised'}")
    print(f"ip: {dbg.ip}")
    print(f"output: {dbg.output!r}")
    if history is not None:
        values = list(history)
        untouched = " (never written)" if set(values) <= {None} else ""
        print(f"cell {options['--watch-cell']}: {_abridge(values)}{untouched}")
    if fault is not None:
        print(f"raised: {fault}")


def _generate(rest: list[str]) -> None:
    """Print a program computing a truth table."""
    rest, options = _pop_options(rest, {"--bits"})
    rest, width, bare = _pop_width(rest)
    rest = _split_positional(rest, set())
    _check_count("generate", rest, 2, bare_width=bare)
    try:
        program = generate(rest[0], rest[1], width)
        if "--bits" in options:
            bits = options["--bits"]
            if set(bits) - {"0", "1"} or not bits:
                _fail(f"--bits must be a string of 0s and 1s, got {bits!r}")
            # The width applies to the *filled* program: a template is left
            # unwrapped because no wrapper treats a {Xi} slot as a token.
            program = instantiate(rest[0], program, [int(b) for b in bits], width)
    except EsolangError as exc:
        _fail(str(exc))
    print(program)


def _run(rest: list[str]) -> None:
    """Run a program through its interpreter and write its output."""
    rest, options = _pop_options(rest, {"--timeout"})
    rest = _split_positional(rest, set())
    _check_count("run", rest, 2)
    language, path = rest[0], rest[1]
    timeout = _timeout_of(options)
    program = _read_program(path)
    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        output = run(language, program, stdin, timeout)
    except TemplateError as exc:
        _fail(_template_hint(exc, language))
    except EsolangError as exc:
        # A usage error (an unknown language) is still 2; anything the
        # program itself did is the program's failure, and exits 1.
        _fail(str(exc), 2 if isinstance(exc, ValueError) else 1)
    sys.stdout.write(output)
    # Piped output stays byte-exact -- it gets compared and diffed -- but a
    # result with no trailing newline runs into the next shell prompt.
    if output and not output.endswith("\n") and sys.stdout.isatty():
        sys.stdout.write("\n")
    # A program that printed nothing is a legal program, and also what you
    # get from an empty file or the wrong path.  Say so on a terminal, where
    # the alternative is a blank line and no way to tell the two apart; a
    # pipe still receives exactly the empty output.
    if not output and sys.stdout.isatty():
        sys.stderr.write(
            f"{language}: the program ran and printed nothing"
            f"{' (the file is empty)' if not program.strip() else ''}\n"
        )


def main() -> None:
    """Dispatch the ``esolangs`` subcommands."""
    argv = sys.argv[1:]
    if not argv:
        sys.stderr.write(USAGE)
        sys.exit(2)

    cmd, rest = argv[0], argv[1:]
    # Accepted after a subcommand too.  The top-level help advertises it
    # without saying where it goes, and `esolangs list --version` answering
    # "unknown option" is a strange way to learn that.
    if {"--version", "-V"} & set(argv):
        print(f"esolangs {__version__}")
        sys.exit(0)
    if cmd in ("--help", "-h", "help"):
        sys.stdout.write(HELP[rest[0]] if rest and rest[0] in HELP else USAGE)
        sys.exit(0)
    if cmd not in HELP:
        _fail(f"unknown command: {cmd}\n\n{USAGE}")
    if {"--help", "-h"} & set(rest):
        sys.stdout.write(HELP[cmd])
        sys.exit(0)

    {
        "list": _list,
        "encode": _encode,
        "generate": _generate,
        "run": _run,
        "debug": _debug,
    }[cmd](rest)


if __name__ == "__main__":
    main()
