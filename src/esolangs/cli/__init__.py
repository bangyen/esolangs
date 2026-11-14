"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                         list the supported languages
    esolangs describe <language>          print its input shape and where
                                          the answer lands
    esolangs encode-inputs <language> <bits>
                                          print the stdin those bits need
    esolangs generate <language> <table>  print a program computing a table
                                          (``--width N`` wraps it to N columns)
    esolangs run <language> <file>        run a program through its interpreter
    esolangs read-answer <language>       print the answer bit in a program's
                                          output, read from stdin

Every subcommand takes ``--help``.  For anything else, invoke the module
directly with ``python -m``.

``describe`` and ``read-answer`` expose the two facts behind every wrong
answer this tool handed out -- how a language wants its input bits, and where
its answer sits in the output (for some, a mark on one cell of a grid) --
which were otherwise readable only from Python.

Exit codes: **2** is a usage error (unknown command, option, or language;
nothing ran), **1** is the program's own failure (read past its input, halted
on an invalid operation, printed no readable answer), and **124** is a run stopped by
``--execution-timeout``, after timeout(1), from every command that takes one, or by
``--max-steps``, ``--max-output`` or ``--max-memory``.  124 is
distinct from 1 so the three languages whose answer *is* a timeout are not
confused with a crash.  Only an unexpected error reaches the terminal as a
traceback.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import asdict
from itertools import pairwise
from typing import cast, get_args

from esolangs import (
    LanguageInfo,
    Raster,
    __version__,
    encode_inputs,
    list_languages,
    read_answer,
)
from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.cli.args import (
    _check_count,
    _errors,
    _expand_short_options,
    _fail,
    _pop_flags,
    _pop_options,
    _pop_set_pairs,
    _pop_width,
    _scale_of,
    _settings_of,
    _split_positional,
)
from esolangs.cli.help import COMMANDS, USAGE, help_text
from esolangs.cli.hints import (
    _as_argument,
    _cli_error_text,
    _did_you_mean,
    _generate_hint,
    _input_sentence,
    _looks_like_a_table,
    _shell_hint,
)
from esolangs.cli.io import _read_stdin
from esolangs.cli.run import _run
from esolangs.compressed import CompressedText
from esolangs.exceptions import EsolangError, ProgramError
from esolangs.raster import png
from esolangs.registry import LANGUAGES, Language, resolve
from esolangs.registry._contracts import AnswerMode, InputShape, SourceForm
from esolangs.registry._describe import _spec
from esolangs.runtime._program import Program


def describe(language: str) -> LanguageInfo:
    """Load full catalog descriptions for commands that display them."""
    from esolangs import describe as describe_language

    return describe_language(language)


def _encode(rest: list[str]) -> None:
    """Print the stdin that feeds a language its input bits."""
    rest = _split_positional(rest, set())
    _check_count("encode-inputs", rest, 2)
    language, bits = rest[0], rest[1]
    if set(bits) - {"0", "1"} or not bits:
        _fail(f"bits must be a string of 0s and 1s, got {bits!r}")
    try:
        sys.stdout.write(encode_inputs(language, [int(bit) for bit in bits]))
    except EsolangError as exc:
        _fail(_shell_hint(_cli_error_text(exc), language))


#: ``list``'s filters; every other fact is in ``list --json --details``.
_FLAG_FILTERS: dict[str, Callable[[Language], bool]] = {
    "--generator": lambda lang: lang.has_backend,
    "--interpreter-only": lambda lang: not lang.has_backend,
}


_CATALOG_FILTERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "--source-kind": ("source_kind", get_args(SourceForm.__value__)),
    "--answer-mode": ("answer_mode", get_args(AnswerMode.__value__)),
    "--input-shape": ("input_shape", (*get_args(InputShape.__value__), "template")),
}


def _input_shape(facts: LanguageInfo) -> str | None:
    """Return the shape ``--input-shape`` filters on: ``template`` included."""
    return "template" if facts.parameterized else facts.input_shape


def _catalog_matches(name: str, options: dict[str, str], inputs: int | None) -> bool:
    """Match declared interfaces and arity caps."""
    declaration = LANGUAGES[name]
    if "--source-kind" in options and options["--source-kind"] != (
        declaration.runtime.source_kind.value
    ):
        return False
    if "--answer-mode" in options and options["--answer-mode"] != (
        declaration.contract.answer_mode
    ):
        return False
    if "--input-shape" not in options and inputs is None:
        return True
    facts = describe(name)
    if "--input-shape" in options and _input_shape(facts) != options["--input-shape"]:
        return False
    if inputs is not None:
        cap = facts.generator_max_inputs
        if not facts.boolean_generator or (cap is not None and cap < inputs):
            return False
    return True


def _catalog_names(options: dict[str, str], flags: list[str]) -> list[str]:
    """Return candidates by declared capabilities, without generating a table."""
    if "--generator" in flags and "--interpreter-only" in flags:
        _fail("--generator and --interpreter-only cannot be combined")
    for option, (_, choices) in _CATALOG_FILTERS.items():
        if option in options and options[option] not in choices:
            _fail(f"{option} must be one of {', '.join(choices)}")
    inputs = None
    if "--inputs" in options:
        try:
            inputs = int(options["--inputs"])
        except ValueError:
            _fail("--inputs must be a non-negative integer")
        if inputs < 0:
            _fail("--inputs must be a non-negative integer")
    pattern = None
    if "--grep" in options:
        try:
            pattern = re.compile(options["--grep"], re.IGNORECASE)
        except re.error as exc:
            _fail(f"--grep is not a valid regular expression: {exc}")
    wanted = [_FLAG_FILTERS[flag] for flag in flags if flag in _FLAG_FILTERS]
    return [
        name
        for name in list_languages()
        if all(test(LANGUAGES[name]) for test in wanted)
        and (pattern is None or pattern.search(_spec(name)))
        and (not options or _catalog_matches(name, options, inputs))
    ]


def _list(rest: list[str]) -> None:
    """Print languages matching the requested capabilities."""
    value_options = {"--grep", "--inputs", *_CATALOG_FILTERS}
    flag_options = {"--details", "--json", *_FLAG_FILTERS}
    rest, options = _pop_options(rest, value_options)
    rest, flags = _pop_flags(rest, flag_options)
    rest = _split_positional(rest, set(), value_options | flag_options)
    details = "--details" in flags
    as_json = "--json" in flags
    _check_count("list", rest, 0)
    names = _catalog_names(options, flags)
    if as_json:
        if not details:
            print(json.dumps(names, indent=2))
            return
        print(
            json.dumps(
                [
                    {
                        "name": name,
                        "generator_scaling": facts.generator_scaling,
                        "source_kind": facts.source_kind,
                        "state_model": facts.state_model,
                        "generator_shape": facts.generator_shape,
                        "answer_mode": facts.answer_mode,
                        # The filter's value, so jq agrees with --input-shape.
                        "input_shape": _input_shape(facts),
                        "random": facts.random,
                        "width_effect": facts.width_effect,
                        # The three the marker column encodes, spelled out.
                        "boolean_generator": facts.boolean_generator,
                        "parameterized": facts.parameterized,
                        "generator_max_inputs": facts.generator_max_inputs,
                        "generator_restrictions": facts.generator_restrictions,
                        "examples": facts.examples,
                    }
                    for name, facts in zip(names, map(describe, names), strict=True)
                ],
                indent=2,
            )
        )
        return
    if not details:
        for name in names:
            print(name)
        return
    width = max(len(name) for name in LANGUAGES)
    # The legend lived in `list --help` only, so the marker columns arrived
    # unexplained for anyone who ran the thing before reading about it.
    print(
        f"{'language'.ljust(width)}  gen=generator tmpl=template ex=example "
        f"int=interpreter-only; then any generator cap"
    )
    for name in names:
        facts = describe(name)
        marks = " ".join(
            filter(
                None,
                (
                    "gen" if facts.boolean_generator else "int",
                    "tmpl" if facts.parameterized else "",
                    "ex" if facts.examples else "",
                ),
            )
        )
        limit = facts.generator_max_inputs
        restriction = facts.generator_restrictions
        suffix = f" max-inputs={limit}" if limit is not None else ""
        if restriction:
            suffix += f" ({restriction})"
        print(f"{name.ljust(width)}  {marks}{suffix}")


def _eaten_width_note(before: list[str]) -> str:
    """Note a truth table that a bare ``--width`` consumed as its value."""
    # `--width` takes an *optional* N, so a truth table typed straight after
    # it is consumed as the width and the report lands on the table being
    # missing -- which is baffling when you did type one.
    eaten = ""
    for arg, value in pairwise(before):
        if arg == "--width" and _looks_like_a_table(value):
            eaten = (
                f"\n\nnote: --width consumed {value!r}, which looks like a "
                f"truth table; put the table after the language"
            )
    return eaten


def _layout_ignored(language: str, *, balance: bool) -> bool:
    """Whether ``--width``/``--balance`` cannot change ``language``'s layout."""
    backend = LANGUAGES[resolve(language)].backend
    return describe(language).width_effect == "none" and not (
        balance and backend is not None and backend.balance is not None
    )


def _emit(artifact: Artifact, *, plain: bool, gzip: bool = False) -> None:
    """Write native source using the artifact's declared file convention."""
    program = artifact.source
    if gzip and isinstance(program, str):
        ending = "\n" if LANGUAGES[artifact.language].runtime.file_newline else ""
        program = CompressedText.from_chunks((program, ending))
    if isinstance(program, CompressedText):
        if plain:
            for chunk in program.plain_chunks():
                sys.stdout.write(chunk)
        else:
            sys.stdout.buffer.write(program.to_gzip())
    elif isinstance(program, Raster):
        assert isinstance(artifact, ProgramArtifact)
        sys.stdout.buffer.write(
            png.write_source(
                program.rows, artifact.language, artifact.settings, artifact.scale
            )
        )
    else:
        ending = "\n" if LANGUAGES[artifact.language].runtime.file_newline else ""
        sys.stdout.write(program + ending)


def _generate(rest: list[str]) -> None:
    """Print a program computing a truth table."""
    from esolangs import generate, instantiate

    value_options = {"--bits", "--scale", "--settings"}
    flag_options = {"--balance", "--plain", "--gzip"}
    rest, set_pairs = _pop_set_pairs(rest)
    rest, options = _pop_options(rest, value_options)
    rest, flags = _pop_flags(rest, flag_options)
    balance = "--balance" in flags
    gzip = "--gzip" in flags
    if gzip and "--plain" in flags:
        _fail("--gzip and --plain are mutually exclusive")
    scale = _scale_of(options)
    before = list(rest)
    rest, width, bare = _pop_width(rest)
    if balance and width is not None:
        _fail("--balance and --width are mutually exclusive")
    rest = _split_positional(
        rest,
        set(),
        value_options | flag_options | {"--width", "--set"},
    )
    eaten = _eaten_width_note(before) if width is not None and not bare else ""
    _check_count("generate", rest, 2, bare_width=bare, eaten=eaten)
    settings = _settings_of(options, set_pairs, language=rest[0])
    try:
        # Widthed at both ends, and that is not a mistake.  ``generate``
        # wraps the template (or hands the width to a *layout* language,
        # which lays it out), and ``instantiate`` wraps a program
        # filled from an unwrapped template; a wrapped one fills in place.
        artifact = generate(
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
            if isinstance(artifact.source, Raster):
                _fail("raster programs read bits from stdin and cannot be instantiated")
            artifact = instantiate(
                rest[0],
                artifact,
                [int(b) for b in bits],
                width=width,
                settings=settings,
            )
        program = artifact.source
        if gzip and isinstance(program, Raster):
            _fail("gzip export requires text; rasters use PNG")
        if isinstance(program, CompressedText) and "--plain" in flags:
            program.plain_chunks()  # Check the export budget before writing anything.
    except EsolangError as exc:
        _fail(_generate_hint(exc, rest[0], rest[1]))
    if (width is not None or bare or balance) and _layout_ignored(
        rest[0], balance=balance
    ):
        sys.stderr.write(
            f"note: {'--balance' if balance else '--width'} has no effect on "
            f"{describe(rest[0]).name} -- "
            f"the generator retains its original layout\n"
        )
    if "--plain" in flags and isinstance(program, Raster):
        sys.stderr.write("note: --plain has no effect on a raster; it is PNG\n")
    binary = (
        gzip
        or isinstance(program, Raster)
        or (isinstance(program, CompressedText) and "--plain" not in flags)
    )
    if binary and sys.stdout.isatty():
        # Unary's gzip once landed on a terminal unannounced.
        _fail(
            f"{describe(rest[0]).name} generates "
            f"{'a PNG' if isinstance(program, Raster) else 'gzip'}; "
            f"redirect stdout to a file"
            + ("" if isinstance(program, Raster) else " or pass --plain")
        )
    with _errors():  # A raster renders here, and may exceed the pixel limit.
        _emit(artifact, plain="--plain" in flags, gzip=gzip)
    if isinstance(artifact, TemplateArtifact):
        # `run` takes the unfilled template as source and answers nonsense
        # with exit 0, where the API refuses it (dogfood, 2.0.0).
        sys.stderr.write(
            f"note: this is a template with unfilled {artifact.bindings.char!r} "
            f"input slots; fill them with: esolangs generate "
            f"--bits <bits> {_as_argument(rest[0])} {rest[1]}\n"
        )


def _printable(value: object) -> str:
    """Return ``value`` as text that stays on one line.

    INTERCAL's zero answer ends in a newline; printed raw it split its line.
    """
    text = str(value)
    return text if text.isprintable() else repr(text)[1:-1]


def _answer_sentence(facts: LanguageInfo) -> str:
    """State where the answer bit lives, in the terms a shell user needs."""
    zero, one = map(_printable, facts.answer_encoding)
    mode = facts.answer_mode
    if mode == "termination":
        text = f"termination ({zero} for 0, {one} for 1)"
    elif mode == "dump":
        text = f"final-state dump ({zero} for 0, {one} for 1)"
    else:
        text = f"printed output ({zero} for 0, {one} for 1)"
    if facts.answer_convention:
        text += f"; {facts.answer_convention}"
    return text


def _generator_sentence(facts: LanguageInfo) -> str:
    """State what generation offers before the reader reaches the fields."""
    if not facts.boolean_generator:
        return "none (interpreter only)"
    parts = ["yes"]
    if facts.parameterized:
        parts.append("template; fill inputs with generate --bits")
    elif facts.reads_input:
        parts.append("reads input bits from stdin")
    if facts.generator_max_inputs is not None:
        parts.append(f"max {facts.generator_max_inputs} inputs")
    if facts.generator_restrictions:
        parts.append(str(facts.generator_restrictions))
    return "; ".join(parts)


def _settings_sentence(facts: LanguageInfo) -> str:
    """Spell dialect choices as names and defaults, not a Python dict."""
    settings = facts.dialect_settings
    if not settings:
        return "none"
    rendered = []
    for key, option in settings.items():
        text = f"{key}={option['default']}"
        if option["choices"]:
            text += f" (choices: {', '.join(str(c) for c in option['choices'])})"
        rendered.append(text)
    return "; ".join(rendered)


#: The facts ``describe`` lists under "details:", in order.
_DETAIL_KEYS = (
    "source_kind",
    "state_model",
    "boolean_generator",
    "parameterized",
    "reads_input",
    "width_effect",
    "generator_max_inputs",
    "generator_restrictions",
    "input_shape",
    "input_encoding",
    "answer_mode",
    "answer_encoding",
    "answer_pattern",
    "answer_convention",
    "self_halts",
    "dumps_on_the_post_halt_step",
    "steppable_to_answer",
    "eof_is_a_value",
    "random",
    "examples",
    "wiki_url",
)


def _describe(rest: list[str]) -> None:
    """Print a language's input shape, answer location and capabilities."""
    rest, flags = _pop_flags(rest, {"--json", "--spec"})
    rest = _split_positional(rest, set(), {"--json", "--spec"})
    as_json = "--json" in flags
    as_spec = "--spec" in flags
    _check_count("describe", rest, 1)
    if as_spec:
        with _errors():
            spec = _spec(rest[0])
        print(json.dumps(spec) if as_json else spec)
        return
    with _errors():
        facts = describe(rest[0])
    if as_json:
        # Verbatim, including the keys the reading layout hides: a caller
        # asking for JSON is not reading it, and a field that vanishes when
        # it is empty is the thing that makes a schema unusable.
        print(json.dumps(asdict(facts), indent=2))
        return
    # The contract first: how bits go in, where the answer comes out, and
    # whether a generator exists.  The field list below keeps the facts
    # that decide how to drive a program; ``--json`` keeps every key.
    name = str(facts.name)
    print(name)
    if facts.parameterized:
        print(
            "input: none -- this generator embeds the bits in the program: "
            f"esolangs generate --bits <bits> {_as_argument(name)} <table>"
        )
    elif not facts.reads_input:
        print("input: none -- this language reads no stdin")
    else:
        print(f"input: {_input_sentence(facts)}")
    print(f"answer: {_answer_sentence(facts)}")
    print(f"generator: {_generator_sentence(facts)}")
    print(f"settings: {_settings_sentence(facts)}")
    print(f"spec: esolangs describe --spec {_as_argument(name)}")
    print()
    print("details:")
    shown_facts: dict[str, object] = {
        **asdict(facts),
        "examples": f"{len(facts.examples)} committed (paths in --json)",
    }
    details = [(key, shown_facts[key]) for key in _DETAIL_KEYS]
    width = max(len(key) for key, _value in details)
    for key, value in details:
        if value is None or value == "":
            continue
        shown = (
            " ".join(map(_printable, value))
            if isinstance(value, tuple)
            else _printable(value)
        )
        print(f"  {key.ljust(width)}  {shown}")


def _read_answer(rest: list[str]) -> None:
    """Read a program's output on stdin and print the answer bit in it."""
    rest = _split_positional(rest, set())
    _check_count("read-answer", rest, 1)
    language = rest[0]
    with _errors():
        declaration = LANGUAGES[resolve(language)]
    contract = declaration.contract
    if contract.answer_mode == "termination":
        zero, one = contract.answer_values
        _fail(
            f"{declaration.name} answers 0 if it {zero} and 1 if it {one}, so "
            f"there is no output to read; use: esolangs run "
            f"--execution-timeout <seconds> {declaration.name} <program-file> "
            "and observe "
            f"whether it halts"
        )
    output = _read_stdin(hint="; pipe a program's output in, or close stdin")
    # NQ's false answer is a space; only absent output is empty stdin.
    if not output:
        _fail(
            f"nothing on stdin to read an answer out of; pipe a program's "
            f"output in: esolangs run {language} prog.txt | esolangs "
            f"read-answer {language}"
        )
    try:
        answer = read_answer(language, output)
    except ProgramError as exc:
        # Output with no readable answer is the program's failure, as in run.
        _fail(exc, 1)
    except EsolangError as exc:
        _fail(exc)
    print(answer)


def main() -> None:
    """Dispatch the ``esolangs`` subcommands, and handle an interrupt.

    ``KeyboardInterrupt`` is caught because a language that answers by not
    terminating prints "will run until you stop it", inviting the interrupt;
    exit 130 is the shell convention for SIGINT.

    ``BrokenPipeError`` likewise: ``esolangs generate ... | head`` closes the
    pipe before the first write, which otherwise left ``Exception ignored
    while flushing sys.stdout`` on the terminal and exit 120.

    Anything else is a bug in this package, not the program being run, and
    exits 70 with a one-line report instead of a traceback.
    """
    for stream in (sys.stdout, sys.stderr):
        # An ASCII locale (or PYTHONIOENCODING=ascii) cannot encode Forþ:
        # `list` died mid-line with exit 70.  Escape instead.
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            # A closed stream refuses; the write that follows reports it.
            with suppress(ValueError, OSError):
                reconfigure(errors="backslashreplace")
    if sys.stderr is None or getattr(sys.stderr, "closed", False):
        # Started with fd 2 closed (``2>&-``): every note and error wrote to
        # None, so even a successful `run` printed nothing and exited 1.
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115 - lives for the run
    if sys.stdout is None or getattr(sys.stdout, "closed", False):
        # A closed stream object, in process, is the same case: it exited 70.
        # Started with fd 1 closed (``esolangs list >&-``): ``print`` drops
        # silently and the flush below raised AttributeError, exit 70.  The
        # same outcome as a pipe closed early, so the same exit.
        sys.stderr.write("stdout is closed; nothing was written\n")
        sys.exit(120)
    try:
        try:
            _dispatch()
        except SystemExit:
            # An early exit flushes here too: `debug`'s exit 1 into a closed
            # pipe printed "Exception ignored while flushing sys.stdout".
            sys.stdout.flush()
            raise
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
        if rest and rest[0] not in COMMANDS:
            # `help nope` printed the usage and exited 0.
            _fail(f"unknown command: {rest[0]}{_did_you_mean(rest[0], set(COMMANDS))}")
        sys.stdout.write(help_text(rest[0]) if rest else USAGE)
        sys.exit(0)
    if cmd not in COMMANDS:
        # Languages and options both suggest a near miss; the subcommands
        # they are typed after did not, so `esolangs lst` got the whole
        # usage block and no hint that `list` was one letter away.
        _fail(f"unknown command: {cmd}{_did_you_mean(cmd, set(COMMANDS))}\n\n{USAGE}")
    if {"--help", "-h"} & set(option_argv[1:]):
        sys.stdout.write(help_text(cmd))
        sys.exit(0)

    rest = _expand_short_options(rest)
    {
        "list": _list,
        "describe": _describe,
        "encode-inputs": _encode,
        "generate": _generate,
        "run": _run,
        "read-answer": _read_answer,
    }[cmd](rest)
