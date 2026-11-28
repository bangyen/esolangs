"""Sonata Boolean program generator: a unary row index strips the table.

The input is the initial string. Through three inputs one rule a row
rewrites it to its answer. Otherwise a rule with one s-var a bit keeps the
essential bits and appends their table. Each kept bit doubles the unary
index between ``@`` and ``#`` in one rewrite (``_U_U``, or ``_U_Uu`` for a
1), each ``u`` strips a table entry, and
``@#^x_T->=^x`` leaves the answer.  For a AND NOT b the setup rule is
``%^a^b->^a^b@#0010``.  A symmetric table counts its ones instead, one ``u``
a 1, over m + 1 entries: AND's is ``%^a^b->^a^b@#001``
([ablations.symmetric_count]).  From m = 7 essential bits an asymmetric table
stores one char per row pair: ``0``/``1`` for 00/11, ``a`` for 01 (the answer
is the last bit), ``b`` for 10 (its negation); the last essential bit rides
after the table and only the other m - 1 double ([ablations.pair_table]).

Size:
    (n + 5)T - 1 chars through n = 3. Beyond, the projected table plus
    4n + 80 chars (m <= 6); from m = 7 half the table plus 4n + 80 chars
    and at most 35 of final rules. n=4 parity:
    97 chars, n=10 random 1847: 667 chars. Constants: 2n+5 chars (16 at n=2),
    two commands and 8max(n,2)+2 written bits below the name limit.
    At 55,041 inputs the setup uses a mask with a fixed set of variable names.

Decisions:
    Halving the table pairwise by a walking cursor (T + 101 chars) was not
    shipped: it transfers a collected rewriting generator step for step.
"""

from string import ascii_letters, digits

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.lookup import constant_output, symmetric_outputs
from esolangs.generation.projection import essential_inputs, read_at
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program

#: The index rules, then the set-up rules around the table.
# After setup, a remaining bit matches the index rules; otherwise a nonempty
# index matches strip, and an empty one matches final. Those precede setup.
# The two-character result could match a two-input setup again; row rules
# take n = 2, so no input marker is needed ([ablations.drop_input_marker]).
_RULES = "{index}@u_U#^x_T->@_U#_T\n@#^x_T->=^x\n{setup}\n"
_MARKER = "0_I->%0_I\n1_I->%1_I\n"
#: Through this many inputs one ``row->=answer`` rule a row, (n + 5)T - 1
#: chars in two steps, beats every other route: all 268 nonconstant tables
#: at n = 2, 3 and none of 2,001 at n = 4.
_ROW_RULES_TO = 3
#: Doubling the index a bit, or counting its ones.
_DOUBLE = "0_R@_U#_T->_R@_U_U#_T\n1_R@_U#_T->_R@_U_Uu#_T\n"
_COUNT = "0_R@_U#_T->_R@_U#_T\n1_R@_U#_T->_R@_Uu#_T\n"
#: Final rules for the pair symbols ``a`` (01) and ``b`` (10); ``z`` is the
#: last essential bit, which follows the table.
_PAIR_A = "@#a_T^z->=^z\n"
_PAIR_B = "@#b_T0->=1\n@#b_T1->=0\n"
#: Essential bits from which pairs beat the plain table (m = 6: never).
_PAIR_FROM = 7
_PAIR = {"00": "0", "11": "1", "01": "a", "10": "b"}
#: Names for the projection's s-vars, one an input.
_NAMES = ascii_letters + digits
# _name would first produce a surrogate at input index 0xD800 - 0x100.
_MASK_FROM = 0xD800 - 0x100 + 1
_MASK_SKIP = 512


def _name(k: int) -> str:
    return _NAMES[k] if k < len(_NAMES) else chr(0x100 + k)


def sonata(truth_table: str) -> str:
    """Build a Sonata program whose final string ends in ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    if (bit := constant_output(truth_table)) is not None:
        if n >= _MASK_FROM:
            return _masked_program(n, [], bit)
        # Only n=2 can match the two-character result again: guard its first bit.
        if n == 2:
            return "".join(f"{guard}^a->={bit}\n" for guard in "01")
        bits = "".join("^" + _name(k) for k in range(n))
        return f"{bits}->={bit}\n"
    if 2 <= n <= _ROW_RULES_TO:
        # A one-character answer cannot match a rule over two or more bits.
        return "\n".join(f"{row:0{n}b}->={bit}" for row, bit in enumerate(truth_table))
    essential = essential_inputs(truth_table, n)
    table = read_at(truth_table, essential, n)
    if n >= _MASK_FROM:
        return _masked_program(n, essential, table)
    if (
        len(essential) >= 2
        and (symmetric := symmetric_outputs(table, len(essential))) is not None
    ):
        # A symmetric table counts its ones over m + 1 entries, never longer
        # than the doubling build ([ablations.symmetric_count]).
        return _program(n, essential, symmetric, _COUNT)
    if len(essential) >= _PAIR_FROM:
        return _pair_program(n, essential, table)
    return _program(n, essential, table, _DOUBLE)


def _masked_program(n: int, essential: list[int], table: str) -> str:
    """Consume a source mask in lockstep with the input, using fixed names."""
    mask = bytearray(b"0") * n
    for bit in essential:
        mask[bit] = ord("1")
    skip = ""
    if n - len(essential) >= _MASK_SKIP:
        # Skip runs of ignored bits with a fixed, UTF-8-safe set of names.
        names = "".join("^" + chr(0x100 + k) for k in range(_MASK_SKIP))
        zeros = "0" * _MASK_SKIP
        skip = f"!{names}_R&{zeros}_M@_U#_T->!_R&_M@_U#_T\n"
    return (
        skip
        + "!^a_R&0_M@_U#_T->!_R&_M@_U#_T\n"
        + "!0_R&1_M@_U#_T->!_R&_M@_U_U#_T\n"
        + "!1_R&1_M@_U#_T->!_R&_M@_U_Uu#_T\n"
        + "!&@u_U#^x_T->!&@_U#_T\n"
        + "!&@#^x_T->=^x\n"
        + f"%_I->!_I&{mask.decode('ascii')}@#{table}\n"
        + _MARKER
    )


def _pair_program(n: int, essential: list[int], table: str) -> str:
    """Return the rules storing ``table`` as one char per row pair."""
    symbols = "".join(_PAIR[table[i : i + 2]] for i in range(0, len(table), 2))
    bits = "".join("^" + _name(k) for k in range(n))
    kept = "".join("^" + _name(k) for k in essential[:-1])
    setup = f"{bits}->{kept}@#{symbols}^{_name(essential[-1])}"
    final = (_PAIR_A if "a" in symbols else "") + (_PAIR_B if "b" in symbols else "")
    return _RULES.format(index=_DOUBLE, setup=setup).replace(
        "@#^x_T->=^x\n", final + "@#^x_T->=^x\n"
    )


def _program(n: int, essential: list[int], table: str, index: str) -> str:
    """Return the rules for ``table`` indexed by ``index`` over ``essential``."""
    # One s-var a bit, so input of another length halts unanswered; the
    # right side keeps the essential bits.
    bits = "".join("^" + _name(k) for k in range(n))
    kept = "".join("^" + _name(k) for k in essential)
    setup = f"{bits}->{kept}@#{table}"
    return _RULES.format(index=index, setup=setup)


def sonata_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return sonata(request.table)
