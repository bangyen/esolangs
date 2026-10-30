"""Basicfuck Boolean program generator: a decision tree over named variables.

Each input is read into its own variable and, if the tree tests it, reduced
from its digit to 0/1 with ``-= 48``.  A node tests ``if(v){..}`` for the
one arm and ``if!(v){..}`` for the zero arm: the variable is not written in
between, so both tests see the same bit and exactly one arm runs.  A node
whose halves agree skips the test, and an empty arm drops its ``if``.  A
repeated subtree is a block ``if(f){..}`` after the tree, entered through a
flag each caller sets (a run follows one path, so a flag is set once).  The
answer cell starts at 0 and each marked leaf adds 1; a closing ``+= 48`` and
``write`` print it.  The complement's tree (marking the zero rows, counting
down, closing with ``+= 49``) races the plain one; ``o=wrap`` makes the
-1 come out as 255 and the sum land on 48 or 49.

Size:
    O(T) at most 14T + 16n + 43 chars, O(n) for parity; n=4 parity: 284
    chars, n=10 parity: 789, n=10 and: 293.

Decisions:
    A subtree is shared only when ``m * body > body + 5m + 9`` for its ``m``
    callers, and at most the 52 - n largest savings get a flag: names
    stay one character.  Blocks follow the tree in depth order, so each
    flag is set before its block is tested.  Sharing never lost to the
    plain tree on 253 tables, n=2..12.
"""

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    short_name,
    subtree_ids,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

#: Single-character names: no reserved word is one, and 53 cover every table
#: a string can hold (n + 1 <= 53 up to 2**52 rows).
_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"


def basicfuck(truth_table: str) -> str:
    """Build a Basicfuck program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    flipped = truth_table.translate(str.maketrans("01", "10"))
    plain = _program(truth_table, n, "+", _ASCII_ZERO)
    return min(plain, _program(flipped, n, "-", _ASCII_ZERO + 1), key=len)


type _Key = tuple[int, int]  # (depth, subtree id): a node that tests an input
type _Ref = _Key | int  # a node, or a constant leaf (0 or 1)

#: Flag names left after the inputs and the answer.
_NAMES = len(_LETTERS)
#: Characters of ``f+=1;``, the call; of ``if(f){`` and ``}``, the block; and
#: of ``,f`` in ``#allocate``, so a node is shared only when
#: ``m * body > body + 5m + 9`` for its ``m`` callers.
_CALL, _BLOCK, _ALLOC = 5, 7, 2


def _program(truth_table: str, n: int, mark: str, base: int) -> str:
    """The program whose tree marks every 1 leaf of ``truth_table``.

    A mark adds or subtracts 1 from the answer cell; ``base`` closes it.  A
    repeated subtree that pays for it becomes a block ``if(f){..}`` after the
    tree, and each place the tree would descend into it sets ``f`` instead.
    """
    ids = subtree_ids(truth_table)
    reps: dict[_Key, int] = {}
    levels: list[list[_Key]] = [[] for _ in range(n)]
    children: dict[_Key, tuple[_Ref, _Ref]] = {}

    def resolve(depth: int, k: int) -> _Ref:
        """The leaf or node reached from subtable ``k``, skipping untested inputs."""
        while ids[depth][k] >= 2 and ids[depth + 1][2 * k] == ids[depth + 1][2 * k + 1]:
            depth, k = depth + 1, 2 * k
        if ids[depth][k] < 2:
            return ids[depth][k]
        key = (depth, ids[depth][k])
        if key not in reps:
            reps[key] = k
            levels[depth].append(key)
        return key

    root = resolve(0, 0)
    callers: dict[_Key, int] = {}
    for depth in range(n):
        for key in levels[depth]:  # grows only at deeper levels
            k = reps[key]
            zero, one = resolve(depth + 1, 2 * k), resolve(depth + 1, 2 * k + 1)
            children[key] = zero, one
            for child in (zero, one):
                if not isinstance(child, int):
                    callers[child] = callers.get(child, 0) + 1

    # Bottom-up: a node's body is its arms, a call standing for a shared child.
    shared: set[_Key] = set()
    body: dict[_Key, int] = {}
    saving: list[tuple[int, _Key]] = []
    for depth in range(n - 1, -1, -1):
        for key in levels[depth]:
            arms = [
                (_CALL if child in shared else body[child])
                if not isinstance(child, int)
                else 5 * child
                for child in children[key]
            ]
            zero, one = arms
            body[key] = (8 + zero if zero else 0) + (7 + one if one else 0)
            m = callers.get(key, 0)
            gain = (m - 1) * body[key] - _CALL * m - _BLOCK - _ALLOC
            if m > 1 and gain > 0:
                saving.append((gain, key))
                shared.add(key)
    # Names run out at 53; keep the largest savings.
    room = max(0, _NAMES - n - 1)
    shared = {key for _, key in sorted(saving, key=lambda s: (-s[0], s[1]))[:room]}

    names = [short_name(i, _LETTERS) for i in range(n + 1 + len(shared))]
    answer = names[n]
    flags = dict(zip(sorted(shared), names[n + 1 :], strict=True))
    inline: dict[_Key, str] = {}

    def arm(ref: _Ref) -> str:
        if isinstance(ref, int):
            return f"{answer}{mark}=1;" if ref else ""
        if ref in flags:
            return f"{flags[ref]}+=1;"
        return text(ref)

    def text(key: _Key) -> str:
        """The statements for one node: an ``if`` per nonempty arm."""
        if key not in inline:
            zero, one = (arm(child) for child in children[key])
            var = names[key[0]]
            inline[key] = (f"if({var}){{{one}}}" if one else "") + (
                f"if!({var}){{{zero}}}" if zero else ""
            )
        return inline[key]

    tested = {key[0] for key in children}
    reads = "".join(
        f"read->{names[i]};" + (f"{names[i]}-={_ASCII_ZERO};" if i in tested else "")
        for i in range(n)
    )
    blocks = "".join(f"if({flags[key]}){{{text(key)}}}" for key in flags)
    head = f"#basicfuck t={len(names)} r=0~255 o=wrap\n#allocate {','.join(names)}\n"
    return f"{head}{reads}{arm(root)}{blocks}{answer}+={base};write<-{answer};"


LANGUAGE = Language(
    "Basicfuck",
    "basicfuck",
    category="tape_based",
    boolean=basicfuck,
    contract=BooleanContract(input_shape="char_stream"),
    no_wrap="the directive and #allocate are lines one and two",
    empty_program="missing directive or #allocate",
    eof="`read` at EOF raises: the page's cat covers three EOF conventions",
    example=Example(expected="0"),
)
