"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                         list the supported languages
    esolangs describe <language>          print its input shape and where
                                          the answer lands
    esolangs encode <language> <bits>     print the stdin those bits need
    esolangs generate <language> <table>  print a program computing a table
                                          (``--width N`` wraps it to N columns)
    esolangs run <language> <file>        run a program through its interpreter
    esolangs read-answer <language>       print the answer bit in a program's
                                          output, read from stdin
    esolangs debug <language> <file>      run under the breakpoint/watch VM

Every subcommand takes ``--help``.  For anything else, invoke the module
directly with ``python -m``.

``describe`` and ``read-answer`` are here because the two facts that decided
every wrong answer this tool ever handed out -- how a language wants its
input bits, and where in the output its answer sits -- were readable from
Python and from nowhere else.  A shell user could run all ten of the
languages that do not simply print their answer, and could not judge one of
them: A Painter Ant's answer is a mark on one cell of its grid.

Exit codes separate the failures a caller handles differently: **2** is a
usage error (an unknown command, option, or language -- nothing ran), **1**
is the program's own failure (it read past its input, halted on an invalid
operation, was a template), and **124** is a run stopped by ``--timeout``,
after timeout(1) -- from every command that takes one, not only ``run`` and
``debug``.  That last one used to be 1 as well, which left the three
languages whose answer *is* a timeout indistinguishable from a crash.
Only
an unexpected error still reaches the terminal as a traceback, which is what
a traceback should mean.
"""

from __future__ import annotations

import json
import sys
from typing import cast

from esolangs import (
    LanguageInfo,
    Raster,
    __version__,
    describe,
    dump_program,
    encode_inputs,
    generate,
    instantiate,
    list_languages,
    read_answer,
)
from esolangs.cli_args import (
    _check_count,
    _expand_short_options,
    _fail,
    _pop_flags,
    _pop_options,
    _pop_portable,
    _pop_set_pairs,
    _pop_width,
    _scale_of,
    _settings_of,
    _split_positional,
)
from esolangs.cli_debug import _debug
from esolangs.cli_help import (
    HELP,
    USAGE,
)
from esolangs.cli_hints import (
    _as_argument,
    _cli_error_text,
    _did_you_mean,
    _generate_hint,
    _input_sentence,
    _looks_like_a_table,
    _shell_hint,
)
from esolangs.cli_io import (
    _read_stdin,
)
from esolangs.cli_run import _run
from esolangs.cli_suggest import _suggest
from esolangs.exceptions import (
    EsolangError,
)
from esolangs.registry import LANGUAGES, resolve
from esolangs.tools.balance import BALANCERS


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
        _fail(_shell_hint(_cli_error_text(exc), language))


def _list(rest: list[str]) -> None:
    """Print the supported languages, optionally with capability markers."""
    rest, flags = _pop_flags(rest, {"--details", "--json"})
    rest = _split_positional(rest, set(), {"--details", "--json"})
    details = "--details" in flags
    as_json = "--json" in flags
    _check_count("list", rest, 0)
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
                        "generator_max_inputs": facts["generator_max_inputs"],
                        "generator_restrictions": facts["generator_restrictions"],
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
    print(
        f"{'language'.ljust(width)}  gen=generator tmpl=template ex=example "
        f"int=interpreter-only"
    )
    for name in list_languages():
        facts = describe(name)
        marks = " ".join(
            filter(
                None,
                (
                    "gen" if facts["boolean_generator"] else "int",
                    "tmpl" if facts["parameterized"] else "",
                    "ex" if facts["examples"] else "",
                ),
            )
        )
        limit = facts["generator_max_inputs"]
        restriction = facts["generator_restrictions"]
        suffix = f" max-inputs={limit}" if limit is not None else ""
        if restriction:
            suffix += f" ({restriction})"
        print(f"{name.ljust(width)}  {marks}{suffix}")


def _generate(rest: list[str]) -> None:
    """Print a program computing a truth table."""
    rest, set_pairs = _pop_set_pairs(rest)
    rest, options = _pop_options(rest, {"--bits", "--scale", "--settings"})
    rest, portable = _pop_portable(rest)
    rest, flags = _pop_flags(rest, {"--balance"})
    balance = "--balance" in flags
    scale = _scale_of(options)
    before = list(rest)
    rest, width, bare = _pop_width(rest)
    if balance and width is not None:
        _fail("--balance and --width are mutually exclusive")
    rest = _split_positional(
        rest,
        set(),
        {
            "--bits",
            "--width",
            "--balance",
            "--scale",
            "--settings",
            "--set",
            "--portable",
        },
    )
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
    settings = _settings_of(options, set_pairs, language=rest[0])
    try:
        # Widthed at both ends, and that is not a mistake.  ``generate``
        # wraps the template (or hands the width to a *layout* language,
        # which lays it out), and ``instantiate`` wraps a program
        # filled from an unwrapped template; a wrapped one fills in place.
        program = generate(
            rest[0],
            rest[1],
            width=width,
            balance=balance,
            scale=scale or 1,
            settings=settings,
        )
        if "--bits" in options:
            bits = options["--bits"]
            if set(bits) - {"0", "1"} or not bits:
                _fail(f"--bits must be a string of 0s and 1s, got {bits!r}")
            if isinstance(program, Raster):
                _fail("raster programs read bits from stdin and cannot be instantiated")
            program = cast(str, program)
            program = instantiate(
                rest[0], program, [int(b) for b in bits], width=width, settings=settings
            )
        if portable:
            program = dump_program(rest[0], program)
    except EsolangError as exc:
        _fail(_generate_hint(exc, rest[0], rest[1]))
    if (
        (width is not None or bare or balance)
        and describe(rest[0])["width_effect"] == "none"
        and not (balance and LANGUAGES[resolve(rest[0])].id in BALANCERS)
    ):
        sys.stderr.write(
            f"note: {'--balance' if balance else '--width'} has no effect on "
            f"{describe(rest[0])['name']} -- "
            f"the generator retains its original layout\n"
        )
    if isinstance(program, Raster):
        sys.stdout.buffer.write(program.to_png())
    else:
        print(program)


def _answer_sentence(facts: LanguageInfo) -> str:
    """State where the answer bit lives, in the terms a shell user needs."""
    zero, one = facts["answer_encoding"]
    mode = facts["answer_mode"]
    if mode == "termination":
        text = f"termination ({zero} for 0, {one} for 1)"
    elif mode == "dump":
        text = f"final-state dump ({zero} for 0, {one} for 1)"
    else:
        text = f"printed output ({zero} for 0, {one} for 1)"
    if facts["answer_convention"]:
        text += f"; {facts['answer_convention']}"
    return text


def _generator_sentence(facts: LanguageInfo) -> str:
    """State what generation offers before the reader reaches the fields."""
    if not facts["boolean_generator"]:
        return "none (interpreter only)"
    parts = ["yes"]
    if facts["parameterized"]:
        parts.append("template; fill inputs with generate --bits")
    elif facts["reads_input"]:
        parts.append("reads input bits from stdin")
    if facts["generator_max_inputs"] is not None:
        parts.append(f"max {facts['generator_max_inputs']} inputs")
    if facts["generator_restrictions"]:
        parts.append(str(facts["generator_restrictions"]))
    return "; ".join(parts)


def _settings_sentence(facts: LanguageInfo) -> str:
    """Spell dialect choices as names and defaults, not a Python dict."""
    settings = facts["dialect_settings"]
    if not settings:
        return "none"
    rendered = []
    for key, option in settings.items():
        text = f"{key}={option['default']}"
        if option["choices"]:
            text += f" (choices: {', '.join(str(c) for c in option['choices'])})"
        rendered.append(text)
    return "; ".join(rendered)


def _describe(rest: list[str]) -> None:
    """Print a language's input shape, answer location and capabilities."""
    rest, flags = _pop_flags(rest, {"--json", "--spec"})
    rest = _split_positional(rest, set(), {"--json", "--spec"})
    as_json = "--json" in flags
    as_spec = "--spec" in flags
    _check_count("describe", rest, 1)
    try:
        facts = describe(rest[0])
    except EsolangError as exc:
        _fail(exc)
        raise  # pragma: no cover - unreachable; _fail exits
    if as_spec:
        print(json.dumps(facts, indent=2) if as_json else facts["spec"])
        return
    if as_json:
        # Verbatim, including the keys the reading layout hides: a caller
        # asking for JSON is not reading it, and a field that vanishes when
        # it is empty is the thing that makes a schema unusable.
        print(json.dumps(facts, indent=2))
        return
    # The contract first: how bits go in, where the answer comes out, and
    # whether a generator exists.  The field list below keeps the facts
    # that decide how to drive a program; ``--json`` keeps every key.
    hidden = set()
    if not facts["reads_input"] and facts["parameterized"]:
        hidden = {"input_shape", "input_encoding"}
    name = str(facts["name"])
    print(name)
    if hidden:
        print(
            "input: none -- this generator embeds the bits in the program: "
            f"esolangs generate --bits <bits> {_as_argument(name)} <table>"
        )
    else:
        print(f"input: {_input_sentence(facts)}")
    print(f"answer: {_answer_sentence(facts)}")
    print(f"generator: {_generator_sentence(facts)}")
    print(f"settings: {_settings_sentence(facts)}")
    print(f"spec: esolangs describe --spec {_as_argument(name)}")
    print()
    print("details:")
    details = [
        ("source_kind", facts["source_kind"]),
        ("state_model", facts["state_model"]),
        ("boolean_generator", facts["boolean_generator"]),
        ("parameterized", facts["parameterized"]),
        ("reads_input", facts["reads_input"]),
        ("width_effect", facts["width_effect"]),
        ("generator_max_inputs", facts["generator_max_inputs"]),
        ("generator_restrictions", facts["generator_restrictions"]),
        ("input_shape", facts["input_shape"]),
        ("input_encoding", facts["input_encoding"]),
        ("answer_mode", facts["answer_mode"]),
        ("answer_encoding", facts["answer_encoding"]),
        ("answer_pattern", facts["answer_pattern"]),
        ("answer_convention", facts["answer_convention"]),
        ("self_halts", facts["self_halts"]),
        ("dumps_on_the_post_halt_step", facts["dumps_on_the_post_halt_step"]),
        ("steppable_to_answer", facts["steppable_to_answer"]),
        ("eof_is_a_value", facts["eof_is_a_value"]),
        ("examples", f"{len(facts['examples'])} committed (paths in --json)"),
        ("wiki_url", facts["wiki_url"]),
    ]
    width = max(len(key) for key, _value in details)
    for key, value in details:
        if value is None or value == "" or key in hidden:
            continue
        shown = " ".join(str(v) for v in value) if isinstance(value, tuple) else value
        print(f"  {key.ljust(width)}  {shown}")


def _read_answer(rest: list[str]) -> None:
    """Read a program's output on stdin and print the answer bit in it."""
    rest = _split_positional(rest, set())
    _check_count("read-answer", rest, 1)
    language = rest[0]
    try:
        facts = describe(language)
    except EsolangError as exc:
        _fail(exc)
        raise  # pragma: no cover - unreachable; _fail exits
    if facts["answer_mode"] == "termination":
        polarity = facts["answer_encoding"]
        zero, one = polarity
        _fail(
            f"{facts['name']} answers by {zero} for a 0 and {one} for a 1, so "
            f"there is no output to read; use: esolangs run "
            f"--timeout <seconds> {facts['name']} <program-file> and observe "
            f"whether it halts"
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
        _fail(exc)


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
    option_argv = argv[: argv.index("--")] if "--" in argv else argv
    # Accepted after a subcommand too.  The top-level help advertises it
    # without saying where it goes, and `esolangs list --version` answering
    # "unknown option" is a strange way to learn that.
    if {"--version", "-V"} & set(option_argv):
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
    if {"--help", "-h"} & set(option_argv[1:]):
        sys.stdout.write(HELP[cmd])
        sys.exit(0)

    rest = _expand_short_options(rest)
    {
        "list": _list,
        "describe": _describe,
        "encode": _encode,
        "generate": _generate,
        "run": _run,
        "suggest": _suggest,
        "read-answer": _read_answer,
        "debug": _debug,
    }[cmd](rest)


if __name__ == "__main__":
    main()
