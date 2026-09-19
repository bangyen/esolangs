"""Feeding a program and judging what it printed.

:func:`encode_inputs` builds the stdin for one row, :func:`check_stdin`
refuses a stdin the language cannot read, :func:`read_answer` turns output
into a bit.  Every judgement is a :func:`~esolangs.describe` fact applied.
"""

import re

from esolangs._describe import _example_for, describe
from esolangs._validate import check_bits
from esolangs.exceptions import (
    ArgumentError,
    ProgramError,
    TruthTableError,
)
from esolangs.registry import LANGUAGES, resolve


def encode_inputs(
    language: str,
    bits: list[int] | tuple[int, ...],
    truth_table: str | None = None,
) -> str:
    """Return the stdin that feeds ``bits`` to a ``language`` program.

    Most read one ``0``/``1`` line per input; Grapheme spells ``%``/``A``,
    Clockwise wants one line, Fargo one number, Taglate pads an odd count --
    each answering the obvious guess with a wrong bit.  ``truth_table`` is
    needed only where the encoding depends on arity.  A language that embeds
    its inputs is refused; use :func:`instantiate`.
    """
    # Every registered language has a committed example, so the lookup
    # always finds one; ``example_stems`` covers all 59 and a test pins that.
    name = resolve(language)
    example = _example_for(LANGUAGES[name].id)
    if example.fill is not None:
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
    if truth_table is not None:
        from esolangs.tools.helpers import _validate_truth_table

        if not isinstance(truth_table, str):
            raise TruthTableError(
                f"truth table must be a string of '0' and '1', got "
                f"{type(truth_table).__name__}"
            )
        arity = _validate_truth_table(truth_table)
        if len(bits) != arity:
            raise ArgumentError(
                f"that table has {arity} input{'' if arity == 1 else 's'}, "
                f"but {len(bits)} bit{' was' if len(bits) == 1 else 's were'} "
                f"given; a {name} program built from it reads {arity}"
            )
    if example.input_shape == "row_index":
        row = sum(bit << (len(bits) - 1 - i) for i, bit in enumerate(bits))
        return f"{row}\n"
    zero, one = example.alphabet
    padded = [0, *bits] if example.ghost_digit and len(bits) % 2 and bits[1:] else bits
    digits = [one if bit else zero for bit in padded]
    if example.input_shape == "one_line":
        return "".join(digits)
    return "".join(f"{digit}\n" for digit in digits)


def check_stdin(language: str, stdin: str, truth_table: str | None = None) -> None:
    """Refuse ``stdin`` that cannot be what ``language`` wants to read.

    The CLI's judge, for Python callers: a ``0``/``1`` line to Grapheme,
    several lines to Clockwise, a non-number to Fargo.  Raises
    :class:`~esolangs.exceptions.ArgumentError`; :func:`run` only warns.
    ``truth_table`` adds the count, catching surplus lines.  Every check reads
    a :func:`describe` field.
    """
    facts = describe(language)
    name = str(facts["name"])
    if not facts["reads_input"]:
        raise ArgumentError(
            f"{name} embeds its inputs in the program and reads no stdin; "
            f"there is nothing to check"
        )
    if not isinstance(stdin, str):
        raise ArgumentError(f"stdin must be a string, got {type(stdin).__name__}")
    shape = str(facts["input_shape"])
    zero, one = facts["input_encoding"]
    # ``splitlines``, as :class:`ScriptedIO` cuts it.  ``strip().split``
    # dropped a leading/trailing blank line the interpreter still read:
    # ``run("brainfuck", xor, "\n\n")`` answered 1 unwarned.
    lines = stdin.splitlines()
    wanted = None
    if truth_table is not None:
        wanted = _validate_shape_for_evaluate(truth_table)
        if shape == "line_per_bit_padded" and wanted % 2 and wanted > 1:
            # Taglate's pad is a digit the program reads like any other, so
            # an odd input count above one costs an extra line.  Read off
            # the shape, which is where that fact already lives.
            wanted += 1

    if shape == "row_index":
        if len(lines) != 1 or not lines[0].isdigit():
            raise ArgumentError(
                f"{name} reads one decimal row index, but stdin is {stdin.strip()!r}"
            )
        if len(lines[0]) > 1 and lines[0][0] == "0":
            # A leading zero is almost always the bit string typed out
            # (``0010`` parses as ten, answers row 10 not 2; count and range
            # both pass).  The bit reading is offered only when the digits
            # are bits: ``int('02', 2)`` crashed the refusal.
            if not set(lines[0]) - {"0", "1"}:
                raise ArgumentError(
                    f"{name} reads one decimal row index, and {lines[0]!r} "
                    f"has a leading zero -- if those are the input bits, the "
                    f"index is {int(lines[0], 2)}: "
                    f"`esolangs encode {name} {lines[0]}`"
                )
            raise ArgumentError(
                f"{name} reads one decimal row index, and {lines[0]!r} has a "
                f"leading zero, which a decimal index never has"
            )
        if wanted is not None and int(lines[0]) >= 2**wanted:
            raise ArgumentError(
                f"{name} row index {lines[0]} is out of range for a "
                f"{wanted}-input program (0..{2**wanted - 1})"
            )
        return
    if shape == "one_line":
        if len(lines) != 1:
            raise ArgumentError(
                f"{name} wants every bit on one line, but stdin is {len(lines)} line(s)"
            )
        if wanted is not None and len(lines[0]) != wanted:
            raise ArgumentError(
                f"{name} wants {wanted} bits on its one line, got {len(lines[0])}"
            )
        # Per character (a character is a bit here); this branch used to
        # return past the per-line alphabet check, so
        # ``check_stdin("Clockwise", "999", table)`` was accepted.
        astray = [char for char in lines[0] if char not in (zero, one)]
        if astray:
            raise ArgumentError(
                f"{name} spells its bits {zero!r} and {one!r}, and "
                f"{len(astray)} character(s) of its one line are outside "
                f"that -- the first is {astray[0]!r}"
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
    two differ -- RAM0's answer is its ``z`` register three lines up, A
    Painter Ant marks the ant's cell ``o``/``@``.
    ``describe(language)["answer_pattern"]`` is the same fact as data (a
    verifier that hardcoded two dumps and forgot a third reported a passing
    language as broken).  A termination-answer language (123, ArrowQueue,
    Point Break) raises :class:`~esolangs.exceptions.ArgumentError`: bound
    the run and catch :class:`~esolangs.exceptions.ExecutionTimeoutError`.
    """
    name = resolve(language)
    if not isinstance(output, str):
        raise ProgramError(f"output must be a string, got {type(output).__name__}")
    example = _example_for(LANGUAGES[name].id)
    if example.answer_mode == "termination":
        raise ArgumentError(
            f"{name} answers by terminating, not by printing: run it under a "
            f"timeout and read a caught ExecutionTimeoutError as the 1"
        )
    if example.answer_pattern:
        found = re.findall(example.answer_pattern, output)
        raw = found[-1] if found else ""
    else:
        raw = output.strip()[-1:]
    zero, one = example.answer_values
    if raw == one:
        return "1"
    if raw == zero:
        return "0"
    # For a pattern language the regex used to be the *whole* explanation,
    # which is the right thing to hand a maintainer and nothing at all to
    # hand a reader wondering where the answer was supposed to be.  The note
    # is the plain-language half and already exists; the pattern follows it
    # in parentheses, so neither reader loses.
    where = "in its final state" if example.answer_pattern else "as the last character"
    # The note whenever there is one, not just for the two pattern
    # languages: Back, Minsky Swap and LaserFuck dump their state and are
    # read by last character, so "as the last character" is a true account
    # of the mechanism and no account at all of where the answer lives.
    detail = f" -- {example.note}" if example.note else ""
    if example.answer_pattern:
        detail += f" (matched with {example.answer_pattern!r})"
    raise ProgramError(
        f"{name} produced no answer this could read: expected {zero!r} or "
        f"{one!r} {where}, got {output[-40:]!r}{detail}"
    )


def _validate_shape_for_evaluate(truth_table: str) -> int:
    """Return the input count of ``truth_table``, refusing a malformed one.

    The row loop needs the arity before :func:`generate` validates, and a
    generator's error named the generator rather than the table.
    """
    from esolangs.tools.helpers import _validate_truth_table

    if not isinstance(truth_table, str):
        raise TruthTableError(
            f"truth table must be a string of '0' and '1', got "
            f"{type(truth_table).__name__}"
        )
    return _validate_truth_table(truth_table)
