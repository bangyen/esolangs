"""Sonata Boolean program generator: a unary row index strips the table.

The input is the initial string.  ``0_I->%0_I`` / ``1_I->%1_I`` mark it once;
a rule with one s-var a bit keeps the essential bits and appends their table.
Each kept bit doubles the unary index between ``@`` and ``#`` in one rewrite
(``_U_U``, or ``_U_Uu`` for a 1), each ``u`` strips a table entry, and
``@#^x_T->=^x`` leaves the answer.  For a AND NOT b the setup rule is
``%^a^b->^a^b@#0010``.  A symmetric table counts its ones instead, one ``u``
a 1, over m + 1 entries: AND's is ``%^a^b->^a^b@#001``
([ablations.symmetric_count]).  From m = 7 essential bits an asymmetric table
stores one char per row pair: ``0``/``1`` for 00/11, ``a`` for 01 (the answer
is the last bit), ``b`` for 10 (its negation); the last essential bit rides
after the table and only the other m - 1 double ([ablations.pair_table]).

Size:
    The projected table plus 4n + 101 chars (m <= 6); from m = 7 half the
    table plus 4n + 101 chars and at most 35 of final rules.  n=4 parity:
    118 chars, n=10 random 1847: 688 chars.

Decisions:
    Halving the table pairwise by a walking cursor (T + 101 chars) was not
    shipped: it transfers a collected rewriting generator step for step.
"""

from string import ascii_letters, digits

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
    symmetric_weights,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape

#: The index rules, then the set-up rules around the table.
_RULES = "{index}@u_U#^x_T->@_U#_T\n@#^x_T->=^x\n{setup}\n0_I->%0_I\n1_I->%1_I\n"
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


def _name(k: int) -> str:
    return _NAMES[k] if k < len(_NAMES) else chr(0x100 + k)


def sonata(truth_table: str) -> str:
    """Build a Sonata program whose final string ends in ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = read_at(truth_table, essential, n)
    symmetric = symmetric_weights(truth_table, n)
    if symmetric is not None:
        # A symmetric table counts its ones over m + 1 entries, never longer
        # than the doubling build ([ablations.symmetric_count]).
        return _program(n, essential, symmetric[1], _COUNT)
    if len(essential) >= _PAIR_FROM:
        return _pair_program(n, essential, table)
    return _program(n, essential, table, _DOUBLE)


def _pair_program(n: int, essential: list[int], table: str) -> str:
    """Return the rules storing ``table`` as one char per row pair."""
    symbols = "".join(_PAIR[table[i : i + 2]] for i in range(0, len(table), 2))
    bits = "".join("^" + _name(k) for k in range(n))
    kept = "".join("^" + _name(k) for k in essential[:-1])
    setup = f"%{bits}->{kept}@#{symbols}^{_name(essential[-1])}"
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
    setup = f"%{bits}->{kept}@#{table}"
    return _RULES.format(index=index, setup=setup)


LANGUAGE = Language(
    "Sonata",
    "sonata",
    category="program_based",
    boolean=sonata,
    # Not a tree: the table is a literal the row index strips.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
        answer_mode="dump",
        answer_pattern="=([01])",
        note="Sonata's input is its initial string and its output the final "
        "one, = and the answer",
    ),
    no_wrap="a newline ends a rule, and a rule cannot span two lines",
    eof="the input is the initial string, so an empty input is the empty string",
    example=Example(expected="=0"),
)
