"""What the CLI says when something is wrong, and how it judges an answer."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from difflib import get_close_matches

from esolangs import LanguageInfo
from esolangs.exceptions import EsolangError, ExecutionTimeoutError, TemplateError
from esolangs.interpreters.source_hints import error_text
from esolangs.registry import SUGGESTION_CUTOFF

# A watched cell's history longer than this is printed abridged: the whole
# thing was one line of 486 comma-separated values for a 486-step program,
# which buries the ends that are actually read.
_HISTORY_SHOWN = 40


#: A run stopped by its ``--timeout``, following timeout(1).  Distinct from
#: a program error's 1, which it shared: for the languages that answer by
#: not terminating, the timeout is the *answer*, and a script had no way
#: to tell that from the program having broken.
_TIMEOUT_EXIT = 124


def _exit_code(exc: EsolangError) -> int:
    """Return the exit code ``exc`` should leave behind.

    ``run --help`` documents 124 for a bound running out, and three of the
    five commands exited 1 on it.  ``ValueError`` is misuse, 2; else 1.
    """
    if isinstance(exc, ExecutionTimeoutError):
        return _TIMEOUT_EXIT
    return 2 if isinstance(exc, ValueError) else 1


def _cli_error_text(exc: BaseException) -> str:
    """Render notes using CLI flags, preserving the original diagnostic."""
    message = str(exc)
    notes = error_text(exc)[len(message) :]
    for parameter, flag in (
        ("timeout=5.0", "--timeout 5.0"),
        ("scale=1", "--scale 1"),
        ("omit scale", "omit --scale"),
        ("width=80", "--width 80"),
        ("seed=0", "--seed 0"),
        ("integer bits to instantiate()", "0/1 digits to --bits"),
    ):
        notes = notes.replace(parameter, flag)
    return message + notes


def _generate_hint(exc: EsolangError, language: str, table: str) -> str:
    """Keep generator notes and point template input advice at the CLI."""
    message = str(exc)
    notes = _cli_error_text(exc)[len(message) :]
    notes = notes.replace(
        "run the generated program with stdin=encode_inputs(language, bits)",
        f"pipe input from esolangs encode {_as_argument(language)} <bits> "
        "when running the generated program",
    )
    return message + _swapped_hint(language, table) + notes


def _template_hint(exc: TemplateError, language: str) -> str:
    """Re-point a template refusal at the CLI flag that fills the slots."""
    message = str(exc)
    notes = _cli_error_text(exc)[len(message) :]
    pointer = "fill them with esolangs.instantiate("
    if pointer not in message:
        return message + notes
    head = message.split(pointer)[0]
    return (
        f"{head}fill them with: esolangs generate --bits <bits> "
        f"{_as_argument(language)} <table>{notes}"
    )


def _shell_hint(message: str, language: str) -> str:
    """Re-point ``encode``'s refusal at the flag that does the same job.

    ``instantiate()`` is not a thing you can type at a shell; ``generate
    --bits`` is.
    """
    pointer = "pass the bits to instantiate() instead"
    if pointer not in message:
        return message
    head = message.split(pointer)[0]
    return (
        f"{head}embed them in the program instead: "
        f"esolangs generate --bits <bits> {_as_argument(language)} <table>"
    )


def _looks_like_a_table(value: str) -> bool:
    """Whether ``value`` is a power-of-two run of 0s and 1s."""
    if not value or set(value) - {"0", "1"}:
        return False
    n = len(value).bit_length() - 1
    return len(value) == 2**n and n >= 1


def _swapped_hint(language: str, table: str) -> str:
    """Return a hint when the language and truth-table arguments look swapped.

    A power-of-two run of 0s and 1s in the language slot is a swap.
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

    Same cutoff as :func:`esolangs.registry.resolve`.
    """
    close = get_close_matches(word, sorted(known), n=2, cutoff=SUGGESTION_CUTOFF)
    if not close:
        return ""
    return f"; did you mean {' or '.join(close)}?"


def _abridge(history: Sequence[object]) -> str:
    """Render a watch history, eliding the middle of a long one."""
    if len(history) <= _HISTORY_SHOWN:
        return str(history)
    head = ", ".join(str(v) for v in history[: _HISTORY_SHOWN // 2])
    tail = ", ".join(str(v) for v in history[-_HISTORY_SHOWN // 2 :])
    return f"[{head}, ... {len(history) - _HISTORY_SHOWN} more ..., {tail}]"


def _decode_note(exc: UnicodeDecodeError) -> str:
    """Describe where a decode failed, without the codec's full sentence."""
    return f"invalid UTF-8 at byte {exc.start}"


def _stdin_hint(facts: LanguageInfo) -> str:
    """Return a clause naming what this language wants on stdin, if anything.

    Suggests rather than skips: some embed-only languages
    have an input command a hand-written program may use.
    """
    if not facts["reads_input"] and facts["parameterized"]:
        return (
            f"; {facts['name']}'s generated programs embed their inputs and "
            f"read no stdin, so there is probably nothing to send -- close it"
        )
    return "; try: esolangs encode <language> <bits> | ..."

    # No note about ``--table`` here.  The first draft printed one whenever
    # it was absent, which is every call that is simply checking a shape --
    # advice on correct input, which is the thing this CLI has spent several
    # rounds removing.  The private stdin check says what the flag adds.


def _input_sentence(facts: LanguageInfo) -> str:
    """Describe this language's stdin in one line, with an example."""
    zero, one = facts["input_encoding"]
    shape = str(facts["input_shape"])
    example = f"{one}{zero}"
    if shape == "row_index":
        return 'one decimal row index, e.g. "2" for the bits 10'
    if shape in {"char_stream", "char_stream_cyclic"}:
        return f'adjacent bit characters, e.g. "{example}"'
    if shape == "char_stream_padded":
        return (
            f'adjacent bit characters, e.g. "{example}" -- and an odd count '
            f"above one is padded with a leading {zero} character"
        )
    lines = f"{one}\\n{zero}"
    return f'one line per bit, e.g. "{lines}"'


def _as_argument(language: str) -> str:
    """Return ``language`` spelled the way a shell needs it.

    Some names contain a space (a count is pinned by
    ``TestPrintedCommandsCanBePasted``), and ``esolangs describe --spec A
    Painter Ant`` gave ``unexpected argument: 'Painter'``.
    """
    return f'"{language}"' if " " in language else language
