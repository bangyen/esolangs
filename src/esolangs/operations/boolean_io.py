"""Feeding a program and judging what it printed.

:func:`encode_inputs` builds the stdin for one row and
:func:`read_answer` turns output into a bit.  Every judgement applies the
registered Boolean I/O contract.
"""

import re

from esolangs.exceptions import (
    ArgumentError,
    ProgramError,
)
from esolangs.registry._catalog import Catalog
from esolangs.registry._contracts import CHAR_STREAMS, BooleanContract
from esolangs.results import ExecutionResult
from esolangs.runtime._validate import _has_backing_type, check_bits
from esolangs.runtime.memory import format_integer


def _symbol_pair(name: str, values: object, encoding: str) -> tuple[str, str]:
    """Validate a scoped contract's two distinct spellings for the bits."""
    if _has_backing_type(values, tuple) and tuple.__len__(values) == 2:
        zero, one = tuple.__iter__(values)
        if _has_backing_type(zero, str) and _has_backing_type(one, str):
            zero, one = str.__str__(zero), str.__str__(one)
            if zero != one:
                return zero, one
    raise ProgramError(
        f"{name} has an invalid {encoding}; expected two distinct strings"
    )


def _answer_codec(
    name: str, contract: BooleanContract
) -> tuple[tuple[str, str], re.Pattern[str] | None]:
    """Validate and prepare the answer side before executing a Boolean row."""
    if contract.answer_mode not in ("output", "dump", "termination"):
        raise ProgramError(f"{name} has an invalid answer mode")
    values = _symbol_pair(name, contract.answer_values, "answer encoding")
    if contract.answer_mode == "termination":
        if values not in (("halts", "diverges"), ("diverges", "halts")):
            raise ProgramError(
                f"{name} has an invalid termination answer encoding; "
                "expected 'halts' and 'diverges'"
            )
        return values, None
    source: object = contract.answer_pattern
    if _has_backing_type(source, re.Pattern) and _has_backing_type(source.pattern, str):
        return values, source
    if not _has_backing_type(source, str):
        raise ProgramError(f"{name} has an invalid answer pattern; expected text")
    source = str.__str__(source)
    if not source:
        if any(len(value) != 1 or value.isspace() for value in values):
            raise ProgramError(
                f"{name} has an invalid answer encoding. "
                "Use one non-whitespace character per answer or set answer_pattern."
            )
        return values, None
    try:
        return values, re.compile(source)
    except (re.error, OverflowError, RecursionError) as error:
        raise ProgramError(f"{name} has an invalid answer pattern: {error}") from error


def encode_inputs(
    language: str,
    bits: list[int] | tuple[int, ...],
    *,
    truth_table: str | None = None,
    catalog: "Catalog | None" = None,
) -> str:
    """Return the stdin encoding for ``bits`` under the Boolean input contract.

    Character readers take adjacent digits; numeric readers take tokens;
    each language spells its bits per its registered ``input_encoding`` and
    ``input_shape``, so the obvious guess is often a wrong bit.

    Args:
        bits: One integer 0 or 1 per input.
        truth_table: Optional check, as for :func:`instantiate`: ``bits``
            must match its input count.  The encoding never depends on it.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: The language reads no stdin (it embeds its inputs, so
            use :func:`instantiate`, or has no input instruction), a bit is
            not an integer 0 or 1, or ``bits`` does not match
            ``truth_table``'s input count.
        TruthTableError: ``truth_table`` is not a binary string of length
            ``2**n``.
        ProgramError: The language's input shape or alphabet is invalid.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    lang = catalog.languages[name]
    contract = lang.contract
    if lang.parameterized:
        raise ArgumentError(
            f"a generated {name} program reads no stdin for its input bits; "
            "pass the bits to instantiate() to embed them in source"
        )
    if not lang.runtime.reads_stdin:
        raise ArgumentError(f"{name} reads no stdin, so there is nothing to encode")
    # As in ``instantiate``: a 2 or a "1" is not caught downstream; it
    # encodes as a 1 and the program silently answers another row.
    bits = check_bits(bits, "bits")
    if truth_table is not None:
        from esolangs.generation.helpers import _validate_truth_table, check_table_text

        arity = _validate_truth_table(check_table_text(truth_table))
        if len(bits) != arity:
            raise ArgumentError(
                f"that table has {arity} input{'' if arity == 1 else 's'}, "
                f"but {len(bits)} bit{' was' if len(bits) == 1 else 's were'} "
                f"given; a {name} program built from it reads {arity}"
            )
    shape = contract.input_shape
    if shape in ("row_index", "row_number"):
        # A row number counts from one, for an input that must be positive.
        row = int("".join("01"[bit] for bit in bits), 2)
        return format_integer(row + (shape == "row_number")) + "\n"
    if shape not in ("line_per_bit", "char_stream", "char_stream_cyclic"):
        raise ProgramError(f"{name} has an invalid input shape")
    zero, one = _symbol_pair(name, contract.alphabet, "input encoding")
    stream = shape in CHAR_STREAMS
    if stream:
        # Two words form a uniquely decodable code exactly when they do not commute.
        if zero + one == one + zero:
            raise ProgramError(
                f"{name} has an invalid input encoding. "
                "The two bit values are ambiguous when concatenated."
            )
    elif "\n" in zero or "\n" in one:
        raise ProgramError(
            f"{name} has an invalid input encoding. Each bit must fit on one line."
        )
    elif zero.removesuffix("\r") == one.removesuffix("\r"):
        raise ProgramError(
            f"{name} has an invalid input encoding. "
            "The two bit lines match after CRLF decoding."
        )
    digits = [one if bit else zero for bit in bits]
    if stream:
        return "".join(digits)
    return "".join(f"{digit}\n" for digit in digits)


def read_answer(language: str, output: str, *, catalog: "Catalog | None" = None) -> str:
    """Return the answer bit, ``"0"`` or ``"1"``, a program's ``output`` carries.

    Most print it (last non-whitespace character); some dump their state.
    ``describe(language).answer_pattern`` and ``.answer_mode`` are the
    same facts as data (a verifier that hardcoded two dumps and forgot a
    third reported a passing language as broken).

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: The language answers by terminating: its answer is
            whether it halts, not anything printed; or ``output`` is not a
            string.
        ProgramError: ``output`` holds no readable answer or the language's
            answer contract is invalid.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if not _has_backing_type(output, str):
        raise ArgumentError(
            f"output must be a string, got {type(output).__name__}"
            + (
                "; pass its .output"
                if _has_backing_type(output, ExecutionResult)
                else ""
            )
        )
    output = str.__str__(output)
    contract = catalog.languages[name].contract
    values, pattern = _answer_codec(name, contract)
    if contract.answer_mode == "termination":
        raise ArgumentError(
            f"{name} answers by terminating, not by printing; a timeout is undecided"
        )
    return _read_output_answer(name, output, values, pattern, contract.note)


def _read_output_answer(
    name: str,
    output: str,
    values: tuple[str, str],
    pattern: re.Pattern[str] | None,
    note: str,
) -> str:
    """Read output using validated encodings and the compiled pattern, if any."""
    if pattern is not None:
        raw = None
        for match in pattern.finditer(output):
            raw = match[1 if match.re.groups else 0]
    else:
        raw = output.strip()[-1:] or None
    zero, one = values
    if raw == one:
        return "1"
    if raw == zero:
        return "0"
    # The note says in plain words where the answer lives, for every language
    # that has one: "as the last character" names the mechanism, not the
    # place, for a state dump.  The regex follows for maintainers.
    where = "in its final state" if pattern is not None else "as the last character"
    detail = f" -- {note}" if note else ""
    if pattern is not None:
        detail += f" (matched with {pattern.pattern!r})"
    raise ProgramError(
        f"{name} produced no answer this could read: expected {zero!r} or "
        f"{one!r} {where}, got {output[-40:]!r}{detail}"
    )
