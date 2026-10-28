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
from esolangs.generation.helpers import _validate_truth_table, check_table_text
from esolangs.registry import LANGUAGES, resolve
from esolangs.registry._contracts import CHAR_STREAMS
from esolangs.runtime._validate import check_bits


def encode_inputs(
    language: str,
    bits: list[int] | tuple[int, ...],
    *,
    truth_table: str | None = None,
) -> str:
    """Return the stdin that feeds ``bits`` to a ``language`` program.

    Character readers take adjacent digits; numeric readers take tokens;
    each language spells its bits per its registered ``input_encoding`` and
    ``input_shape``, so the obvious guess is often a wrong bit.

    Args:
        bits: One integer 0 or 1 per input.
        truth_table: Needed only where the encoding depends on arity; when
            given, ``bits`` must match its input count.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: The language reads no stdin (it embeds its inputs, so
            use :func:`instantiate`, or has no input instruction), a bit is
            not an integer 0 or 1, or ``bits`` does not match
            ``truth_table``'s input count.
        TruthTableError: ``truth_table`` is not a binary string of length
            ``2**n``.
    """
    name = resolve(language)
    lang = LANGUAGES[name]
    contract = lang.contract
    if lang.parameterized:
        raise ArgumentError(
            f"{name} embeds its inputs in the program and reads no stdin, so "
            f"there is nothing to encode; pass the bits to instantiate() "
            f"instead"
        )
    if lang.boolean is None:
        # Deadfish, HQ9+ and Nope. have no input instruction; the registry's
        # default contract encoded ``"1\n0\n"`` for them all the same.
        raise ArgumentError(f"{name} reads no stdin, so there is nothing to encode")
    # As in ``instantiate``: a 2 or a "1" is not caught downstream; it
    # encodes as a 1 and the program silently answers another row.
    bits = check_bits(bits, "bits")
    if truth_table is not None and lang.boolean is not None:
        check_table_text(truth_table)
        arity = _validate_truth_table(truth_table)
        if len(bits) != arity:
            raise ArgumentError(
                f"that table has {arity} input{'' if arity == 1 else 's'}, "
                f"but {len(bits)} bit{' was' if len(bits) == 1 else 's were'} "
                f"given; a {name} program built from it reads {arity}"
            )
    if contract.input_shape in {"row_index", "row_number"}:
        # A row number counts from one, for an input that must be positive.
        row = sum(bit << (len(bits) - 1 - i) for i, bit in enumerate(bits))
        row += contract.input_shape == "row_number"
        try:
            return f"{row}\n"
        except ValueError as exc:
            # CPython caps int->str at 4300 digits; a bare ValueError broke the
            # every-error-is-EsolangError promise (``[1] * 15000``).
            raise ArgumentError(
                f"{name} reads a decimal row, and {len(bits)} bits name "
                f"an integer too large to render as one: {exc}"
            ) from exc
    zero, one = contract.alphabet
    digits = [one if bit else zero for bit in bits]
    if contract.input_shape in CHAR_STREAMS:
        return "".join(digits)
    return "".join(f"{digit}\n" for digit in digits)


def read_answer(language: str, output: str) -> str:
    """Return the answer bit, ``"0"`` or ``"1"``, a program's ``output`` carries.

    Most print it (last non-whitespace character); some dump their state.
    ``describe(language)["answer_pattern"]`` and ``answer_mode`` are the
    same facts as data (a verifier that hardcoded two dumps and forgot a
    third reported a passing language as broken).

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: The language answers by terminating: its answer is
            whether it halts, not anything printed; or ``output`` is not a
            string.
        ProgramError: ``output`` holds no readable answer.
    """
    name = resolve(language)
    if not isinstance(output, str):
        raise ArgumentError(f"output must be a string, got {type(output).__name__}")
    contract = LANGUAGES[name].contract
    if contract.answer_mode == "termination":
        raise ArgumentError(
            f"{name} answers by terminating, not by printing; a timeout is undecided"
        )
    if contract.answer_pattern:
        found = re.findall(contract.answer_pattern, output)
        raw = found[-1] if found else ""
    else:
        raw = output.strip()[-1:]
    zero, one = contract.answer_values
    if raw == one:
        return "1"
    if raw == zero:
        return "0"
    # The note says in plain words where the answer lives, for every language
    # that has one: "as the last character" names the mechanism, not the
    # place, for a state dump.  The regex follows for maintainers.
    where = "in its final state" if contract.answer_pattern else "as the last character"
    detail = f" -- {contract.note}" if contract.note else ""
    if contract.answer_pattern:
        detail += f" (matched with {contract.answer_pattern!r})"
    raise ProgramError(
        f"{name} produced no answer this could read: expected {zero!r} or "
        f"{one!r} {where}, got {output[-40:]!r}{detail}"
    )
