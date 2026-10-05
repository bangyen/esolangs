"""Feeding a program and judging what it printed.

:func:`encode_inputs` builds the stdin for one row, :func:`_check_stdin`
refuses a stdin the language cannot read, :func:`read_answer` turns output
into a bit.  Every judgement applies the registered Boolean I/O contract.
"""

import re

from esolangs._validate import check_bits
from esolangs.exceptions import (
    ArgumentError,
    ProgramError,
    TruthTableError,
)
from esolangs.interpreters.source_hints import with_hint
from esolangs.registry import LANGUAGES, resolve


def encode_inputs(
    language: str,
    bits: list[int] | tuple[int, ...],
    truth_table: str | None = None,
) -> str:
    """Return the stdin that feeds ``bits`` to a ``language`` program.

    Character readers take adjacent digits; numeric readers take tokens.
    Grapheme spells ``%``/``A``, Fargo takes a row index, Taglate pads odd counts --
    each answering the obvious guess with a wrong bit.  ``truth_table`` is
    needed only where the encoding depends on arity.  A language that embeds
    its inputs is refused; use :func:`instantiate`.
    """
    name = resolve(language)
    contract = LANGUAGES[name].contract
    if contract.parameterized:
        raise ArgumentError(
            f"{name} embeds its inputs in the program and reads no stdin, so "
            f"there is nothing to encode; pass the bits to instantiate() "
            f"instead"
        )
    # Checked for the same reason ``instantiate`` checks it: a 2 or a "1"
    # is not caught downstream.  It encodes as a 1 and the program answers
    # a different row of the table, which is the wrong answer arriving with
    # no sign that anything went astray.
    bits = check_bits(bits, "bits")
    if truth_table is not None and LANGUAGES[name].boolean is not None:
        from esolangs.tools.helpers import _validate_truth_table

        if not isinstance(truth_table, str):
            raise with_hint(
                TruthTableError(
                    f"truth table must be a string of '0' and '1', got "
                    f"{type(truth_table).__name__}"
                ),
                ("pass truth-table text, for example '0110' for two-input XOR"),
            )
        arity = _validate_truth_table(truth_table)
        if len(bits) != arity:
            raise ArgumentError(
                f"that table has {arity} input{'' if arity == 1 else 's'}, "
                f"but {len(bits)} bit{' was' if len(bits) == 1 else 's were'} "
                f"given; a {name} program built from it reads {arity}"
            )
    if contract.input_shape == "row_index":
        row = sum(bit << (len(bits) - 1 - i) for i, bit in enumerate(bits))
        try:
            return f"{row}\n"
        except ValueError as exc:
            # CPython caps int->str at 4300 digits, and a row index that wide
            # names a row no program could read.  It escaped as a bare
            # ValueError past the "every deliberate error is an EsolangError"
            # promise (``encode_inputs("Fargo", [1] * 15000)``).
            raise ArgumentError(
                f"{name} reads a decimal row index, and {len(bits)} bits name "
                f"an integer too large to render as one: {exc}"
            ) from exc
    zero, one = contract.alphabet
    padded = [0, *bits] if contract.ghost_digit and len(bits) % 2 and bits[1:] else bits
    digits = [one if bit else zero for bit in padded]
    if contract.input_shape in {
        "char_stream",
        "char_stream_padded",
        "char_stream_cyclic",
    }:
        return "".join(digits)
    return "".join(f"{digit}\n" for digit in digits)


def _check_stdin(language: str, stdin: str, truth_table: str | None = None) -> None:
    """Refuse ``stdin`` that cannot be what ``language`` wants to read.

    The CLI's judge, for Python callers: a wrong alphabet, unexpected
    character, or non-number row index.  Raises
    :class:`~esolangs.exceptions.ArgumentError`; :func:`run` does not validate it.
    ``truth_table`` adds the count, catching surplus inputs.  Every check reads
    the registered Boolean I/O contract.
    """
    name = resolve(language)
    lang = LANGUAGES[name]
    contract = lang.contract
    if lang.boolean is None or contract.parameterized:
        raise ArgumentError(
            f"{name} embeds its inputs in the program and reads no stdin; "
            f"there is nothing to check"
        )
    if not isinstance(stdin, str):
        raise ArgumentError(f"stdin must be a string, got {type(stdin).__name__}")
    shape = contract.input_shape
    zero, one = contract.alphabet
    # ``splitlines``, as :class:`ScriptedIO` cuts it.  ``strip().split``
    # dropped a leading/trailing blank line the interpreter still read:
    # ``run("brainfuck", xor, "\n\n")`` answered 1 unwarned.
    lines = stdin.splitlines()
    wanted = None
    if truth_table is not None:
        wanted = _validate_shape_for_evaluate(truth_table)
        if shape == "char_stream_padded" and wanted % 2 and wanted > 1:
            # Taglate's pad is a digit the program reads like any other, so
            # an odd input count above one costs an extra character.  Read off
            # the shape, which is where that fact already lives.
            wanted += 1

    if shape == "row_index":
        # ``isdecimal``, not ``isdigit``: a superscript like ``²`` passes
        # ``isdigit`` and then ``int`` rejects it with a bare ValueError.
        if len(lines) != 1 or not lines[0].isdecimal():
            raise ArgumentError(
                f"{name} reads one decimal row index, but stdin is {stdin.strip()!r}"
            )
        if len(lines[0]) > 1 and lines[0][0] == "0":
            # A leading zero is almost always the bit string typed out
            # (``0010`` parses as ten, answers row 10 not 2; count and range
            # both pass).  The bit reading is offered only when the digits
            # are bits: ``int('02', 2)`` crashed the refusal.
            if not set(lines[0]) - {"0", "1"}:
                try:
                    index_hint = str(int(lines[0], 2))
                except ValueError as exc:
                    raise ArgumentError(
                        f"{name} reads one decimal row index; {len(lines[0])} "
                        "input bits have a leading zero and their index is "
                        "too large to print"
                    ) from exc
                raise ArgumentError(
                    f"{name} reads one decimal row index, and {lines[0]!r} "
                    f"has a leading zero -- if those are the input bits, the "
                    f"index is {index_hint}: "
                    f"`esolangs encode {name} {lines[0]}`"
                )
            raise ArgumentError(
                f"{name} reads one decimal row index, and {lines[0]!r} has a "
                f"leading zero, which a decimal index never has"
            )
        if wanted is not None:
            try:
                index = int(lines[0])
            except ValueError as exc:
                # ``isdecimal`` passed, so the only way here is CPython's
                # 4300-digit int->str cap; the bare ValueError used to reach
                # the CLI's generic "this is a bug in esolangs" handler.
                raise ArgumentError(
                    f"{name} row index has {len(lines[0])} digits, more than "
                    f"the {wanted}-input program can name (0..{2**wanted - 1})"
                ) from exc
            if index >= 2**wanted:
                raise ArgumentError(
                    f"{name} row index {lines[0]} is out of range for a "
                    f"{wanted}-input program (0..{2**wanted - 1})"
                )
        return
    if shape in {"char_stream", "char_stream_padded", "char_stream_cyclic"}:
        # A reader that skips whitespace (``input_bit``) takes its bits
        # wherever they sit, so the check reads the same text it will.
        checked = (
            "".join(char for char in stdin if not char.isspace())
            if contract.ignores_whitespace
            else stdin
        )
        astray = [char for char in checked if char not in (zero, one)]
        if astray:
            raise ArgumentError(
                f"{name} spells its bits {zero!r} and {one!r}, and "
                f"stdin contains an unexpected character {astray[0]!r}"
            )
        if wanted is not None and len(checked) != wanted:
            raise ArgumentError(
                f"{name} reads {wanted} characters for this table, "
                f"but stdin has {len(checked)}"
            )
        return
    stray = [line for line in lines if line not in (zero, one)]
    if stray:
        # Phrased around the alphabet rather than the stray count, because
        # the useful half is what this language *does* spell its bits with:
        # a reader who fed 0/1 lines to Grapheme needs '%' and 'A', not a
        # tally of how many lines were wrong.
        raise ArgumentError(
            f"{name} spells its bits {zero!r} and {one!r}, and {len(stray)} "
            f"stdin line(s) are outside that -- the first is {stray[0]!r}"
        )
    if wanted is not None and len(lines) != wanted:
        raise ArgumentError(
            f"{name} reads {wanted} line(s) for this table, but stdin has {len(lines)}"
        )


def read_answer(language: str, output: str) -> str:
    """Return the answer bit a ``language`` program's ``output`` carries.

    Most print it (last non-whitespace character); six dump their state, and
    two differ -- RAM0's answer is on its ``z:`` line, A Painter Ant marks
    the ant's cell ``o``/``@``.
    ``describe(language)["answer_pattern"]`` is the same fact as data (a
    verifier that hardcoded two dumps and forgot a third reported a passing
    language as broken).  A termination-answer language (123, ArrowQueue,
    Crement, Vandevelo) raises :class:`~esolangs.exceptions.ArgumentError`:
    its answer is whether it halts, not anything printed.
    """
    name = resolve(language)
    if not isinstance(output, str):
        raise ProgramError(f"output must be a string, got {type(output).__name__}")
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
    # For a pattern language the regex used to be the *whole* explanation,
    # which is the right thing to hand a maintainer and nothing at all to
    # hand a reader wondering where the answer was supposed to be.  The note
    # is the plain-language half and already exists; the pattern follows it
    # in parentheses, so neither reader loses.
    where = "in its final state" if contract.answer_pattern else "as the last character"
    # The note whenever there is one, not just for the two pattern
    # languages: Back, Minsky Swap and LaserFuck dump their state and are
    # read by last character, so "as the last character" is a true account
    # of the mechanism and no account at all of where the answer lives.
    detail = f" -- {contract.note}" if contract.note else ""
    if contract.answer_pattern:
        detail += f" (matched with {contract.answer_pattern!r})"
    raise ProgramError(
        f"{name} produced no answer this could read: expected {zero!r} or "
        f"{one!r} {where}, got {output[-40:]!r}{detail}"
    )


def _validate_shape_for_evaluate(truth_table: str) -> int:
    """Return the input count of ``truth_table``, refusing a malformed one."""
    from esolangs.tools.helpers import _validate_truth_table

    if not isinstance(truth_table, str):
        raise with_hint(
            TruthTableError(
                f"truth table must be a string of '0' and '1', got "
                f"{type(truth_table).__name__}"
            ),
            ("pass truth-table text, for example '0110' for two-input XOR"),
        )
    return _validate_truth_table(truth_table)
