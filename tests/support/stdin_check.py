"""Test oracle for the stdin half of the Boolean I/O contract."""

from esolangs.exceptions import ArgumentError, TruthTableError
from esolangs.generation.helpers import _validate_truth_table
from esolangs.registry import LANGUAGES, resolve
from esolangs.runtime.source_hints import with_hint


def _validate_shape_for_evaluate(truth_table: str) -> int:
    """Return the input count of ``truth_table``, refusing a malformed one."""
    if not isinstance(truth_table, str):
        raise with_hint(
            TruthTableError(
                f"truth table must be a string of '0' and '1', got "
                f"{type(truth_table).__name__}"
            ),
            ("pass truth-table text, for example '0110' for two-input XOR"),
        )
    return _validate_truth_table(truth_table)


def _check_stdin(language: str, stdin: str, truth_table: str | None = None) -> None:
    """Refuse ``stdin`` that cannot be what ``language`` wants to read."""
    name = resolve(language)
    lang = LANGUAGES[name]
    contract = lang.contract
    if lang.boolean is None or lang.parameterized:
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

    if shape in {"row_index", "row_number"}:
        # A row number is the row index plus one, for a language whose input
        # must be positive (Blindfolded Arithmetic).
        base = int(shape == "row_number")
        noun = "row number" if base else "row index"
        # ``isdecimal``, not ``isdigit``: a superscript like ``²`` passes
        # ``isdigit`` and then ``int`` rejects it with a bare ValueError.
        if len(lines) != 1 or not lines[0].isdecimal():
            raise ArgumentError(
                f"{name} reads one decimal {noun}, but stdin is {stdin.strip()!r}"
            )
        if len(lines[0]) > 1 and lines[0][0] == "0":
            # A leading zero is almost always the bit string typed out
            # (``0010`` parses as ten, answers row 10 not 2; count and range
            # both pass).  The bit reading is offered only when the digits
            # are bits: ``int('02', 2)`` crashed the refusal.
            if not set(lines[0]) - {"0", "1"}:
                try:
                    index_hint = str(int(lines[0], 2) + base)
                except ValueError as exc:
                    raise ArgumentError(
                        f"{name} reads one decimal {noun}; {len(lines[0])} "
                        f"input bits have a leading zero and their {noun} is "
                        "too large to print"
                    ) from exc
                raise ArgumentError(
                    f"{name} reads one decimal {noun}, and {lines[0]!r} "
                    f"has a leading zero -- if those are the input bits, the "
                    f"{noun.split()[-1]} is {index_hint}: "
                    f"`esolangs encode {name} {lines[0]}`"
                )
            raise ArgumentError(
                f"{name} reads one decimal {noun}, and {lines[0]!r} has a "
                f"leading zero, which a decimal {noun} never has"
            )
        if wanted is not None:
            try:
                index = int(lines[0])
            except ValueError as exc:
                # ``isdecimal`` passed, so the only way here is CPython's
                # 4300-digit int->str cap; the bare ValueError used to reach
                # the CLI's generic "this is a bug in esolangs" handler.
                raise ArgumentError(
                    f"{name} {noun} has {len(lines[0])} digits, more than the "
                    f"{wanted}-input program can name "
                    f"({base}..{2**wanted - 1 + base})"
                ) from exc
            if not base <= index < 2**wanted + base:
                raise ArgumentError(
                    f"{name} {noun} {lines[0]} is out of range for a "
                    f"{wanted}-input program ({base}..{2**wanted - 1 + base})"
                )
        return
    if shape in {"char_stream", "char_stream_cyclic"}:
        if contract.input_sets:
            first, _, rest = stdin.partition("\n")
            if rest.strip():
                raise ArgumentError(
                    f"{name} reads its bits from the first line, and stdin "
                    f"has more after it: {rest.strip()[:20]!r}"
                )
            stdin = first
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
        raise ArgumentError(
            f"{name} spells its bits {zero!r} and {one!r}, and {len(stray)} "
            f"stdin line(s) are outside that -- the first is {stray[0]!r}"
        )
    if wanted is not None and len(lines) != wanted:
        raise ArgumentError(
            f"{name} reads {wanted} line(s) for this table, but stdin has {len(lines)}"
        )
