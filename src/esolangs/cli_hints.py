"""What the CLI says when something is wrong, and how it judges an answer."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from difflib import get_close_matches

from esolangs import LanguageInfo, check_stdin
from esolangs._evaluate import _terminates
from esolangs.exceptions import EsolangError, ExecutionTimeoutError, TemplateError
from esolangs.registry import SUGGESTION_CUTOFF

# A watched cell's history longer than this is printed abridged: the whole
# thing was one line of 486 comma-separated values for a 486-step program,
# which buries the ends that are actually read.
_HISTORY_SHOWN = 40


#: A run stopped by its ``--timeout``, following timeout(1).  Distinct from
#: a program error's 1, which it shared: for the three languages that answer
#: by not terminating, the timeout is the *answer*, and a script had no way
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


#: The two input shapes whose bit count cannot be recovered from stdin.
#: Every other language reads a line per bit, so a run can compare what it
#: took against what it was given; these two read a single line -- all the
#: bits at once, or a row index -- and a wrong count is indistinguishable
#: from a right one without knowing the arity.
_UNCOUNTABLE_SHAPES = ("one_line", "row_index")


def _template_hint(exc: TemplateError, language: str) -> str:
    """Re-point a template refusal at the CLI flag that fills the slots."""
    message = str(exc)
    pointer = "fill them with esolangs.instantiate("
    if pointer not in message:
        return message
    head = message.split(pointer)[0]
    return (
        f"{head}fill them with: esolangs generate --bits <bits> "
        f"{_as_argument(language)} <table>"
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


def _shape_warning(facts: LanguageInfo, stdin: str, table: str | None = None) -> str:
    """Return the library's complaint about ``stdin``, or ``''``.

    The checks live in :func:`esolangs.check_stdin`; two copies drifted
    twice before.
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


def _decode_note(exc: UnicodeDecodeError) -> str:
    """Describe where a decode failed, without the codec's full sentence."""
    return f"invalid UTF-8 at byte {exc.start}"


def _stdin_hint(facts: LanguageInfo) -> str:
    """Return a clause naming what this language wants on stdin, if anything.

    Suggests rather than skips: three of the seventeen embed-only languages
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
    # rounds removing.  ``check-stdin --help`` says what the flag adds.


def _input_sentence(facts: LanguageInfo) -> str:
    """Describe this language's stdin in one line, with an example."""
    zero, one = facts["input_encoding"]
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


def _diverging_answer(
    name: str, source: str, stdin: str, bound: float, facts: LanguageInfo
) -> str:
    """Return the answer bit for a language that answers by terminating.

    By repeated-state proof, not by waiting: ``answer --timeout 20`` on a
    1-row used to take twenty seconds where ``verify`` settles four rows
    in a fifth of a second.  The clock stays as the backstop for unbounded
    growth.
    """
    encoding = facts["answer_encoding"]
    return _terminates(
        name,
        source,
        stdin,
        bound,
        str(encoding.index("halts")),
        str(encoding.index("diverges")),
    )


def _as_argument(language: str) -> str:
    """Return ``language`` spelled the way a shell needs it.

    Nine of the 59 names contain a space; ``esolangs describe --spec A
    Painter Ant`` gave ``unexpected argument: 'Painter'``.
    """
    return f'"{language}"' if " " in language else language
