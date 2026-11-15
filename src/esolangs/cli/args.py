"""Argument parsing for the CLI, and the one way it refuses.

Every subcommand takes its positionals and options through here, so the exit
code for a usage error (2), the option-name suggestion and the arity message
are written once rather than per command.
"""

from __future__ import annotations

import os
import re
import select
import stat
import sys
from collections.abc import Collection, Iterator
from contextlib import contextmanager, suppress
from typing import NoReturn, TextIO

from esolangs._dialect import DialectSchema
from esolangs._language import Language
from esolangs.cli.help import command_synopsis
from esolangs.cli.hints import _as_argument, _cli_error_text, _did_you_mean, _is_option
from esolangs.exceptions import EsolangError
from esolangs.registry import Catalog, get_catalog
from esolangs.runtime._json import record_loads
from esolangs.runtime._validate import check_scale, check_timeout
from esolangs.runtime.memory import _hit_digit_cap, format_integer, parse_integer
from esolangs.settings import DialectSettings

#: Flags every subcommand accepts, so a near miss on one of them is
#: suggested by whichever subcommand it was typed after.
_GLOBAL_FLAGS = {"--help", "--version"}


#: Each command's positional arguments, in order, so a missing one can be
#: named rather than left to be inferred from the usage line.
_ARGUMENTS = {
    "encode-inputs": ("<language>", "<bits>"),
    "generate": ("<language>", "<truth-table>"),
    "run": ("<language>", "<program-file>"),
    "describe": ("<language>",),
    "read-answer": ("<language>",),
}


def _abandon_output(stream: TextIO) -> None:
    """Keep Python's shutdown flush from retrying the failed destination."""
    with suppress(OSError, ValueError), open(os.devnull, "wb") as sink:
        os.dup2(sink.fileno(), stream.fileno())


def _output_ready(stream: TextIO) -> bool:
    """Check whether an optional notice can write without waiting on a pipe."""
    try:
        fd = stream.fileno()
    except (OSError, ValueError):
        return True  # Caller-provided streams such as StringIO have no descriptor.
    try:
        if hasattr(select, "poll"):
            poller = select.poll()
            poller.register(fd, select.POLLOUT)
            return bool(poller.poll(0))
        # On platforms without poll, pipe readiness cannot be checked here.
        return not stat.S_ISFIFO(os.fstat(fd).st_mode)
    except (OSError, ValueError):
        return False


def _diagnostic(message: str, *, ready_only: bool = False) -> None:
    """Write to stderr without changing the command's outcome if it fails."""
    stream = sys.stderr
    if stream is None or (ready_only and not _output_ready(stream)):
        return
    try:
        try:
            stream.write(message)
        except UnicodeEncodeError:
            # A caller-supplied text adapter may lack reconfigure().
            stream.write(message.encode("ascii", "backslashreplace").decode("ascii"))
        stream.flush()
    except KeyboardInterrupt:
        _abandon_output(stream)
        raise
    except OSError:
        _abandon_output(stream)
    except ValueError:
        pass  # A closed adapter or one that rejected even the escaped message.


def _fail(message: str | BaseException, code: int = 2) -> NoReturn:
    if isinstance(message, BaseException):
        message = _cli_error_text(message)
    _diagnostic(message + "\n")
    sys.exit(code)


_SHORT_OPTIONS = {"-s": "--settings"}

#: Required-value options, excluding the optional value on ``--width``.
_VALUE_OPTIONS = {
    "generate": {"--bits", "--scale", "--settings", "--set"},
    "list": {"--grep", "--inputs", "--source-kind", "--input-shape", "--answer-mode"},
    "run": {
        "--execution-timeout",
        "--total-timeout",
        "--preparation-timeout",
        "--seed",
        "--scale",
        "--max-output",
        "--max-memory",
        "--max-steps",
        "--settings",
        "--set",
    },
}


def _normalize_options(command: str, rest: list[str]) -> list[str]:
    """Attach mandatory values so later passes cannot mistake them for flags."""
    names = _VALUE_OPTIONS.get(command, set())
    normalized: list[str] = []
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--":
            normalized.extend(rest[i:])
            break
        name, sep, inline = arg.partition("=")
        canonical = _SHORT_OPTIONS.get(name, name)
        if canonical in names:
            name = canonical
            if not sep and i + 1 < len(rest) and rest[i + 1] != "--":
                i += 1
                sep, inline = "=", rest[i]
        normalized.append(name + sep + inline)
        i += 1
    return normalized


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
        elif i + 1 < len(rest) and rest[i + 1] != "--":
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


def _integer_spelling(value: str) -> bool:
    """Recognize the optional decimal operand of ``--width``."""
    return re.fullmatch(r"[+-]?\d(?:_?\d)*", value.strip()) is not None


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
        if _is_option(arg) and arg.partition("=")[0] not in known:
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
    catalog: Catalog,
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
        synopsis = command_synopsis(command)
        # And say which one is missing.  The synopsis alone left the reader
        # to diff what they typed against a usage line -- easy for two
        # arguments, and it is exactly the two-argument commands that get
        # here.  ``_ARGUMENTS`` names them in order.
        missing = _ARGUMENTS.get(command, ())[len(args) : wanted]
        named = f"\n\nmissing {', '.join(missing)}" if missing else ""
        _fail(f"{synopsis}{named}{eaten}")
    if len(args) > wanted:
        if wanted:
            # The language comes first. Keep later operands out of its name.
            joined = " ".join(args[: len(args) - wanted + 1])
            try:
                resolved = catalog.resolve(joined)
            except EsolangError:
                pass
            else:
                operand = _as_argument(resolved, catalog=catalog)
                action = "pass it as" if operand.startswith("-- ") else "quote it as"
                _fail(f"language name was split across arguments; {action} {operand}")
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
            if following is None or not _integer_spelling(following):
                # A bare ``--width`` has no value to quote, so the option
                # itself is what a repeat report names.
                seen["--width"] = arg
                from esolangs.generation.wrap import DEFAULT_WIDTH

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
            _fail(f"--width must be positive, got {format_integer(width)}")
    return args, width, bare


def _pop_flags(rest: list[str], names: set[str]) -> tuple[list[str], set[str]]:
    """Remove bare flags before the separator, refusing repeats."""
    boundary = rest.index("--") if "--" in rest else len(rest)
    flags: set[str] = set()
    args: list[str] = []
    for arg in rest[:boundary]:
        if arg not in names:
            args.append(arg)
        elif arg in flags:
            _fail(f"{arg} given more than once")
        else:
            flags.add(arg)
    return args + rest[boundary:], flags


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


def _timeout_of(
    options: dict[str, str], *, option: str = "--execution-timeout"
) -> float | None:
    """Return a deadline flag's seconds, or None, refusing a bad value.

    The *value* checks are the private stdin check's neighbour
    :func:`esolangs.runtime._validate.check_timeout`, not a second copy: this had
    its own rules for zero, negatives and non-finite values, and the
    library then grew a ceiling that this did not know about.
    A ``--execution-timeout 1e10`` therefore got past here and overflowed a C
    wait later, as a raw ``OverflowError``.
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
        # Re-worded from ``timeout`` to the flag: the library names the
        # parameter, and this names the flag the reader typed.
        _fail(
            _cli_error_text(exc)
            .replace("timeout must", f"{option} must", 1)
            .replace("--execution-timeout 5.0", f"{option} 5.0")
        )
    return seconds


@contextmanager
def _errors() -> Iterator[None]:
    """Report library errors using the command's exit code."""
    try:
        yield
    except EsolangError as exc:
        _fail(exc)


def _decimal_integer(value: str) -> int:
    """Parse an int-compatible decimal operand without the host digit cap."""
    digits = value.strip()
    if digits and digits != value:
        # Validate padding with int's whitespace rules before stripping it.
        prefix, _, suffix = value.partition(digits)
        int(prefix + "0" + suffix)
    return parse_integer(digits)


def _integer(
    value: str,
    name: str,
    *,
    kind: str = "an integer",
) -> int:
    """Parse an integer with a flag-specific usage error."""
    try:
        return _decimal_integer(value)
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
    value = options.get("--seed")
    if value is None:
        return None
    return _integer(value, "--seed", kind="a whole number")


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


def _set_value(key: str, raw: str, schema: DialectSchema | None) -> int | str:
    """Read one ``--set`` value using its declared scalar type."""
    if (
        schema is not None
        and key in schema.choices
        and type(schema.choices[key][0]) is int
    ):
        try:
            return _base_zero_integer(raw)
        except ValueError:
            _fail(f"--set {key} needs an integer, got {raw!r}")
    return raw


def _base_zero_integer(raw: str) -> int:
    """Parse base-0 operands without capping their decimal digits."""
    try:
        return int(raw, 0)
    except ValueError as exc:
        if not _hit_digit_cap(exc):
            raise
        value = _decimal_integer(raw)
        # CPython's digit cap can fire before it rejects a nonzero decimal
        # starting with zero. Preserve that base-0 restriction on retry.
        if value and int(raw.strip().lstrip("+-")[0]) == 0:
            raise
        return value


type _SettingsArguments = tuple[dict[str, object], dict[str, str]]


def _settings_arguments(
    options: dict[str, str],
    set_pairs: list[str],
) -> _SettingsArguments | None:
    """Check settings operand syntax before counting positionals."""
    if "--settings" not in options and not set_pairs:
        return None
    values: dict[str, object] = {}
    if "--settings" in options:
        try:
            parsed = record_loads(options["--settings"])
        except (ValueError, RecursionError) as exc:
            _fail(f"--settings is not valid JSON ({exc}); pass a JSON object")
        if not isinstance(parsed, dict):
            _fail("--settings must be a JSON object")
        values.update(parsed)
    pairs: dict[str, str] = {}
    for pair in set_pairs:
        key, sep, raw = pair.partition("=")
        if not sep or not key:
            _fail(f"--set needs KEY=VALUE, got {pair!r}")
        pairs[key] = raw
    return values, pairs


def _settings_of(
    arguments: _SettingsArguments | None,
    *,
    language: str,
    catalog: Catalog | None = None,
) -> DialectSettings | None:
    """Validate choices against the selected language's schema."""
    if arguments is None:
        return None
    values, pairs = arguments
    try:
        catalog = get_catalog(catalog)
        bound = Language(language, catalog=catalog)
        schema = catalog.languages[bound.name].runtime.dialect_schema
        overrides = {key: _set_value(key, raw, schema) for key, raw in pairs.items()}
        choices = values | overrides
        return bound.settings(**choices)  # type: ignore[arg-type]
    except EsolangError as exc:
        _fail(exc)
