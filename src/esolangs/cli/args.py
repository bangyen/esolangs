"""Argument parsing for the CLI, and the one way it refuses.

Every subcommand takes its positionals and options through here, so the exit
code for a usage error (2), the option-name suggestion and the arity message
are written once rather than per command.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from typing import NoReturn

from esolangs.cli.help import HELP
from esolangs.cli.hints import _cli_error_text, _did_you_mean
from esolangs.exceptions import EsolangError
from esolangs.generation.wrap import DEFAULT_WIDTH
from esolangs.registry import resolve
from esolangs.runtime._validate import check_scale, check_timeout
from esolangs.settings import DialectSettings, dialect_choices

#: Flags every subcommand accepts, so a near miss on one of them is
#: suggested by whichever subcommand it was typed after.
_GLOBAL_FLAGS = {"--help", "--version"}


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


def _fail(message: str | BaseException, code: int = 2) -> NoReturn:
    if isinstance(message, BaseException):
        message = _cli_error_text(message)
    sys.stderr.write(message + "\n")
    sys.exit(code)


#: Long options that consume the next token, across every subcommand.  The
#: short-option expansion skips the token after one of these: it is a value,
#: even when it happens to spell ``-p``.
_VALUE_OPTIONS = {
    "--source",
    "--answer",
    "--inputs",
    "--bits",
    "--scale",
    "--settings",
    "--set",
    "--timeout",
    "--max-output",
    "--max-memory",
    "--seed",
    "--steps",
    "--watch-cell",
    "--break-at",
    "--break-on-cell",
    "--break-on-output",
    "--stdin",
}

_SHORT_OPTIONS = {"-p": "--portable", "-s": "--settings"}


def _expand_short_options(rest: list[str]) -> list[str]:
    """Expand the short options before the positional separator."""
    expanded: list[str] = []
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--":
            expanded.extend(rest[i:])
            break
        if expanded and expanded[-1] in _VALUE_OPTIONS:
            expanded.append(arg)
            i += 1
            continue
        name, sep, inline = arg.partition("=")
        if name in _SHORT_OPTIONS:
            expanded.append(_SHORT_OPTIONS[name] + (sep + inline if sep else ""))
        else:
            expanded.append(arg)
        i += 1
    return expanded


def _scan_values(
    rest: list[str], names: Collection[str]
) -> Iterator[tuple[str | None, str]]:
    """Yield ``(name, value)`` per ``--name V`` or ``--name=V``, else ``(None, arg)``.

    Only ``names`` before ``--`` are options; everything else is yielded as is.
    """
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--":
            yield from ((None, tail) for tail in rest[i:])
            return
        name, sep, inline = arg.partition("=")
        if name not in names:
            yield None, arg
            i += 1
        elif sep:
            yield name, inline
            i += 1
        elif i + 1 < len(rest):
            yield name, rest[i + 1]
            i += 2
        else:
            _fail(f"{name} needs a value")


def _pop_set_pairs(rest: list[str]) -> tuple[list[str], list[str]]:
    """Remove repeatable ``--set KEY=VALUE`` options before ``--``."""
    args: list[str] = []
    pairs: list[str] = []
    for name, value in _scan_values(rest, {"--set"}):
        (args if name is None else pairs).append(value)
    return args, pairs


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
    vocabulary: Collection[str] = frozenset(),
) -> list[str]:
    """Return ``rest``'s positionals, refusing any unrecognized option.

    ``vocabulary`` is only for the did-you-mean: value-taking options are
    already consumed, so ``known`` lacks them and a misspelling (``--wdith``)
    would have nothing to match.  The caller names its full option set.

    An unknown ``--option`` is refused rather than kept as a positional:
    ``debug --frobnicate brainfuck p.txt`` once reported ``cannot read
    brainfuck``, blaming the language for a typo.  A program file named
    ``--x`` stays reachable after a bare ``--``, after which everything is
    positional.
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

    Extra arguments are named, not dropped, since silence turned a wrong
    command into a confident wrong answer.  ``generate --width abc brainfuck
    0110`` consumes no width and reads ``abc`` as the language, so the message
    says why the count came out that way (``bare_width``).
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

    Returns the remaining arguments, the width (``None`` when absent, leaving
    the program on one line), and whether a bare ``--width`` was taken.  A
    bare ``--width`` uses :data:`DEFAULT_WIDTH`; an explicit value must be an
    integer, since reading the language name as a width would generate the
    wrong thing.
    """
    args: list[str] = []
    width: int | None = None
    bare = False
    seen: dict[str, str] = {}
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--":
            args.extend(rest[i:])
            break
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
        width = _integer(value, "--width")
        if width <= 0:
            _fail(f"--width must be positive, got {width}")
    return args, width, bare


def _pop_flags(rest: list[str], names: set[str]) -> tuple[list[str], list[str]]:
    """Remove bare flags before the positional separator."""
    boundary = rest.index("--") if "--" in rest else len(rest)
    flags = [arg for arg in rest[:boundary] if arg in names]
    args = [arg for arg in rest[:boundary] if arg not in names]
    return args + rest[boundary:], flags


def _pop_portable(rest: list[str]) -> tuple[list[str], bool]:
    """Remove one portable-format flag before the positional separator."""
    rest, flags = _pop_flags(rest, {"--portable"})
    if len(flags) > 1:
        _fail("--portable given more than once")
    return rest, bool(flags)


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
    for name, value in _scan_values(rest, names):
        if name is None:
            args.append(value)
        else:
            _refuse_repeat(found, name)
            found[name] = value
    return args, found


def _timeout_of(options: dict[str, str], *, option: str = "--timeout") -> float | None:
    """Return the ``--timeout`` seconds, or None, refusing a bad value.

    The *value* checks are the private stdin check's neighbour
    :func:`esolangs.runtime._validate.check_timeout`, not a second copy: this had
    its own rules for zero, negatives and non-finite values, and the
    library then grew a floor and a ceiling that this did not know about.
    A ``--timeout 1e10`` therefore got past here and overflowed the C
    timer three calls later, as a raw ``OverflowError``.
    """
    if option not in options:
        return None
    try:
        seconds = float(options[option])
    except ValueError:
        _fail(f"{option} must be a number, got {options[option]!r}")
    try:
        check_timeout(seconds)
    except EsolangError as exc:
        # Re-worded from ``timeout`` to ``--timeout``: the library names the
        # parameter, and this names the flag the reader typed.
        _fail(
            _cli_error_text(exc)
            .replace("timeout must", f"{option} must", 1)
            .replace("--timeout 5.0", f"{option} 5.0")
        )
    return seconds


def _pop_cell(options: dict[str, str]) -> tuple[int, int] | None:
    """Read ``--break-on-cell I=V`` into a pair, or ``None`` if absent.

    A cell breakpoint needs two numbers where every other option takes one,
    and ``I=V`` keeps that one token rather than making this the only option
    that consumes two arguments.
    """
    raw = options.get("--break-on-cell")
    if raw is None:
        return None
    index, sep, value = raw.partition("=")
    if not sep or not _is_int(index) or not _is_int(value):
        _fail(f"--break-on-cell wants INDEX=VALUE, got {raw!r}")
    return int(index), int(value)


@contextmanager
def _errors(code: int = 2) -> Iterator[None]:
    """Report library errors using the command's exit code."""
    try:
        yield
    except EsolangError as exc:
        _fail(exc, code)


def _integer(value: str, name: str, *, kind: str = "an integer") -> int:
    """Parse an integer with a flag-specific usage error."""
    try:
        return int(value)
    except ValueError:
        _fail(f"{name} must be {kind}, got {value!r}")


def _nonnegative(value: int, name: str, shown: object) -> None:
    """Reject negative bounds and cell indices."""
    if value < 0:
        _fail(f"{name} must not be negative, got {shown}")


def _seed_of(options: dict[str, str]) -> int | None:
    """Read ``--seed``, refusing anything that is not a whole number.

    Checked here rather than left to :func:`esolangs.run`, so a mistyped
    seed is a usage error naming the flag rather than a ``ValueError`` from
    somewhere further in.
    """
    if "--seed" not in options:
        return None
    return _integer(options["--seed"], "--seed", kind="a whole number")


def _scale_of(options: dict[str, str]) -> int | None:
    """Read a positive integer pixel scale."""
    if "--scale" not in options:
        return None
    try:
        return check_scale(
            _integer(options["--scale"], "--scale", kind="a positive integer")
        )
    except ValueError:
        _fail(f"--scale must be a positive integer, got {options['--scale']!r}")


def _set_value(key: str, raw: str) -> int | str | None:
    """Read one ``--set`` value; the two modulus settings are integers."""
    if raw == "null":
        return None
    if key in {"cell_modulus", "io_modulus"}:
        try:
            return int(raw, 0)
        except ValueError:
            _fail(f"--set {key} needs an integer, got {raw!r}")
    return raw


def _settings_of(
    options: dict[str, str],
    set_pairs: list[str] | tuple[str, ...] = (),
    *,
    language: str | None = None,
) -> DialectSettings | None:
    """Parse dialect overrides from JSON and/or ``--set KEY=VALUE`` pairs."""
    values: dict[str, object] = {}
    if "--settings" in options:
        try:
            parsed = json.loads(options["--settings"])
        except ValueError as exc:
            _fail(f"--settings is not valid JSON ({exc}); pass a JSON object")
        if not isinstance(parsed, dict):
            _fail("--settings must be a JSON object")
        values.update(parsed)
    for pair in set_pairs:
        key, sep, raw = pair.partition("=")
        if not sep or not key:
            _fail(f"--set needs KEY=VALUE, got {pair!r}")
        values[key] = _set_value(key, raw)
    if not values and "--settings" not in options and not set_pairs:
        return None
    try:
        return DialectSettings(**values)  # type: ignore[arg-type]
    except EsolangError as exc:
        message = str(exc)
        if language is not None and message.startswith("unknown dialect setting:"):
            try:
                choices = dialect_choices(language)
            except EsolangError:
                choices = None
            if choices is not None:
                accepted = ", ".join(choices) if choices else "no dialect settings"
                message += f"; {language} accepts: {accepted}"
        _fail(message)
