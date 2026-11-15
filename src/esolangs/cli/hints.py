"""What the CLI says when something is wrong, and how it judges an answer."""

from __future__ import annotations

import shlex
import sys
from collections.abc import Iterable
from contextlib import suppress
from difflib import get_close_matches

from esolangs import LanguageInfo
from esolangs.exceptions import (
    EsolangError,
    ExecutionBudgetError,
    TemplateError,
    UnknownLanguageError,
)
from esolangs.registry import SUGGESTION_CUTOFF, Catalog, get_catalog
from esolangs.runtime.source_hints import error_text

#: A run stopped by its ``--execution-timeout``, following timeout(1).  Distinct from
#: a program error's 1, which it shared. A timeout leaves termination
#: undecided; it does not establish a Boolean answer.
_TIMEOUT_EXIT = 124


def _exit_code(exc: EsolangError) -> int:
    """Return the exit code ``exc`` should leave behind.

    ``run --help`` documents 124 for the timeout running out, and three of the
    five commands exited 1 on it.  ``ValueError`` is misuse, 2; else 1.
    An output or memory cap is the same verdict -- the caller's budget ran
    out, the answer is undecided -- and exited 1, "the program broke".
    """
    if isinstance(exc, ExecutionBudgetError):
        return _TIMEOUT_EXIT
    return 2 if isinstance(exc, ValueError) else 1


def _cli_error_text(exc: BaseException) -> str:
    """Render notes using CLI flags, preserving the original diagnostic."""
    message = str(exc)
    notes = error_text(exc)[len(message) :]
    for parameter, flag in (
        ("timeout=5.0", "--execution-timeout 5.0"),
        ("scale=1", "--scale 1"),
        ("omit scale", "omit --scale"),
        ("use scale 1", "use --scale 1"),
        ("width=80", "--width 80"),
        ("seed=0", "--seed 0"),
        ("omit seed", "omit --seed"),
        ("integer bits to instantiate()", "0/1 digits to --bits"),
    ):
        notes = notes.replace(parameter, flag)
    return message + notes


def _notes(exc: BaseException) -> str:
    """Return ``exc``'s notes rendered with CLI flags."""
    return _cli_error_text(exc)[len(str(exc)) :]


def _generate_hint(
    exc: EsolangError, language: str, table: str, *, catalog: Catalog
) -> str:
    """Keep generator notes and point template input advice at the CLI."""
    message = str(exc)
    notes = _notes(exc)
    operand = _as_argument(language, catalog=catalog)
    for target in ("the generated program", "the raster"):
        notes = notes.replace(
            f"run {target} with stdin=encode_inputs(language, bits)",
            f"pipe input from esolangs encode-inputs {operand} <bits> "
            f"when running {target}",
        )
    return message + _swapped_hint(language, table, catalog=catalog) + notes


def _template_hint(
    exc: TemplateError, language: str, *, catalog: Catalog | None = None
) -> str:
    """Re-point a template refusal at the CLI flag that fills the slots."""
    message = str(exc)
    notes = _notes(exc)
    pointer = "fill them with esolangs.instantiate("
    if pointer not in message:
        return message + notes
    head = message.split(pointer)[0]
    operand = _as_argument(language, catalog=get_catalog(catalog))
    return (
        f"{head}fill them with: esolangs generate --bits <bits> "
        f"{operand} <table>{notes}"
    )


#: The flag that raises each bound ``run`` can report.
_BOUND_FLAGS = {
    "execution_timeout": "--execution-timeout",
    "total_timeout": "--total-timeout",
    "preparation_timeout": "--preparation-timeout",
    "max_steps": "--max-steps",
    "max_output": "--max-output",
    "max_memory": "--max-memory",
}


def _timeout_text(exc: ExecutionBudgetError) -> str:
    """Name the flag to raise; the API's hint says only "the bound"."""
    bound = getattr(exc, "bound", None)
    if (
        not isinstance(bound, str)
        or (flag := _BOUND_FLAGS.get(str.__str__(bound))) is None
    ):
        return _cli_error_text(exc)
    return str(exc) + _notes(exc).replace("the bound", flag).replace(bound, flag)


def _shell_hint(message: str, language: str, *, catalog: Catalog) -> str:
    """Re-point ``encode-inputs``'s refusal at the flag that does the same job.

    ``instantiate()`` is not a thing you can type at a shell; ``generate
    --bits`` is.
    """
    operand = _as_argument(language, catalog=catalog)
    return message.replace(
        "pass the bits to instantiate() to embed them in source",
        f"embed them in source with: esolangs generate --bits <bits> {operand} <table>",
        1,
    )


def _looks_like_a_table(value: str) -> bool:
    """Whether ``value`` is a power-of-two run of 0s and 1s."""
    if not value or set(value) - {"0", "1"}:
        return False
    n = len(value).bit_length() - 1
    return len(value) == 2**n and n >= 1


def _swapped_hint(language: str, table: str, *, catalog: Catalog) -> str:
    """Return a hint when the language and truth-table arguments look swapped.

    A power-of-two run of 0s and 1s in the language slot is a swap.
    """
    if not _looks_like_a_table(language):
        return ""
    separator = "-- " if table.startswith("-") else ""
    return (
        f"; {language!r} looks like a truth table -- the language comes "
        "first: esolangs generate "
        f"{separator}{_as_argument(table, catalog=catalog)} {language}"
    )


def _did_you_mean(word: str, known: Iterable[str]) -> str:
    """Return a ``did you mean`` clause for ``word``, or an empty string.

    Same cutoff as :func:`esolangs.registry.resolve`.
    """
    close = get_close_matches(word, sorted(known), n=2, cutoff=SUGGESTION_CUTOFF)
    if not close:
        return ""
    return f"; did you mean {' or '.join(close)}?"


def _decode_note(exc: UnicodeDecodeError) -> str:
    """Describe where a decode failed, without the codec's full sentence."""
    return f"invalid UTF-8 at byte {exc.start}"


def _input_sentence(facts: LanguageInfo) -> str:
    """Describe this language's stdin in one line, with an example."""
    if facts.input_encoding is None:
        return "none"
    # Escaped: Unary's zero is NUL, written raw into the terminal.
    zero, one = (c if c.isprintable() else repr(c)[1:-1] for c in facts.input_encoding)
    shape = str(facts.input_shape)
    example = f"{one}{zero}"
    if shape == "row_index":
        return 'one decimal row index, e.g. "2" for the bits 10'
    if shape == "row_number":
        return 'one decimal row index plus one, e.g. "3" for the bits 10'
    if shape in {"char_stream", "char_stream_cyclic"}:
        return f'adjacent bit characters, e.g. "{example}"'
    lines = f"{one}\\n{zero}"
    return f'one line per bit, e.g. "{lines}"'


def _is_option(value: str) -> bool:
    """Tell whether a leading dash makes a standalone operand an option."""
    return len(value) > 1 and value[0] == "-" and not value[1].isdigit()


def _as_argument(
    language: str, *, catalog: Catalog, encoding: str | None = None
) -> str:
    """Quote a language, using its ID for an option-shaped or unencodable name."""
    codec = encoding or getattr(sys.stderr, "encoding", None) or "utf-8"
    try:
        language.encode(codec)
    except UnicodeEncodeError:
        needs_id = True
    else:
        needs_id = _is_option(language)
    if needs_id:
        with suppress(UnknownLanguageError):
            language = catalog.languages[catalog.resolve(language)].id
    return shlex.quote(language)
