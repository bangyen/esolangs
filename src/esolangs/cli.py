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

from __future__ import annotations

import json
import sys
import threading
import warnings
from collections.abc import Iterable, Sequence
from contextlib import AbstractContextManager, nullcontext
from difflib import get_close_matches
from typing import cast

from esolangs import (
    __version__,
    check_runnable,
    check_stdin,
    describe,
    encode_inputs,
    evaluate,
    generate,
    instantiate,
    list_languages,
    read_answer,
    run,
)
from esolangs._validate import check_timeout
from esolangs.debugger import make_debugger
from esolangs.exceptions import (
    EsolangError,
    ExecutionTimeoutError,
    GeneratorCapError,
    TemplateError,
)
from esolangs.registry import LANGUAGES, SUGGESTION_CUTOFF
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
  run [--timeout S] [--judge] [--table T] <language> <file>
                              run a program through its interpreter
                              (--judge prints the answer bit instead)
  check-stdin [--table T] <language>
                              judge stdin against what that language reads,
                              without running anything
  read-answer <language>      read a program's output on stdin and print
                              the answer bit it carries
  answer <language> <truth-table> <bits>
                              generate, feed those bits, run, and print the
                              one answer bit
  verify <language> <truth-table>
                              generate, run every row, and report whether
                              the program computes that table
  evaluate <language> <truth-table>
                              the same, printing the table it computed
  debug [--steps N] [--timeout S] [--watch-cell I] [--break-on-output S]
        <language> <file>
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
  esolangs answer brainfuck 0110 10
  esolangs verify Fargo 10010110
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
    "list": """usage: esolangs list [--details] [--json]

List the supported languages, one per line.

options:
  --details   add a marker column per language:
                gen    has a boolean generator
                tmpl   that generator returns a {Xi} template rather than a
                       runnable program -- see `esolangs generate --help`
                ex     a committed program in examples/
  --json      print a JSON array instead: names alone, or with --details
              an object per language carrying the same three facts as
              booleans, so nobody has to parse the marker column.
""",
    "generate": f"""usage: esolangs generate [--width [N]] [--bits BITS] <language>
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
               `esolangs describe <language>` reports which of three
               things it does, as `width_effect`: `wrap` reflows the
               finished program between whole tokens, `layout` hands the
               width to the generator as a *hint* (LaserFuck asked for 10
               gives 18, asked for 200 gives 56, because it folds runs
               rather than breaking lines), and `none` ignores it, because
               the language's newlines are semantic or it rejects them.  A template is
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
leading zero line, so its 3-input programs read four.  Stdin is checked
against that shape: this command warns, and `--judge` refuses outright.  A
shape indistinguishable from a legitimate one still answers the wrong row,
so check `esolangs describe <language>` -- or have `esolangs encode` spell
it for you:

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
  --table TABLE      the truth table the program was generated from.  Adds
                     the bit *count* to the stdin check, which is the one
                     thing a shape check cannot do on its own: three lines
                     fed to a two-input program, or a row index out of
                     range, are only wrong relative to an arity.
  --judge            print the answer bit -- 0 or 1 -- instead of the raw
                     output.  Nine languages do not simply print their
                     answer: six dump their whole final state with the
                     answer at a fixed place in it (RAM0's is its `z`
                     register; A Painter Ant marks the ant's cell `o` or
                     `@`), and three answer by terminating or not.  Judging
                     needs `--timeout` for those three, since not
                     terminating is what the 1 looks like.
""",
    "answer": """usage: esolangs answer [--timeout S] <language> <truth-table> <bits>

Generate a program for <truth-table>, feed it <bits>, run it, and print the
single answer bit.

This is `verify` for one row instead of all of them.  Everything it does was
already possible -- generate to a file, encode the bits, pipe them in, judge
the output -- but that is four commands and a temporary file, and the
encoding step is the one people get wrong.  Nothing here can be
mis-encoded: the bits go in as bits.

  esolangs answer brainfuck 0110 10        -> 1
  esolangs answer Fargo 10010110 101       -> 1
  esolangs answer "A Painter Ant" 0110 01  -> 1

Works for every language, including the seventeen whose generators embed
their inputs, the six that dump their whole final state, and the three that
answer by not terminating -- for those a bound is needed, and the default
below is applied.

options:
  --timeout SECONDS  bound the run.  Defaults to 5 seconds for the three
                     languages whose answer for a 1 is that the program
                     never stops, and to none for the rest.
""",
    "verify": """usage: esolangs verify [--timeout S] <language> <truth-table>

Generate a program for <truth-table>, run it on every row of its input
space, and report whether it computes that table.

Prints `ok` and exits 0 on a match.  On a mismatch it prints the table the
program actually computed beside the one you asked for, and exits 1.

**It checks the generator, not a file of yours.**  The program it runs is
the one it just generated, so `ok` means "this language's generator builds
a correct program for this table" -- it cannot tell you anything about a
program you wrote.  For that, run yours and judge the output:
`esolangs run --judge <language> <your-file>`.

This is the whole round trip in one command: generate, encode each row's
bits in whatever shape the language wants, run, and read the answer out of
whatever the program printed.  Doing it by hand means a shell loop over
2**n rows -- which is what the Python API's `esolangs.verify` was already
for, and what a CLI-only user had to write out.

A generator may refuse a table as too big for it; that is reported and
exits 2, since nothing ran.

options:
  --timeout SECONDS  bound each row.  The three languages that answer 1 by
                     not terminating do *not* pay it on every 1-row: those
                     rows are settled by a repeated machine state, which
                     proves the loop in microseconds, so the bound is only
                     the backstop for a program that diverges by growing.
                     A sixteen-row 123 table at --timeout 30 takes under a
                     second, not eight minutes.

examples:
  esolangs verify brainfuck 0110
  esolangs verify --timeout 5 123 0110
""",
    "evaluate": """usage: esolangs evaluate [--timeout S] <language> <truth-table>

Print the truth table a generated <language> program actually computes.

`verify` with the comparison left to you: the output is a binary string the
same length as <truth-table>, so a mismatch shows which rows disagree
rather than collapsing to a yes or no.  Exits 0 whenever the program ran.

examples:
  esolangs evaluate brainfuck 0110
  esolangs evaluate "A Painter Ant" 10010110
""",
    "check-stdin": """usage: esolangs check-stdin [--table T] <language>

Read stdin and say whether it is what <language> wants, without running a
program.

Exits 0 and says nothing when it is fine.  Otherwise it names what is wrong
and exits 2 -- the wrong alphabet, the wrong number of lines, a row index
with a leading zero, and with --table the wrong bit count or an index out of
range.

This is the check `run` applies as a warning and `run --judge` applies as a
refusal, on its own, so a pipeline can validate input before spending a run
on it.

examples:
  esolangs encode Grapheme 10 | esolangs check-stdin Grapheme
  printf '1\\n0\\n1\\n' | esolangs check-stdin --table 0110 brainfuck
""",
    "describe": """usage: esolangs describe [--json] <language>

Print what a language does with its input bits and where it puts the answer.

The fields are the ones the Python API returns from `esolangs.describe`:
its state model and interpreter, whether it has a truth-table generator and
whether that generator embeds the bits (`--bits`) or reads them from stdin,
the input shape and alphabet, and how to find the answer in the output.

This exists because those facts decided every wrong answer anyone got out
of this tool, and the only place they were readable was a Python session.

options:
  --json      print `esolangs.describe` verbatim as JSON.  The default
              layout is for reading and loses things on the way: a pair
              prints as `0 1` with no way back to two values, an empty
              field is dropped rather than shown as empty, and the closing
              `input` line is a sentence this command composes and not a
              key at all.  --json is the dict, exactly.

examples:
  esolangs describe Fargo
  esolangs describe "A Painter Ant"
  esolangs describe --json brainfuck
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
  esolangs generate --bits 01 123 0110 > p123.txt
  esolangs run --judge --timeout 10 123 p123.txt
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


def _null_context() -> AbstractContextManager[None]:
    """Return a do-nothing ``with`` target, for an already-bounded run."""
    return nullcontext()


#: How long a blocking stdin read waits before it says that it is waiting.
#: Shorter than the run notice: a read that has not finished is far more
#: likely to be a mistake than a program that is still going.
_WAITING_NOTICE_AFTER = 3.0

#: The most a program file may hold.  Two orders of magnitude above the
#: largest program any generator here produces.
_MAX_PROGRAM_BYTES = 1024 * 1024

#: How long to wait for a program file that is not delivering, when no
#: ``--timeout`` was given to bound it instead.
_READ_DEADLINE = 10.0

#: How long an unbounded run goes before it says that it is unbounded.
#: A constant so a test can shorten it rather than wait.
_UNBOUNDED_NOTICE_AFTER = 10.0


class _UnboundedNotice:
    """Print one line if an unbounded run is still going after a while.

    ``run`` and ``debug`` take no bound by default, which is right -- most
    of these programs halt, and imposing a budget nobody chose would be
    worse.  But several languages loop forever *by design*, and the
    unbounded path on one of those is an indefinite spin with no output and
    nothing on screen to suggest a cause; one reader killed it after eight
    CPU-minutes.

    So the default is unchanged and the silence is not: a timer fires once,
    names the flag, and is cancelled the moment the run finishes.  Nothing
    is printed for the ordinary case of a program that halts promptly.
    """

    def __init__(self, command: str) -> None:
        """Arm the notice for ``command``, which names the flag to pass."""
        self._timer = threading.Timer(
            _UNBOUNDED_NOTICE_AFTER, self._say, args=(command,)
        )
        self._timer.daemon = True

    @staticmethod
    def _say(command: str) -> None:
        """Write the one line, from the timer thread."""
        sys.stderr.write(
            f"still running after {_UNBOUNDED_NOTICE_AFTER:.0f}s with no bound; "
            f"several of these languages loop forever by design -- "
            f"`esolangs {command} --timeout SECONDS` stops one\n"
        )

    def __enter__(self) -> _UnboundedNotice:
        """Start the timer."""
        self._timer.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        """Cancel it, whether the run finished or raised."""
        self._timer.cancel()


#: A run stopped by its ``--timeout``, following timeout(1).  Distinct from
#: a program error's 1, which it shared: for the three languages that answer
#: by not terminating, the timeout is the *answer*, and a script had no way
#: to tell that from the program having broken.
_TIMEOUT_EXIT = 124

#: The two input shapes whose bit count cannot be recovered from stdin.
#: Every other language reads a line per bit, so a run can compare what it
#: took against what it was given; these two read a single line -- all the
#: bits at once, or a row index -- and a wrong count is indistinguishable
#: from a right one without knowing the arity.
_UNCOUNTABLE_SHAPES = ("one_line", "row_index")

#: Each command's positional arguments, in order, so a missing one can be
#: named rather than left to be inferred from the usage line.
_ARGUMENTS = {
    "encode": ("<language>", "<bits>"),
    "generate": ("<language>", "<truth-table>"),
    "run": ("<language>", "<program-file>"),
    "debug": ("<language>", "<program-file>"),
    "describe": ("<language>",),
    "read-answer": ("<language>",),
    "check-stdin": ("<language>",),
    "answer": ("<language>", "<truth-table>", "<bits>"),
    "verify": ("<language>", "<truth-table>"),
    "evaluate": ("<language>", "<truth-table>"),
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


def _looks_like_a_table(value: str) -> bool:
    """Whether ``value`` is a power-of-two run of 0s and 1s."""
    if not value or set(value) - {"0", "1"}:
        return False
    n = len(value).bit_length() - 1
    return len(value) == 2**n and n >= 1


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
    close = get_close_matches(word, sorted(known), n=2, cutoff=SUGGESTION_CUTOFF)
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
    command: str,
    args: list[str],
    wanted: int,
    *,
    bare_width: bool = False,
    eaten: str = "",
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
        _fail(f"{synopsis}{named}{eaten}")
    if len(args) > wanted:
        # A name with spaces in it arrives as several positionals, and the
        # complaint named whichever word landed past the count.  The
        # resolver can match the joined words; it was never asked.
        joined = " ".join(args)
        try:
            from esolangs.registry import resolve

            resolved = resolve(joined)
        except EsolangError:
            resolved = None
        if resolved is not None:
            _fail(
                f"unexpected argument: {args[wanted]!r}; did you mean the "
                f"language {resolved!r}?  Quote a name with spaces in it: "
                f'"{resolved}"'
            )
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
    """Return the ``--timeout`` seconds, or None, refusing a bad value.

    The *value* checks are :func:`esolangs.check_stdin`'s neighbour
    :func:`esolangs._validate.check_timeout`, not a second copy: this had
    its own rules for zero, negatives and non-finite values, and the
    library then grew a floor and a ceiling that this did not know about.
    A ``--timeout 1e10`` therefore got past here and overflowed the C
    timer three calls later, as a raw ``OverflowError``.
    """
    if "--timeout" not in options:
        return None
    try:
        seconds = float(options["--timeout"])
    except ValueError:
        _fail(f"--timeout must be a number, got {options['--timeout']!r}")
    try:
        check_timeout(seconds)
    except EsolangError as exc:
        # Re-worded from ``timeout`` to ``--timeout``: the library names the
        # parameter, and this names the flag the reader typed.
        _fail(str(exc).replace("timeout must", "--timeout must", 1))
    return seconds


def _read_program(path: str, timeout: float | None = None) -> str:
    """Return the program in ``path``, or exit with a usage error.

    The trailing newline is the *file's*, not the program's, and three
    interpreters (CV(N)(C), Grapheme, NoComment) reject one as an unknown
    command.  Since ``esolangs generate ... > prog.txt`` writes that newline,
    keeping it meant this tool produced programs its own ``run`` refused,
    and the three committed examples could not be run at all.
    """
    # The *open* is on the thread as well as the read.  Opening a FIFO
    # blocks until a writer appears, so bounding only the read left the
    # command hanging one line earlier -- which is what a reader saw when
    # ``--timeout 2`` did not stop ``run`` on an unfed pipe.
    return _bounded_read(path, timeout).rstrip("\n")


def _shape_warning(
    facts: dict[str, object], stdin: str, table: str | None = None
) -> str:
    """Return the library's complaint about ``stdin``, or ``''``.

    The checks themselves live in :func:`esolangs.check_stdin` now.  They
    were written here, and a Python caller had no way to reach them -- the
    one place the API was weaker than this command line, and the guards in
    question are the ones every reader of this package trips over.  Two
    copies would have drifted, as two copies of a check in this repository
    have twice before.
    """
    if not facts["reads_input"]:
        return ""
    try:
        check_stdin(str(facts["name"]), stdin, table)
    except EsolangError as exc:
        # Some of these already name the exact command; appending the
        # generic pointer to those said "esolangs encode" twice in one line.
        tail = (
            ""
            if "esolangs encode" in str(exc)
            else ("; `esolangs encode` builds the right stdin")
        )
        return f"{exc}{tail}"
    return ""


def _note(message: str) -> None:
    """Write one advisory line to stderr, without Python's warning framing."""
    sys.stderr.write(f"{message}\n")


def _bounded_read(path: str, timeout: float | None) -> str:
    """Open and read ``path``, with a size cap and a deadline.

    Both halves on a daemon thread, because both can block forever and
    neither can be interrupted from Python: ``open`` on a FIFO waits for a
    writer, and a read of a character device never ends -- ``/dev/zero``
    reached 3.9 GB of resident memory, ignored ``--timeout``, and ignored
    SIGINT, because the interpreter sat inside one C-level call throughout.

    The size cap is two orders of magnitude above the largest program any
    generator here produces.  The deadline is the caller's ``--timeout``
    when there is one, so the bound they asked for covers the whole
    command rather than only the part after the file is in memory.
    """
    box: list[str | BaseException] = []

    def _slurp() -> None:
        try:
            with open(path) as handle:
                box.append(handle.read(_MAX_PROGRAM_BYTES + 1))
        except BaseException as exc:
            box.append(exc)

    reader = threading.Thread(target=_slurp, daemon=True)
    reader.start()
    waited = timeout if timeout is not None else _READ_DEADLINE
    reader.join(waited)
    if reader.is_alive():
        _fail(
            f"gave up reading {path} after {waited:.0f}s -- it is not "
            f"delivering data (a FIFO with no writer, or a device)",
            _TIMEOUT_EXIT,
        )
    result = box[0] if box else ""
    if isinstance(result, OSError):
        _fail(f"cannot read {path}: {result}")
    if isinstance(result, UnicodeDecodeError):
        # Its own clause: ``UnicodeDecodeError`` is a ``ValueError``, not an
        # ``OSError``, so pointing ``run`` at a PNG used to dump a raw
        # traceback where every other unreadable file gets one clean line.
        _fail(f"cannot read {path}: not text ({_decode_note(result)})")
    if isinstance(result, BaseException):
        raise result
    if len(result) > _MAX_PROGRAM_BYTES:
        _fail(
            f"{path} is larger than the {_MAX_PROGRAM_BYTES // 1024} KiB this "
            f"reads; the largest program this package generates is far under "
            f"it, so this is almost certainly not a program"
        )
    return result


def _decode_note(exc: UnicodeDecodeError) -> str:
    """Describe where a decode failed, without the codec's full sentence."""
    return f"invalid UTF-8 at byte {exc.start}"


def _read_stdin(timeout: float | None = None, hint: str = "") -> str:
    """Return this command's stdin, or exit if it is not text or never comes.

    Shared by the commands that read it.  Each called ``sys.stdin.read()``
    directly and each therefore had the same hole: a program's binary output
    piped into ``read-answer`` crashed with a traceback rather than being
    refused.

    **The read is bounded and announced.**  ``sys.stdin.read()`` blocks
    until end-of-file, so a pipe that is open and never written -- which is
    what a terminal looks like, and what a parent process that forgot to
    close stdin gives you -- hung this command forever with nothing on
    screen.  ``--timeout`` did not help, because it bounds *execution* and
    this happens before any program runs.

    So: the read happens on a daemon thread, ``--timeout`` bounds it as
    well, and an unbounded read that is still waiting says so.  A thread
    rather than :func:`select.select` because stdin here is not always a
    real file -- the tests supply an object with no ``fileno`` -- and this
    works for anything with a ``read``.
    """
    if sys.stdin.isatty():
        return ""
    box: list[str | BaseException] = []

    def _slurp() -> None:
        try:
            box.append(sys.stdin.read())
        except BaseException as exc:
            box.append(exc)

    reader = threading.Thread(target=_slurp, daemon=True)
    reader.start()
    with _WaitingNotice(hint):
        reader.join(timeout)
    if reader.is_alive():
        _fail(
            f"no input arrived on stdin within {timeout:.0f}s, and nothing "
            f"closed it{hint}",
            _TIMEOUT_EXIT,
        )
    result = box[0] if box else ""
    if isinstance(result, UnicodeDecodeError):
        _fail(f"cannot read stdin: not text ({_decode_note(result)})")
    if isinstance(result, BaseException):
        raise result
    return result


def _stdin_hint(facts: dict[str, object]) -> str:
    """Return a clause naming what this language wants on stdin, if anything.

    A language whose generator embeds its inputs usually wants nothing, and
    saying so is most of the help: the reader who typed `esolangs run RAM0
    prog.txt` and watched it wait was waiting for input the program was
    never going to ask for.

    *Usually*, not always -- the flag says the generated program reads no
    stdin, and three of those seventeen languages have an input command a
    hand-written program may still use.  So this suggests and does not
    skip.
    """
    if not facts["reads_input"] and facts["parameterized"]:
        return (
            f"; {facts['name']}'s generated programs embed their inputs and "
            f"read no stdin, so there is probably nothing to send -- close it"
        )
    return "; try: esolangs encode <language> <bits> | ..."


class _WaitingNotice:
    """Say, once, that this command is waiting for input that is not coming.

    The same shape as :class:`_UnboundedNotice` and for the same reason: the
    default is unchanged and the silence is not.
    """

    def __init__(self, hint: str = "") -> None:
        """Arm the notice, mentioning ``hint`` if there is one."""
        self._timer = threading.Timer(_WAITING_NOTICE_AFTER, self._say, args=(hint,))
        self._timer.daemon = True

    @staticmethod
    def _say(hint: str) -> None:
        """Write the one line, from the timer thread."""
        sys.stderr.write(
            f"still waiting for input on stdin after "
            f"{_WAITING_NOTICE_AFTER:.0f}s; nothing has closed it{hint}\n"
        )

    def __enter__(self) -> _WaitingNotice:
        """Start the timer."""
        self._timer.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        """Cancel it."""
        self._timer.cancel()


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
    rest = _split_positional(rest, {"--details", "--json"})
    details = "--details" in rest
    as_json = "--json" in rest
    _check_count("list", [a for a in rest if a not in {"--details", "--json"}], 0)
    if as_json:
        if not details:
            print(json.dumps(list_languages(), indent=2))
            return
        print(
            json.dumps(
                [
                    {
                        "name": name,
                        # The three the marker column encodes, spelled out.
                        "boolean_generator": facts["boolean_generator"],
                        "parameterized": facts["parameterized"],
                        "has_example": bool(facts["examples"]),
                    }
                    for name, facts in (
                        (name, describe(name)) for name in list_languages()
                    )
                ],
                indent=2,
            )
        )
        return
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
    options_taken = {
        "--steps",
        "--watch-cell",
        "--break-on-output",
        "--timeout",
        "--table",
    }
    # Options first, then the stray-flag check: a *value* can begin with a
    # dash (``--timeout -inf``), and a check that runs before the pairs are
    # consumed cannot tell one from a flag -- it answered that with
    # "unknown option: -inf" instead of "must be finite".
    rest, options = _pop_options(rest, options_taken)
    # Before the positional count, matching ``run``: a forgotten number made
    # the language the timeout's value and the complaint landed on the file.
    limit = _timeout_of(options)
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
    program = _read_program(path, limit)
    try:
        facts = describe(language)
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    stdin = _read_stdin(limit, _stdin_hint(facts))
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
    breakpoints_set = False
    if "--break-on-output" in options:
        if not options["--break-on-output"]:
            _fail("--break-on-output needs some text; every output contains ''")
        dbg.break_on_output(options["--break-on-output"])
        breakpoints_set = True
    watched = int(options["--watch-cell"]) if "--watch-cell" in options else None
    history = dbg.watch_cell(watched) if watched is not None else None
    steps = int(options["--steps"]) if "--steps" in options else None
    # A debugged program is one the caller is already unsure of, so a raise
    # here is a result to report rather than a crash to propagate: the
    # state up to the fault is the thing they asked to see.
    fault = None
    reason = None
    warning = _shape_warning(describe(language), stdin, options.get("--table"))
    if warning:
        sys.stderr.write(f"{warning}\n")
    # ``run`` gained this last round and ``debug`` did not, so `debug 123
    # prog.txt` -- the command you reach for precisely when something is
    # not stopping -- still hung with nothing on screen.  ``--steps`` counts
    # as a bound here as much as ``--timeout`` does, so a run that has one
    # is not told to pass one.
    bounded = steps is not None or limit is not None
    if describe(language)["answer_mode"] == "termination" and not bounded:
        sys.stderr.write(
            f"{describe(language)['name']}: this language answers 1 by not "
            f"terminating, so a program with that answer will run until you "
            f"stop it; pass --timeout SECONDS or --steps N to bound it\n"
        )
    try:
        with _UnboundedNotice("debug") if not bounded else _null_context():
            reason = dbg.run(steps, limit)
    except Exception as exc:
        fault = f"{type(exc).__name__}: {exc}"

    if breakpoints_set and reason != "breakpoint":
        # A breakpoint that never fires looks exactly like a program that
        # never reached it, and the report said nothing either way.
        sys.stderr.write("note: no breakpoint matched during this run\n")
    print(f"halted: {'yes' if dbg.halted else 'no'}")
    # Exit codes below, after the report is printed: a script that cannot
    # tell a clean halt from a crash has to parse prose, and `run` has had
    # this taxonomy for several rounds.  The state up to the fault is still
    # printed either way, which is the whole point of the command.
    # Always printed, so a script reading fixed field positions does not
    # break on the one case it most wants to parse.
    print(f"stopped: {reason if reason is not None else 'raised'}")
    print(f"ip: {dbg.ip}")
    print(f"output: {dbg.output!r}")
    if history is not None:
        values = list(history)
        # A `None` means the cell did not exist yet at that step -- the tape
        # had not grown that far, or the language has no such store.  The
        # all-`None` case was annotated and the *mixed* case was not, which
        # is the one where a reader actually needs telling: a row reading
        # `[None, None, 0, 0, ...]` otherwise looks like a value.
        if set(values) <= {None}:
            untouched = " (never written)"
        elif None in values:
            untouched = " (None: the cell did not exist yet at that step)"
        else:
            untouched = ""
        if set(values) <= {None}:
            # Verdict first, and no wall of Nones: a never-written cell used
            # to print four hundred of them and put "(never written)" at the
            # far right of a wrapped line.
            print(
                f"cell {options['--watch-cell']}: never written in "
                f"{len(values)} step(s)"
            )
        else:
            print(f"cell {options['--watch-cell']}: {_abridge(values)}{untouched}")
    if fault is not None:
        print(f"raised: {fault}")
        # 1, like ``run``: the program itself failed.  This exited 0 for
        # every outcome -- a clean halt, a timeout and a crash alike -- so a
        # script could not tell them apart without parsing the report.
        sys.exit(1)
    if reason == "timeout":
        sys.exit(_TIMEOUT_EXIT)


def _generate(rest: list[str]) -> None:
    """Print a program computing a truth table."""
    rest, options = _pop_options(rest, {"--bits"})
    before = list(rest)
    rest, width, bare = _pop_width(rest)
    rest = _split_positional(rest, set(), {"--bits", "--width"})
    # `--width` takes an *optional* N, so a truth table typed straight after
    # it is consumed as the width and the report lands on the table being
    # missing -- which is baffling when you did type one.
    eaten = ""
    if width is not None and not bare:
        for i, arg in enumerate(before[:-1]):
            value = before[i + 1]
            if arg == "--width" and _looks_like_a_table(value):
                eaten = (
                    f"\n\nnote: --width consumed {value!r}, which looks like a "
                    f"truth table; put the table after the language"
                )
    _check_count("generate", rest, 2, bare_width=bare, eaten=eaten)
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
    if (width is not None or bare) and describe(rest[0])["width_effect"] == "none":
        # Silently ignoring the flag was the sharpest half of the width
        # confusion: two identical programs, one of which was asked to be
        # narrower.  The languages that ignore it have semantic newlines or
        # reject them outright, so honouring it is not on the table --
        # saying so is.
        sys.stderr.write(
            f"note: --width has no effect on {describe(rest[0])['name']} -- "
            f"its newlines are part of the program, so it is emitted as the "
            f"generator built it\n"
        )
    print(program)


def _describe(rest: list[str]) -> None:
    """Print a language's input shape, answer location and capabilities."""
    rest = _split_positional(rest, {"--json"})
    as_json = "--json" in rest
    rest = [a for a in rest if a != "--json"]
    _check_count("describe", rest, 1)
    try:
        facts = describe(rest[0])
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    if as_json:
        # Verbatim, including the keys the reading layout hides: a caller
        # asking for JSON is not reading it, and a field that vanishes when
        # it is empty is the thing that makes a schema unusable.
        print(json.dumps(facts, indent=2))
        return
    # A template language reads no stdin, so its input shape and alphabet
    # are noise -- and ``input_shape`` is the field the README tells you to
    # trust.  Hidden here rather than dropped from ``describe()``, whose
    # keys stay uniform across all 69: a caller that iterates them without
    # branching is the pattern this package spent four rounds proving, and
    # a per-language schema would break it.
    hidden = set()
    if not facts["reads_input"] and facts["parameterized"]:
        hidden = {"input_shape", "input_encoding"}
    width = max(len(key) for key in facts)
    for key, value in facts.items():
        if value is None or value == "" or key in hidden:
            continue
        shown = "\n".join(str(v) for v in value) if isinstance(value, list) else value
        if isinstance(value, tuple):
            shown = " ".join(str(v) for v in value)
        print(f"{key.ljust(width)}  {shown}")
    if hidden:
        print(
            f"{'input'.ljust(width)}  none -- this generator embeds the bits "
            f"in the program: esolangs generate --bits <bits> "
            f"{facts['name']} <table>"
        )
    else:
        # The symmetric row.  A reader had ``input_encoding`` and
        # ``input_shape`` and had to compose them, while the template
        # languages got a sentence -- so the languages where getting it
        # wrong is possible were the ones told least plainly.
        print(f"{'input'.ljust(width)}  {_input_sentence(facts)}")


def _check_stdin(rest: list[str]) -> None:
    """Judge stdin against a language's declared shape, running nothing."""
    rest, options = _pop_options(rest, {"--table"})
    rest = _split_positional(rest, set(), {"--table"})
    _check_count("check-stdin", rest, 1)
    language = rest[0]
    try:
        facts = describe(language)
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    stdin = _read_stdin(hint="; pipe the input in, or close stdin")
    table = options.get("--table")
    try:
        check_stdin(str(facts["name"]), stdin, table)
    except EsolangError as exc:
        _fail(str(exc))
    # No note about ``--table`` here.  The first draft printed one whenever
    # it was absent, which is every call that is simply checking a shape --
    # advice on correct input, which is the thing this CLI has spent several
    # rounds removing.  ``check-stdin --help`` says what the flag adds.


def _input_sentence(facts: dict[str, object]) -> str:
    """Describe this language's stdin in one line, with an example.

    Composed from ``input_shape`` and ``input_encoding`` rather than stored,
    so a language that declares a new shape is described by declaring it.
    """
    zero, one = cast("tuple[str, str]", facts["input_encoding"])
    shape = str(facts["input_shape"])
    example = f"{one}{zero}"
    if shape == "row_index":
        return 'one decimal row index, e.g. "2" for the bits 10'
    if shape == "one_line":
        return f'every bit on one line, e.g. "{example}"'
    lines = f"{one}\\n{zero}"
    if shape == "line_per_bit_padded":
        return (
            f'one line per bit, e.g. "{lines}" -- and an odd count above one '
            f"is padded with a leading {zero} line"
        )
    return f'one line per bit, e.g. "{lines}"'


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
    output = _read_stdin(hint="; pipe a program's output in, or close stdin")
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


def _answer(rest: list[str]) -> None:
    """Generate, feed one row's bits, run, and print the answer bit."""
    rest, options = _pop_options(rest, {"--timeout"})
    timeout = _timeout_of(options)
    rest = _split_positional(rest, set(), {"--timeout"})
    _check_count("answer", rest, 3)
    language, table, bits = rest
    if set(bits) - {"0", "1"} or not bits:
        _fail(f"bits must be a string of 0s and 1s, got {bits!r}")
    try:
        facts = describe(language)
        name = str(facts["name"])
        row = [int(bit) for bit in bits]
        program = generate(name, table)
        if facts["parameterized"]:
            source, stdin = instantiate(name, program, row, truth_table=table), ""
        else:
            source, stdin = program, encode_inputs(name, row, table)
        if facts["answer_mode"] == "termination":
            # A bound is the answer here rather than a safeguard, so one is
            # supplied: this command exists to be a one-liner, and making a
            # reader discover that three of the sixty-nine need a flag would
            # defeat that.
            print(_diverging_answer(name, source, stdin, timeout or 5.0, facts))
            return
        print(read_answer(name, run(name, source, stdin, timeout)))
    except EsolangError as exc:
        # No ``TemplateError`` clause: this command generates the template
        # and fills it in the same breath, so it never hands an unfilled one
        # on -- the same reason ``evaluate`` has none.
        _fail(str(exc), 2 if isinstance(exc, ValueError) else 1)


def _diverging_answer(
    name: str, source: str, stdin: str, bound: float, facts: dict[str, object]
) -> str:
    """Return the answer bit for a language that answers by terminating."""
    encoding = cast("tuple[str, str]", facts["answer_encoding"])
    try:
        run(name, source, stdin, bound)
    except ExecutionTimeoutError:
        return str(encoding.index("diverges"))
    return str(encoding.index("halts"))


def _evaluate(rest: list[str]) -> None:
    """Print the table a generated program actually computes."""
    _run_round_trip(rest, "evaluate")


def _verify(rest: list[str]) -> None:
    """Report whether a generated program computes the table asked for."""
    _run_round_trip(rest, "verify")


def _run_round_trip(rest: list[str], command: str) -> None:
    """Shared body of ``verify`` and ``evaluate``.

    One function because they differ only in what they print: the work --
    generate, walk every row, encode, run, read the answer -- is the same,
    and is the thing a CLI-only user had to write a shell loop for.
    """
    rest, options = _pop_options(rest, {"--timeout"})
    timeout = _timeout_of(options)
    rest = _split_positional(rest, set(), {"--timeout"})
    _check_count(command, rest, 2)
    language, table = rest[0], rest[1]
    try:
        computed = evaluate(language, table, timeout)
    except GeneratorCapError as exc:
        # Nothing ran, so this is the usage class: the generator refused the
        # table rather than building a program that got the wrong answer.
        _fail(str(exc))
    except EsolangError as exc:
        # No ``TemplateError`` clause: this command never hands an unfilled
        # template on, because ``evaluate`` reads ``parameterized`` and
        # fills the slots itself.
        _fail(str(exc), 2 if isinstance(exc, ValueError) else 1)
    if command == "evaluate":
        print(computed)
        return
    if computed == table:
        print("ok")
        return
    # The computed table beside the wanted one, because which rows disagree
    # is the whole content of a failure here.
    differing = [
        i for i, (a, b) in enumerate(zip(computed, table, strict=True)) if a != b
    ]
    _fail(
        f"computed {computed}, wanted {table}\n"
        f"{len(differing)} row(s) disagree: {', '.join(map(str, differing))}",
        1,
    )


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
    rest, options = _pop_options(rest, {"--timeout", "--table"})
    # The value is checked here, before the positionals are counted.  It ran
    # after, so `run --timeout brainfuck prog.txt` -- a forgotten number --
    # swallowed the language as the timeout's value and then reported
    # "missing <program-file>", sending the reader to look at the one
    # argument that was not the problem.
    timeout = _timeout_of(options)
    rest = _split_positional(rest, {"--judge"}, {"--timeout", "--judge", "--table"})
    judge = "--judge" in rest
    # Refused like every value-taking option is.  `--judge --judge` was
    # accepted in silence while `--timeout 5 --timeout 9` was refused, and
    # the inconsistency is the finding rather than either policy.
    if rest.count("--judge") > 1:
        _fail("--judge given more than once")
    rest = [arg for arg in rest if arg != "--judge"]
    _check_count("run", rest, 2)
    language, path = rest[0], rest[1]
    program = _read_program(path, timeout)
    # Resolved *before* stdin is read.  It was after, so
    # `esolangs run NotALang prog.txt` with stdin held open blocked forever
    # without ever saying the language was unknown -- the one thing it could
    # have answered without reading a byte.
    try:
        facts = describe(language)
        mode = facts["answer_mode"]
        name = facts["name"]
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    stdin = _read_stdin(timeout, _stdin_hint(facts))
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
    table = options.get("--table")
    warning = _shape_warning(facts, stdin, table)
    if warning and judge:
        # ``--judge`` is the caller saying "this is a truth-table program and
        # I want its answer bit", so a stdin the language cannot read the way
        # they meant is a usage error rather than advice: the whole output of
        # this command would be one wrong digit.  Plain ``run`` only warns,
        # because it executes arbitrary programs of the language and the
        # shape this calls wrong may be exactly what one of them wants.
        #
        # That split is the answer to "warn or refuse?" -- the flag says
        # which of the two situations you are in.
        _fail(f"{warning}\n(refused because --judge asks for an answer bit)")
    if judge and table is None and facts["input_shape"] in _UNCOUNTABLE_SHAPES:
        # Last, after the specific diagnoses above.  Put first, this swallowed
        # them: `abc` fed to Fargo was answered with "pass --table" instead of
        # "reads one decimal row index", which is the more useful of the two
        # by a wide margin.  So this only speaks when nothing else has -- when
        # the stdin is a perfectly good single line and the only thing that
        # cannot be checked is how many bits it should hold.
        #
        # A refusal rather than advice, and only for these two shapes.  The
        # first draft printed a note on every `--judge` call without a table,
        # including the ones where nothing was wrong, and a warning that fires
        # on correct input is worth less than no warning at all.  The other
        # sixty-seven read a line per bit, so `run` counts what the program
        # took against what it was given and catches a mismatch after the
        # fact; these two read a single line and never run off an end to
        # count.
        reads = (
            "one line of bits"
            if facts["input_shape"] == "one_line"
            else "one row index"
        )
        _fail(
            f"{name} reads {reads}, so the bit count cannot be checked from "
            f"stdin alone -- pass --table <truth-table> with --judge, or use: "
            f"esolangs answer {name} <truth-table> <bits>"
        )
    # No copy of the warning here.  ``run`` emits the same judgement as a
    # ``UserWarning`` now, so printing it as well said everything twice --
    # and Python's default format would have put this file's path and a line
    # of its source in front of it, which is nobody's idea of a CLI message.
    try:
        with (
            _UnboundedNotice("run") if timeout is None else _null_context(),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            output = run(language, program, stdin, timeout)
        surplus = next(
            (str(e.message) for e in caught if "lines supplied" in str(e.message)),
            None,
        )
        if judge and surplus is not None:
            # A surplus read under ``--judge`` is the arity mismatch the
            # flag exists to catch: the answer bit would be for a different
            # row.  Refused *instead of* being rendered as advice, so it is
            # said once rather than twice.
            _fail(f"{surplus}\n(refused because --judge asks for an answer bit)")
        for entry in caught:
            _note(str(entry.message))
        # The count and range checks `--table` buys.  ``run`` warns through
        # the library, which is not given the table and so can only judge
        # shape and alphabet -- so `run --table` computed this and used it
        # for nothing, while `check-stdin --table` and `run --judge --table`
        # both refused the same stdin.  Three routes, two answers.
        #
        # Only when the library did not already say it: a shape complaint
        # comes back from both, and saying it twice is what the note-vs-
        # warning split was cleaned up to stop.
        said = {str(entry.message) for entry in caught}
        if (
            warning
            and warning not in said
            and not any(warning.startswith(one.rstrip(".")) for one in said)
        ):
            _note(warning)
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
    if not program.strip():
        # Legal, and almost never what was meant: an empty file is what you
        # get from a redirect that failed or a generate that was never run.
        # Said on stderr, so a pipeline still receives the empty output.
        _note(f"note: {path} is empty, so there was no program to run")
    if not output and sys.stdout.isatty():
        sys.stderr.write(
            f"{language}: the program ran and printed nothing"
            f"{' (the file is empty)' if not program.strip() else ''}\n"
        )


def main() -> None:
    """Dispatch the ``esolangs`` subcommands, and handle an interrupt.

    ``KeyboardInterrupt`` is caught here because this tool *invites* it:
    on a language that answers by not terminating it prints "will run until
    you stop it", and then dumped a traceback when the reader did. 130 is
    the shell convention for a command killed by SIGINT.

    ``BrokenPipeError`` likewise: ``esolangs generate ... | head`` is an
    ordinary thing to type, and closing the pipe before the first write
    left ``Exception ignored while flushing sys.stdout`` on the terminal
    and exit 120.
    """
    try:
        _dispatch()
        # Flushed here, where the failure is catchable.  Python flushes
        # stdout again during interpreter shutdown, and a pipe closed
        # before the first write made *that* print "Exception ignored
        # while flushing sys.stdout" after the command had otherwise
        # finished.
        sys.stdout.flush()
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        sys.exit(130)
    except BrokenPipeError:  # pragma: no cover - needs a closed pipe
        # Python flushes stdout at exit and would report the same error
        # again from the interpreter's own teardown; pointing it at
        # ``devnull`` is the documented way to stop that.
        import os

        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(120)


def _dispatch() -> None:
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
        # Languages and options both suggest a near miss; the subcommands
        # they are typed after did not, so `esolangs lst` got the whole
        # usage block and no hint that `list` was one letter away.
        _fail(f"unknown command: {cmd}{_did_you_mean(cmd, set(HELP))}\n\n{USAGE}")
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
        "check-stdin": _check_stdin,
        "answer": _answer,
        "verify": _verify,
        "evaluate": _evaluate,
        "debug": _debug,
    }[cmd](rest)


if __name__ == "__main__":
    main()
