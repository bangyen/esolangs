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
after timeout(1) -- from every command that takes one, not only ``run`` and
``debug``.  That last one used to be 1 as well, which left the three
languages whose answer *is* a timeout indistinguishable from a crash, and
then stayed 1 in ``evaluate``, ``verify`` and ``answer`` after the other
two were fixed, which left a script unable to use one code for the event.  Only
an unexpected error still reaches the terminal as a traceback, which is what
a traceback should mean.
"""

from __future__ import annotations

import json
import sys

from esolangs import (
    __version__,
    check_stdin,
    describe,
    encode_inputs,
    generate,
    instantiate,
    list_languages,
    read_answer,
)
from esolangs import spec as _spec
from esolangs.cli_args import (
    _check_count,
    _fail,
    _pop_options,
    _pop_width,
    _split_positional,
)
from esolangs.cli_debug import _debug
from esolangs.cli_help import (
    HELP,
    USAGE,
)
from esolangs.cli_hints import (
    _as_argument,
    _did_you_mean,
    _input_sentence,
    _looks_like_a_table,
    _shell_hint,
    _swapped_hint,
)
from esolangs.cli_hints import (
    _shape_warning as _shape_warning,
)
from esolangs.cli_hints import (
    _template_hint as _template_hint,
)

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
from esolangs.cli_io import (
    _UNBOUNDED_NOTICE_AFTER as _UNBOUNDED_NOTICE_AFTER,
)
from esolangs.cli_io import (
    _bounded_read as _bounded_read,
)
from esolangs.cli_io import (
    _emit_partial as _emit_partial,
)
from esolangs.cli_io import (
    _read_program as _read_program,
)
from esolangs.cli_io import (
    _read_stdin,
)
from esolangs.cli_io import (
    _smuggled_bytes as _smuggled_bytes,
)
from esolangs.cli_io import (
    _UnboundedNotice as _UnboundedNotice,
)
from esolangs.cli_io import (
    _WaitingNotice as _WaitingNotice,
)
from esolangs.cli_io import (
    _write_output as _write_output,
)
from esolangs.cli_round_trip import _answer, _evaluate, _verify
from esolangs.cli_run import _run
from esolangs.exceptions import (
    EsolangError,
)
from esolangs.registry import LANGUAGES


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
    print(f"{'language'.ljust(width)}  gen=generator tmpl=template ex=example")
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
        # Widthed at both ends, and that is not a mistake.  ``generate``
        # wraps the template (or hands the width to a *layout* language
        # like COD, which lays it out), and ``instantiate`` wraps a program
        # filled from an unwrapped template; a wrapped one fills in place.
        program = generate(rest[0], rest[1], width)
        if "--bits" in options:
            bits = options["--bits"]
            if set(bits) - {"0", "1"} or not bits:
                _fail(f"--bits must be a string of 0s and 1s, got {bits!r}")
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
    rest = _split_positional(rest, {"--json", "--spec"})
    as_json = "--json" in rest
    as_spec = "--spec" in rest
    rest = [a for a in rest if a not in {"--json", "--spec"}]
    _check_count("describe", rest, 1)
    try:
        facts = describe(rest[0])
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    if as_spec:
        # Printed rather than folded into the record, because it is prose
        # of a few thousand characters and would swamp every other field.
        text = _spec(str(facts["name"]))
        print(json.dumps({**facts, "spec": text}, indent=2) if as_json else text)
        return
    if as_json:
        # Verbatim, including the keys the reading layout hides: a caller
        # asking for JSON is not reading it, and a field that vanishes when
        # it is empty is the thing that makes a schema unusable.
        print(json.dumps(facts, indent=2))
        return
    # A template language reads no stdin, so its shape and alphabet are
    # noise.  Hidden here, not dropped from ``describe()``, whose keys stay
    # uniform across all 60.
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
            f"{_as_argument(str(facts['name']))} <table>"
        )
    else:
        # The symmetric row.  A reader had ``input_encoding`` and
        # ``input_shape`` and had to compose them, while the template
        # languages got a sentence -- so the languages where getting it
        # wrong is possible were the ones told least plainly.
        print(f"{'input'.ljust(width)}  {_input_sentence(facts)}")
    # Every field above is about driving a *generated* program.  Someone
    # writing their own needs the language's command table, which this
    # package ships as the interpreter's module docstring and used to name
    # only as ``interpreter: stack_based.unsquare`` -- an import path, with
    # no hint that importing it is the point.
    print(
        f"{'spec'.ljust(width)}  esolangs describe --spec "
        f"{_as_argument(str(facts['name']))}"
    )


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
        polarity = facts["answer_encoding"]
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

    Anything else is a bug in this package rather than in the program
    being run, and exits 70 with a one-line report instead of a
    traceback.
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
    except Exception as exc:
        # Anything reaching here is a package bug (three interpreters once
        # raised ``OverflowError`` through ``main``): one line and an exit
        # code nothing else uses, not a traceback.
        sys.stderr.write(
            f"internal error: {type(exc).__name__}: {exc}\n"
            f"This is a bug in esolangs, not in your program; please report "
            f"it with the command you ran.\n"
        )
        sys.exit(70)


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
