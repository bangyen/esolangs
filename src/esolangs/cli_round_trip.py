"""``esolangs answer``, ``evaluate`` and ``verify``: generate, run every row, judge."""

from __future__ import annotations

from esolangs import (
    Raster,
    describe,
    encode_inputs,
    evaluate,
    generate,
    instantiate,
    read_answer,
    run,
)
from esolangs.cli_args import (
    _check_count,
    _fail,
    _pop_options,
    _pop_width,
    _split_positional,
    _timeout_of,
)
from esolangs.cli_hints import _diverging_answer, _exit_code, _looks_like_a_table
from esolangs.exceptions import EsolangError, GeneratorCapError


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
        source: str | Raster
        if facts["parameterized"]:
            if isinstance(program, Raster):  # pragma: no cover - inconsistent metadata
                raise TypeError("a raster generator cannot be parameterized")
            source, stdin = instantiate(name, program, row, truth_table=table), ""
        else:
            source, stdin = program, encode_inputs(name, row, table)
        if facts["answer_mode"] == "termination":
            if not isinstance(source, str):  # pragma: no cover - inconsistent metadata
                raise TypeError("a raster language cannot answer by termination")
            # A bound is the answer here rather than a safeguard, so one is
            # supplied: this command exists to be a one-liner, and making a
            # reader discover that the termination-answer languages need a
            # flag would defeat that.
            print(_diverging_answer(name, source, stdin, timeout or 5.0, facts))
            return
        print(read_answer(name, run(name, source, stdin, timeout)))
    except EsolangError as exc:
        # No ``TemplateError`` clause: this command generates the template
        # and fills it in the same breath, so it never hands an unfilled one
        # on -- the same reason ``evaluate`` has none.
        _fail(str(exc), _exit_code(exc))


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
    before = list(rest)
    rest, width, bare = _pop_width(rest)
    rest = _split_positional(rest, set(), {"--timeout", "--width"})
    # The same trap ``generate`` carries: ``--width`` takes an *optional* N,
    # so a truth table typed straight after it is eaten as the width and the
    # complaint lands on a missing table.
    eaten = ""
    if width is not None and not bare:
        for i, arg in enumerate(before[:-1]):
            value = before[i + 1]
            if arg == "--width" and _looks_like_a_table(value):
                eaten = (
                    f"\n\nnote: --width consumed {value!r}, which looks like a "
                    f"truth table; put the table after the language"
                )
    _check_count(command, rest, 2, bare_width=bare, eaten=eaten)
    language, table = rest[0], rest[1]
    try:
        computed = evaluate(language, table, timeout, width)
    except GeneratorCapError as exc:
        # Nothing ran, so this is the usage class: the generator refused the
        # table rather than building a program that got the wrong answer.
        _fail(str(exc))
    except EsolangError as exc:
        # No ``TemplateError`` clause: this command never hands an unfilled
        # template on, because ``evaluate`` reads ``parameterized`` and
        # fills the slots itself.
        _fail(str(exc), _exit_code(exc))
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
