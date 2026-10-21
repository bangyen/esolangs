"""Hot Boolean program generator: a chain of bit readers over a table tree.

The table is a tree of Church pairs ``λs. s hi lo`` keyed by input 0 at the
root, with the combinators ``1`` and ``0`` as leaves; equal halves fold to
``K half``, and the pair ``(1, 0)`` to the identity.  The program is
``R_0 tree`` for the stages

    R_i = λt m f. f (λb a. a (a (λx. R_(i+1) (t x))))
    R_n = λt m f. f (λb a. b (λd c. d (t d c c)))

compiled to ``S``/``K`` by bracket abstraction, each holding the next as a
constant.  ``f`` is an appended ``F``, which hands ``B`` and ``A``; ``a (a
...)`` reads a marker (the next stage's ``m``) and a bit, and the tree
applied to the bits picks ``D`` or ``C`` between the opening 1 and closing 0.

Size:
    Theta(T) text worst case: 14 chars a pair and 75 a reader stage;
    n=4 parity: 594 chars, n=10 parity: 14,640.

Decisions:
    The identity is ``0K`` (``0 K y -> y``), not ``SKK``: with the ``(1, 0)``
    fold, n=10 parity is 14,640 chars against 15,696.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: ``R_i`` with ``{}`` for ``R_(i+1)``.
_READ = "S(KK)(S(K(S(0K)))(S(KK)(S(KK)(S(K(S(0K)))(S(K(S(0K)))(S(KK)(S(K({})))))))))"
#: ``R_n``.
_ANSWER = (
    "S(KK)(S(K(S(0K)))(S(KK)(S(K(S(KK)))(S(K(S(0K)))(S(KK)"
    "(S(K(S(S(KS)K)))(S(S(KS)(S(KS)))(K(K(0K))))))))))"
)


def _tree(table: str) -> str:
    """Return the pair tree whose applications to the bits pick the leaf."""
    if len(table) == 1:
        return table
    half = len(table) // 2
    lo, hi = table[:half], table[half:]
    if lo == hi:
        return f"K{_grouped(_tree(lo))}"
    if (hi, lo) == ("1", "0"):
        return "0K"
    return f"S(S(0K)(K{_grouped(_tree(hi))}))(K{_grouped(_tree(lo))})"


def _grouped(term: str) -> str:
    """Return ``term`` as an argument: a leaf bare, an application grouped."""
    return term if len(term) == 1 else f"({term})"


def hot(truth_table: str) -> str:
    """Build a Hot program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    program = _ANSWER
    for _ in range(n):
        program = _READ.format(program)
    return f"{program}({_tree(truth_table)})"


LANGUAGE = Language(
    "Hot",
    "hot",
    category="other",
    boolean=hot,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=wrap_chars,
    eof="the stream past the input string is 0 bits",
    empty_program="a Hot program needs at least one combinator",
)
