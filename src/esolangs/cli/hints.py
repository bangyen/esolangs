"""What the CLI says when something is wrong, and how it judges an answer."""

from __future__ import annotations

import shlex
import sys
from collections.abc import Callable, Iterable
from contextlib import suppress
from difflib import get_close_matches

from esolangs import LanguageInfo
from esolangs.exceptions import (
    EsolangError,
    ExecutionBudgetError,
    TemplateError,
    UnknownLanguageError,
)
from esolangs.operations.boolean_io import _encode_inputs
from esolangs.registry import (
    SUGGESTION_CUTOFF,
    Catalog,
    LanguageDeclaration,
    get_catalog,
)
from esolangs.registry._contracts import CHAR_STREAMS
from esolangs.runtime.source_hints import (
    can_render_argument,
    display_label,
    error_text,
    is_option,
    shell_argument,
    syntax_repair,
)

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


def _cli_error_text(
    exc: BaseException, *, language: str | None = None, catalog: Catalog | None = None
) -> str:
    """Render notes using CLI flags, preserving the original diagnostic."""
    message = str(exc)
    render: Callable[[str], str] | None = None
    if language is not None and catalog is not None:
        name = catalog.resolve(language)
        argument = shell_argument(name)
        if argument is not None and not can_render_argument(
            name, _display_encoding(sys.stderr)
        ):
            original = f"hint: {syntax_repair(argument)}"
            replacement = f"hint: {syntax_repair(_as_argument(name, catalog=catalog))}"

            def render(note: str) -> str:
                return replacement if note == original else note

    notes = error_text(exc, render_hint=render)[len(message) :]
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
    exc: EsolangError,
    language: str,
    table: str,
    options_for: Callable[[LanguageDeclaration], list[str] | str],
    *,
    catalog: Catalog,
) -> str:
    """Keep generator notes and point template input advice at the CLI."""
    message = str(exc)
    notes = _notes(exc)
    operand = _as_argument(language, catalog=catalog)
    if operand is not None:
        for target in ("the generated program", "the raster"):
            notes = notes.replace(
                f"run {target} with stdin=encode_inputs(language, bits)",
                f"pipe input from esolangs encode-inputs {operand} <bits> "
                f"when running {target}",
            )
    if isinstance(exc, UnknownLanguageError):
        message += _swapped_hint(language, table, options_for, catalog=catalog)
    return message + notes


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
    if operand is None:
        return message + notes
    return (
        f"{head}fill them with: esolangs generate --bits <bits> "
        f"{operand} <table>{notes}"
    )


def _saved_template_hint(language: str, path: str, catalog: Catalog) -> str:
    """Suggest filling the existing artifact with a shell-ready filename."""
    encoding = _display_encoding(sys.stderr)
    operand = _as_argument(language, catalog=catalog, encoding=encoding)
    if operand is None or not can_render_argument(path, encoding):
        return (
            "fill the saved template with esolangs generate --from-template and --bits"
        )
    return (
        "fill the saved template, for example: "
        f"esolangs generate --from-template={shlex.quote(path)} "
        f"--bits BITS --artifact {operand}"
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
    if operand is None:
        return message
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


def _swapped_hint(
    language: str,
    table: str,
    options_for: Callable[[LanguageDeclaration], list[str] | str],
    *,
    catalog: Catalog,
) -> str:
    """Return a hint when the language and truth-table arguments look swapped.

    A power-of-two run of 0s and 1s in the language slot is a swap.
    """
    if not _looks_like_a_table(language):
        return ""
    guidance = f"; {language!r} looks like a truth table -- the language comes first"
    try:
        declaration = catalog.languages[catalog.resolve(table)]
    except UnknownLanguageError as exc:
        return f"{guidance}. {exc}"
    options = options_for(declaration)
    if isinstance(options, str):
        return f"{guidance}. {options}"
    flags = "".join(f"{shlex.quote(option)} " for option in options)
    encoding = _display_encoding(sys.stderr)
    operand = _as_argument(
        table, catalog=catalog, encoding=encoding, force_separator=table.startswith("-")
    )
    if operand is None:
        return guidance
    return f"{guidance}: esolangs generate {flags}{operand} {language}"


def _did_you_mean(word: str, known: Iterable[str]) -> str:
    """Return a ``did you mean`` clause for ``word``, or an empty string.

    Same cutoff as :func:`esolangs.registry.resolve`.
    """
    close = get_close_matches(word, sorted(known), n=2, cutoff=SUGGESTION_CUTOFF)
    if not close:
        return ""
    return f"; did you mean {' or '.join(close)}?"


def _input_sentence(facts: LanguageInfo, *, catalog: Catalog) -> str:
    """Describe this language's stdin with a sample from its own encoder."""
    shape = facts.input_shape
    example = _encode_inputs(
        catalog.languages[facts.name], display_label(facts.name), [1, 0]
    )
    # Keep the newline that represents a final empty line or normalizes CRLF.
    if shape not in CHAR_STREAMS and not example.endswith(("\n\n", "\r\n")):
        example = example.removesuffix("\n")
    literal = repr(example)
    if literal.startswith("'"):
        quoted = literal[1:-1].replace('"', r"\"")
        literal = f'"{quoted}"'
    if shape == "row_index":
        return f"one decimal row index, e.g. {literal} for the bits 10"
    if shape == "row_number":
        return f"one decimal row index plus one, e.g. {literal} for the bits 10"
    if shape in CHAR_STREAMS:
        return f"adjacent bit characters, e.g. {literal}"
    return f"one line per bit, e.g. {literal}"


def _display_encoding(stream: object) -> str:
    """Use ASCII for copyable text when a stream declares no codec."""
    encoding: str | None = getattr(stream, "encoding", None)
    return encoding or "ascii"


def _as_argument(
    language: str,
    *,
    catalog: Catalog,
    encoding: str | None = None,
    force_separator: bool = False,
) -> str | None:
    """Quote a renderable language operand, protecting option-shaped names."""
    codec = encoding or _display_encoding(sys.stderr)
    if is_option(language) or not can_render_argument(language, codec):
        with suppress(UnknownLanguageError):
            declaration = catalog.languages[catalog.resolve(language)]
            language = next(
                (
                    spelling
                    for spelling in (
                        declaration.id,
                        *declaration.aliases,
                        declaration.name,
                    )
                    if can_render_argument(spelling, codec)
                ),
                language,
            )
    return shell_argument(language, encoding=codec, force_separator=force_separator)
