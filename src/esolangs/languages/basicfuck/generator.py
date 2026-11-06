"""Basicfuck Boolean program generator: a decision tree over named variables.

Each input is read into its own variable and, if the tree tests it, reduced
from its digit to 0/1 with ``-= 48``.  A node tests ``if(v){..}`` for the
one arm and ``if!(v){..}`` for the zero arm: the variable is not written in
between, so both tests see the same bit and exactly one arm runs.  A node
whose halves agree skips the test, and an empty arm drops its ``if``.  A
repeated subtree is a block ``if(f){..}`` after the tree, entered through a
flag each caller sets (a run follows one path, so a flag is set once).  The
answer cell starts at 0 and each marked leaf adds 1; a closing ``+= 48`` and
``write`` print it.  A table with more ones than zeros builds its
complement's tree instead (marking the zero rows, counting down, closing
with ``+= 49``); ``o=wrap`` makes the -1 come out as 255 and the sum land
on 48 or 49. Parity over essential inputs and its complement add the selected
bytes in the two-value range 48..49: modular addition XORs their low bits.
Ignored inputs are still read. One read cell and an accumulator need no flags.

Size:
    O(T) at most 14T + 16n + 43 chars; parity over m essential inputs uses
    8n+5m+59 chars and n+m+2 commands; n=4 parity: 111 chars,
    n=10 parity: 189 chars, n=10 and: 293 chars.
    Constants: 8n+48 chars,
    n+2 commands, 12+bl(n+2)+bl(n) written bits.

Decisions:
    A subtree is shared only when ``m * body > body + 5m + 9`` for its ``m``
    callers, and at most the 52 - n largest estimated savings get a flag: names
    stay one character.  Blocks follow the tree in depth order, so each
    flag is set before its block is tested.  Sharing never lost to the
    plain tree on 253 tables, n=2..12.
"""

from esolangs.generation.algebraic import affine_form
from esolangs.generation.decision import reduced_diagram
from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    short_name,
)

#: Single-character names: no reserved word is one, and 53 cover every table
#: a string can hold (n + 1 <= 53 up to 2**52 rows).
_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"


def basicfuck(truth_table: str) -> str:
    """Build a Basicfuck program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table == truth_table[0] * len(truth_table):
        return (
            "#basicfuck t=2 r=~\n#allocate a,b\n"
            + "read->a;" * n
            + f"b+={48 + int(truth_table[0])};write<-b;"
        )
    if (form := affine_form(truth_table, n)) is not None:
        bias, coefficients = form
        # With both cells in 48..49, wrapped addition is XOR of their low bits.
        # Initialize explicitly before accumulating; variable addition needs t=3.
        return (
            "#basicfuck t=3 r=48~49 o=wrap\n#allocate a,b\n"
            + f"b+={48 + bias};"
            + "".join(
                "read->a;" + ("b+=a;" if selected else "") for selected in coefficients
            )
            + "write<-b;"
        )
    if truth_table.count("1") <= len(truth_table) // 2:
        return _program(truth_table, n, "+", _ASCII_ZERO)
    flipped = truth_table.translate(str.maketrans("01", "10"))
    return _program(flipped, n, "-", _ASCII_ZERO + 1)


type _Key = tuple[int, int]  # (depth, subtree id): a node that tests an input
type _Ref = _Key | int  # a node, or a constant leaf (0 or 1)

#: One-character name pool for inputs, the answer and flags.
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
    diagram, root_id = reduced_diagram(truth_table, n)
    levels: list[list[_Key]] = [[] for _ in range(n)]
    children: dict[_Key, tuple[_Ref, _Ref]] = {}

    def reference(node: int) -> _Ref:
        return node if node < 2 else (diagram[node].level, node)

    root = reference(root_id)
    if not isinstance(root, int):
        levels[root[0]].append(root)
    placed = {root}
    callers: dict[_Key, int] = {}
    # Flag allocation retains breadth-first, zero-first placement and pricing.
    for depth in range(n):
        for key in levels[depth]:
            node = diagram[key[1]]
            zero, one = reference(node.zero), reference(node.one)
            children[key] = zero, one
            for child in (zero, one):
                if not isinstance(child, int):
                    callers[child] = callers.get(child, 0) + 1
                    if child not in placed:
                        placed.add(child)
                        levels[child[0]].append(child)

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
    # Keep the largest estimated gains within the one-character flag budget.
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
