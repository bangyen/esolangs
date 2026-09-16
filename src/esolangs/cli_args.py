"""Argument parsing for the CLI, and the one way it refuses.

Every subcommand takes its positionals and options through here, so the exit
code for a usage error (2), the option-name suggestion and the arity message
are written once rather than per command.
"""

from __future__ import annotations

import sys

from esolangs._validate import check_timeout
from esolangs.cli_help import (
    HELP,
)
from esolangs.cli_hints import (
    _did_you_mean,
)
from esolangs.exceptions import EsolangError
from esolangs.tools.wrap import DEFAULT_WIDTH

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
    "check-stdin": ("<language>",),
    "answer": ("<language>", "<truth-table>", "<bits>"),
    "verify": ("<language>", "<truth-table>"),
    "evaluate": ("<language>", "<truth-table>"),
}


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


def _seed_of(options: dict[str, str]) -> int | None:
    """Read ``--seed``, refusing anything that is not a whole number.

    Checked here rather than left to :func:`esolangs.run`, so a mistyped
    seed is a usage error naming the flag rather than a ``ValueError`` from
    somewhere further in.
    """
    if "--seed" not in options:
        return None
    try:
        return int(options["--seed"])
    except ValueError:
        _fail(f"--seed must be a whole number, got {options['--seed']!r}")
        raise  # pragma: no cover - unreachable; _fail exits
