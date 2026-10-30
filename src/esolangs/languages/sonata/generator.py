"""Sonata Boolean program generator: a unary row index strips the table.

The input is the initial string.  ``0_I->%0_I`` / ``1_I->%1_I`` mark it once;
a rule with one s-var a bit keeps the essential bits and appends their table.
Each kept bit doubles the unary index between ``@`` and ``#`` in one rewrite
(``_U_U``, or ``_U_Uu`` for a 1), each ``u`` strips a table entry, and
``@#^x_T->=^x`` leaves the answer.  For a AND NOT b the setup rule is
``%^a^b->^a^b@#0010``.  A symmetric table counts its ones instead, one ``u``
a 1, over m + 1 entries: AND's is ``%^a^b->^a^b@#001``
([ablations.symmetric_count]).

Size:
    The projected table plus 4n + 101 chars.  n=4 parity: 118 chars,
    n=10 random 1847: 1,165 chars.

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
    return _program(n, essential, table, _DOUBLE)


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
