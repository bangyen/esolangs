"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                         list the supported languages
    esolangs describe <language>          print its input shape and where
                                          the answer lands
    esolangs encode <language> <bits>     print the stdin those bits need
    esolangs generate <language> <table>  print a program computing a table
                                          (``--width N`` wraps it to N columns)
    esolangs run <language> <file>        run a program through its interpreter
                                          (``--judge`` prints the answer bit)
    esolangs read-answer <language>       print the answer bit in a program's
                                          output, read from stdin
    esolangs debug <language> <file>      run under the breakpoint/watch VM

Every subcommand takes ``--help``.  For anything else, invoke the module
directly with ``python -m``.

``describe`` and ``read-answer`` are here because the two facts that decided
every wrong answer this tool ever handed out -- how a language wants its
input bits, and where in the output its answer sits -- were readable from
Python and from nowhere else.  A shell user could run all nine of the
languages that do not simply print their answer, and could not judge one of
them: A Painter Ant's answer is a mark on one cell of an eleven-line grid.

Exit codes separate the failures a caller handles differently: **2** is a
usage error (an unknown command, option, or language -- nothing ran), **1**
is the program's own failure (it read past its input, halted on an invalid
operation, was a template), and **124** is a run stopped by ``--timeout``,
after timeout(1).  That last one used to be 1 as well, which left the three
languages whose answer *is* a timeout indistinguishable from a crash.  Only
an unexpected error still reaches the terminal as a traceback, which is what
a traceback should mean.
"""

import sys
from collections.abc import Iterable, Sequence
from difflib import get_close_matches
from typing import cast

from esolangs import (
    __version__,
    check_runnable,
    describe,
    encode_inputs,
    generate,
    instantiate,
    list_languages,
    read_answer,
    run,
)
from esolangs.debugger import make_debugger
from esolangs.exceptions import EsolangError, ExecutionTimeoutError, TemplateError
from esolangs.registry import LANGUAGES
from esolangs.tools.wrap import DEFAULT_WIDTH

USAGE = """usage: esolangs <command> [...]

commands:
  list [--details]            list the supported languages
  encode <language> <bits>    print the stdin that feeds those bits
  generate [--width [N]] [--bits BITS] <language> <truth-table>
                              print a program computing a truth table
                              (--width wraps it; --bits fills a template)
  describe <language>         print how that language reads its input and
                              where it puts the answer
  run [--timeout S] [--judge] <language> <file>
                              run a program through its interpreter
                              (--judge prints the answer bit instead)
  read-answer <language>      read a program's output on stdin and print
                              the answer bit it carries
  debug [--steps N] [--watch-cell I] [--break-on-output S] <language> <file>
                              run under the debugger and report where it
                              stopped, plus any watched cell's history

Language names are case-insensitive.  `esolangs <command> --help` describes
one command in full; `--version` prints the version.

examples:
  esolangs list
  esolangs describe Fargo
  esolangs encode Grapheme 10
  esolangs generate Circlefuck 0110
  esolangs generate --width brainfuck 10010110
  esolangs generate --bits 10 Minifuck 0110
  esolangs run Circlefuck hello.txt
  esolangs encode LaserFuck 10 | esolangs run --judge LaserFuck prog.txt
  esolangs debug --steps 20 --watch-cell 0 brainfuck prog.txt
"""

HELP = {
    "encode": """usage: esolangs encode <language> <bits>

Print the stdin that feeds <bits> to a <language> program, so it can be
piped straight into `esolangs run`:

    esolangs encode Taglate 101 | esolangs run Taglate prog.txt

Most languages read one 0/1 line per bit and this is no more than what you
would have typed.  Four are not most languages, and each fails silently if
you guess: Grapheme spells its bits %/A, Clockwise wants them all on one
line, Fargo wants the row index as one decimal number, and Taglate pads an
odd input count with a leading zero line.  `esolangs describe <language>`
prints which of those you are dealing with.

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
    "run": """usage: esolangs run [--timeout S] [--judge] <language> <program-file>

Run a program through its interpreter and print what it writes.

The program is read from <program-file>; its input is this command's stdin.
Most languages read one line per input bit, but four do not: Grapheme reads
%/A rather than 0/1, Clockwise takes every bit on one line, Fargo takes the
row index as one decimal number, and Taglate pads an odd input count with a
leading zero line, so its 3-input programs read four.  Feeding the wrong
encoding is answered with a wrong result, not an error, so check
`esolangs describe <language>` -- or have `esolangs encode` spell it for you:

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
                     A timeout exits 124, distinct from a program error's 1.
  --judge            print the answer bit -- 0 or 1 -- instead of the raw
                     output.  Nine languages do not simply print their
                     answer: six dump their whole final state with the
                     answer at a fixed place in it (RAM0's is its `z`
                     register; A Painter Ant marks the ant's cell `o` or
                     `@`), and three answer by terminating or not.  Judging
                     needs `--timeout` for those three, since not
                     terminating is what the 1 looks like.
""",
    "describe": """usage: esolangs describe <language>

Print what a language does with its input bits and where it puts the answer.

The fields are the ones the Python API returns from `esolangs.describe`:
its state model and interpreter, whether it has a truth-table generator and
whether that generator embeds the bits (`--bits`) or reads them from stdin,
the input shape and alphabet, and how to find the answer in the output.

This exists because those facts decided every wrong answer anyone got out
of this tool, and the only place they were readable was a Python session.

examples:
  esolangs describe Fargo
  esolangs describe "A Painter Ant"
""",
    "read-answer": """usage: esolangs read-answer <language>

Read a program's output on stdin and print the answer bit it carries.

For most languages the answer is the last thing printed and this is barely
more than `tail`.  For nine it is not: six dump their entire final machine
state, and the answer sits at a fixed place in it -- RAM0's in its `z`
register three lines from the end, A Painter Ant's as the mark on the ant's
own cell (`o` for 0, `@` for 1) somewhere in an eleven-line grid.  Working
that out by hand meant generating all four rows and diffing them.

The three languages that answer by terminating have no output to read, so
they are refused here and named: use `run --judge --timeout S` instead.

examples:
  esolangs encode LaserFuck 10 | esolangs run LaserFuck p.txt \
    | esolangs read-answer LaserFuck
  esolangs run --judge --timeout 10 123 prog.txt
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

#: Flags every subcommand accepts, so a near miss on one of them is
#: suggested by whichever subcommand it was typed after.
_GLOBAL_FLAGS = {"--help", "--version"}

#: A run stopped by its ``--timeout``, following timeout(1).  Distinct from
#: a program error's 1, which it shared: for the three languages that answer
#: by not terminating, the timeout is the *answer*, and a script had no way
#: to tell that from the program having broken.
_TIMEOUT_EXIT = 124

#: Each command's positional arguments, in order, so a missing one can be
#: named rather than left to be inferred from the usage line.
_ARGUMENTS = {
    "encode": ("<language>", "<bits>"),
    "generate": ("<language>", "<truth-table>"),
    "run": ("<language>", "<program-file>"),
    "debug": ("<language>", "<program-file>"),
    "describe": ("<language>",),
    "read-answer": ("<language>",),
}


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


def _shell_hint(message: str, language: str) -> str:
    """Re-point ``encode``'s refusal at the flag that does the same job.

    Same problem as :func:`_template_hint` and the sibling it was written
    for: ``encode Minifuck 10`` was answered with "pass the bits to
    instantiate() instead", and ``instantiate()`` is not a thing you can
    type at a shell.  The flag that embeds bits is ``generate --bits``.
    """
    pointer = "pass the bits to instantiate() instead"
    if pointer not in message:
        return message
    head = message.split(pointer)[0]
    return (
        f"{head}embed them in the program instead: "
        f"esolangs generate --bits <bits> {language} <table>"
    )


def _swapped_hint(language: str, table: str) -> str:
    """Return a hint when the language and truth-table arguments look swapped.

    ``generate 0110 brainfuck`` was answered with "unknown language: 0110",
    which is true and unhelpful: a power-of-two run of 0s and 1s in the
    language slot is a swap, not a language nobody has implemented.
    """
    looks_like_table = bool(language) and not set(language) - {"0", "1"}
    if not looks_like_table:
        return ""
    n = len(language).bit_length() - 1
    if len(language) != 2**n or n < 1:
        return ""
    return (
        f"; {language!r} looks like a truth table -- the language comes "
        f"first: esolangs generate {table} {language}"
    )


def _did_you_mean(word: str, known: Iterable[str]) -> str:
    """Return a ``did you mean`` clause for ``word``, or an empty string.

    Language names have had suggestions for a while and option names had
    none, so ``--wdith 40`` was a flat "unknown option" while ``Brainfck``
    got helped.  Same cutoff as :func:`esolangs.registry.resolve` uses.
    """
    close = get_close_matches(word, sorted(known), n=2, cutoff=0.6)
    if not close:
        return ""
    return f"; did you mean {' or '.join(close)}?"


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


def _split_positional(
    rest: list[str],
    known: set[str],
    vocabulary: set[str] = frozenset(),  # type: ignore[assignment]
) -> list[str]:
    """Return ``rest``'s positionals, refusing any unrecognized option.

    ``vocabulary`` is only for the did-you-mean: the value-taking options
    have already been consumed by the time this runs, so ``known`` no
    longer contains them and a misspelling of one had nothing to match
    against -- ``--wdith`` was a flat "unknown option" while ``Brainfck``
    got a suggestion.  The caller names its full option set here.

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
            name = arg.partition("=")[0]
            suggest = set(known) | set(vocabulary) | _GLOBAL_FLAGS
            _fail(f"unknown option: {arg}{_did_you_mean(name, suggest)}")
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
        # And say which one is missing.  The synopsis alone left the reader
        # to diff what they typed against a usage line -- easy for two
        # arguments, and it is exactly the two-argument commands that get
        # here.  ``_ARGUMENTS`` names them in order.
        missing = _ARGUMENTS.get(command, ())[len(args) : wanted]
        named = f"\n\nmissing {', '.join(missing)}" if missing else ""
        _fail(f"{synopsis}{named}")
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
            following = rest[i + 1] if i + 1 < len(rest) else None
            if following is None or not _is_int(following):
                # A bare ``--width`` has no value to quote, so the option
                # itself is what a repeat report names.
                seen["--width"] = arg
                width = DEFAULT_WIDTH
                bare = True
                i += 1
                continue
            value = following
            # The *value*, like every other repeatable option reports.  This
            # said ``first was '--width'``, which is the one thing the reader
            # already knows and omits the number they have to go and find.
            seen["--width"] = value
            i += 2
        elif arg.startswith("--width="):
            _refuse_repeat(seen, "--width")
            value = arg.split("=", 1)[1]
            seen["--width"] = value
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
        _fail(_shell_hint(str(exc), language))


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
    # The legend lived in `list --help` only, so the marker columns arrived
    # unexplained for anyone who ran the thing before reading about it.
    print(f"{'language'.ljust(width)}  gen=generator tmpl={{Xi}} ex=example")
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
    rest = _split_positional(rest, set(), options_taken)
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
    rest = _split_positional(rest, set(), {"--bits", "--width"})
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
        _fail(f"{exc}{_swapped_hint(rest[0], rest[1])}")
    print(program)


def _describe(rest: list[str]) -> None:
    """Print a language's input shape, answer location and capabilities."""
    rest = _split_positional(rest, set())
    _check_count("describe", rest, 1)
    try:
        facts = describe(rest[0])
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    width = max(len(key) for key in facts)
    for key, value in facts.items():
        if value is None or value == "":
            continue
        shown = "\n".join(str(v) for v in value) if isinstance(value, list) else value
        if isinstance(value, tuple):
            shown = " ".join(str(v) for v in value)
        print(f"{key.ljust(width)}  {shown}")


def _read_answer(rest: list[str]) -> None:
    """Read a program's output on stdin and print the answer bit in it."""
    rest = _split_positional(rest, set())
    _check_count("read-answer", rest, 1)
    language = rest[0]
    try:
        facts = describe(language)
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    if facts["answer_mode"] == "termination":
        polarity = cast("tuple[str, str]", facts["answer_encoding"])
        zero, one = polarity
        _fail(
            f"{facts['name']} answers by {zero} for a 0 and {one} for a 1, so "
            f"there is no output to read; use: esolangs run --judge "
            f"--timeout <seconds> {facts['name']} <program-file>"
        )
    output = "" if sys.stdin.isatty() else sys.stdin.read()
    if not output.strip():
        _fail(
            f"nothing on stdin to read an answer out of; pipe a program's "
            f"output in: esolangs run {language} prog.txt | esolangs "
            f"read-answer {language}"
        )
    try:
        print(read_answer(language, output))
    except EsolangError as exc:
        _fail(str(exc))


def _judge(language: str, output: str, mode: object) -> str:
    """Return the answer bit for a finished run, or exit explaining why not."""
    if mode == "termination":
        # It halted, and halting is this group's 0.  The 1 is the timeout,
        # which never reaches here -- ``_run`` reports it before judging.
        return "0"
    try:
        return read_answer(language, output)
    except EsolangError as exc:
        _fail(str(exc), 1)
        raise  # pragma: no cover - unreachable; _fail exits


def _run(rest: list[str]) -> None:
    """Run a program through its interpreter and write its output."""
    rest, options = _pop_options(rest, {"--timeout"})
    rest = _split_positional(rest, {"--judge"}, {"--timeout", "--judge"})
    judge = "--judge" in rest
    rest = [arg for arg in rest if arg != "--judge"]
    _check_count("run", rest, 2)
    language, path = rest[0], rest[1]
    timeout = _timeout_of(options)
    program = _read_program(path)
    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        mode = describe(language)["answer_mode"]
        name = describe(language)["name"]
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    if mode == "termination" and timeout is None:
        if judge:
            # Judging needs the bound, so this is a refusal rather than the
            # warning below -- and only one of the two is printed.
            _fail(
                f"--judge needs --timeout for {name}: its answer for a 1 is "
                f"that the program never stops, so there is nothing to wait "
                f"for without a bound"
            )
        # The default path for these three is an unbounded run of a program
        # written to loop forever, which is a hang with no output and no
        # explanation.  Not refused -- a program whose answer is 0 halts,
        # and running one unbounded is perfectly sensible -- but said aloud.
        sys.stderr.write(
            f"{name}: this language answers 1 by not terminating, so a "
            f"program with that answer will run until you stop it; pass "
            f"--timeout SECONDS to bound it\n"
        )
    try:
        output = run(language, program, stdin, timeout)
    except TemplateError as exc:
        _fail(_template_hint(exc, language))
    except ExecutionTimeoutError as exc:
        if mode == "termination":
            # The timeout *is* the answer here, so it is not a failure.
            if judge:
                print("1")
                return
            sys.stderr.write(
                f"{exc}\nnote: {name} answers 1 by not terminating, so for a "
                f"generated truth-table program this timeout is the answer 1"
                f" -- `--judge` prints it as one\n"
            )
            sys.exit(_TIMEOUT_EXIT)
        # Distinct from a program error's 1, following timeout(1), so a
        # script can tell "ran out of time" from "the program broke".  Those
        # shared exit 1, which made the three termination languages'
        # answer indistinguishable from a crash.
        _fail(str(exc), _TIMEOUT_EXIT)
    except EsolangError as exc:
        # A usage error (an unknown language) is still 2; anything the
        # program itself did is the program's failure, and exits 1.
        _fail(str(exc), 2 if isinstance(exc, ValueError) else 1)
    if judge:
        print(_judge(language, output, mode))
        return
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
        "describe": _describe,
        "encode": _encode,
        "generate": _generate,
        "run": _run,
        "read-answer": _read_answer,
        "debug": _debug,
    }[cmd](rest)


if __name__ == "__main__":
    main()
