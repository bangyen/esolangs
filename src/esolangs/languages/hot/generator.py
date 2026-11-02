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
Whole constants instead discard both stream bits per input with ``A0``,
then emit ``DCC`` or ``DDC``.

Size:
    Theta(T) text worst case: 18 chars a pair and 73 a reader stage;
    n=8 majority: 1,999 chars, n=10 parity: 14,640.
    Constants use 4n+3 characters and rewrites; n=8 zero: 35 chars.

Decisions:
    The identity is ``0K`` (``0 K y -> y``), not ``SKK``: with the ``(1, 0)``
    fold, n=10 parity is 14,640 chars against 15,696.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.hot.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: ``R_i`` with ``{}`` for ``R_(i+1)``.
_READ = "S(KK)(S(K(S(0K)))(S(KK)(S(KK)(S(K(S(0K)))(S(K(S(0K)))(S(KK)(S(K({})))))))))"
#: ``R_n``.
_ANSWER = (
    "S(KK)(S(K(S(0K)))(S(KK)(S(K(S(KK)))(S(K(S(0K)))(S(KK)"
    "(S(K(S(S(KS)K)))(S(S(KS)(S(KS)))(K(K(0K))))))))))"
)


def _tree(table: str, *, majority: bool = False) -> str:
    """Return the pair tree, emitting each character once from canonical IDs."""
    ids = subtree_ids(table)
    n = len(ids) - 1
    pieces: list[str] = []

    def emit(depth: int, slot: int, *, grouped: bool = False) -> None:
        if depth == n:
            pieces.append(table[slot])
            return
        if grouped:
            pieces.append("(")
        lo, hi = 2 * slot, 2 * slot + 1
        if (
            majority
            and depth == n - 2
            and table[4 * slot : 4 * slot + 4] in ("0001", "0111")
        ):
            # AND is lambda xy.xyx; OR is lambda xy.xxy, not searched terms.
            pieces.append("SSK" if table[4 * slot + 1] == "0" else "S(0K)(0K)")
        elif ids[depth + 1][lo] == ids[depth + 1][hi]:
            pieces.append("K")
            emit(depth + 1, lo, grouped=True)
        elif depth == n - 1 and table[lo : hi + 1] == "01":
            pieces.append("0K")
        else:
            pieces.append("S(S(0K)(K")
            emit(depth + 1, hi, grouped=True)
            pieces.append("))(K")
            emit(depth + 1, lo, grouped=True)
            pieces.append(")")
        if grouped:
            pieces.append(")")

    emit(0, 0)
    return "".join(pieces)


def hot(truth_table: str) -> str:
    """Build a Hot program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        # A0 drops one stream bit; each input is a marker followed by its value.
        return "A0" * (2 * n) + "D" + ("D" if truth_table[0] == "1" else "C") + "C"
    program = _ANSWER
    for _ in range(n):
        program = _READ.format(program)
    # Only the named family clears the gate ([ablations.majority_pair_rule]).
    majority = all(
        (bit == "1") == (2 * row.bit_count() > n) for row, bit in enumerate(truth_table)
    )
    return f"{program}({_tree(truth_table, majority=majority)})"


LANGUAGE = Language(
    "Hot",
    "hot",
    category="other",
    boolean=hot,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=wrap_chars,
    proof_execution=(execution, True, (1, 2, 3, 6)),
    proof_workspace=(workspace, True, (2, 3, 6)),
    eof="the stream past the input string is 0 bits",
    empty_program="a Hot program needs at least one combinator",
)
