"""Boolean generator for sophie."""

from itertools import chain, count

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _residual_ids,
    _validate_truth_table,
)

__all__ = ["sophie", "sophie_labels"]


def sophie(truth_table: str) -> str:
    """Build a Sophie program computing the given truth table.

    ``truth_table`` has ``2**n`` entries, most significant input first.

    Sophie reads a character with ``;`` and branches on the accumulator with
    ``@0{then}{else}`` -- the else block runs flat after a failed check, so
    consecutive conditionals must use the block form. A leaf loads ``#0`` or
    ``#1`` for one final ``,`` to print; a last-level ``01`` is its read.

    :func:`_sophie_hybrid` nests unshared residual states like a tree and
    labels only states reached from multiple parents, merging equal ones.

    **Reordering the inputs is not available here**, unlike most tree
    generators: ``;`` and ``:`` *assign* to the accumulator, ``#`` loads only
    a literal, and nothing else writes it, so a bit can only be branched on
    before the next read and the test order is the stream order.  The merge
    collects the saving a reorder would have found.
    """
    _validate_truth_table(truth_table)
    return _sophie_hybrid(truth_table)


#: Accumulator values a Sophie label may not take: a read leaves ``0`` or
#: ``1`` (48/49), so a block labelled either would fire on an ordinary bit.
_SOPHIE_RESERVED = frozenset({_ASCII_ZERO, _ASCII_ONE})

#: Values spelled as one character, ``#c``/``@c{``: not ``$``, brackets
#: (``_partners`` ignores loads), ``#`` (``matches`` misreads ``@#{``) or space.
_SOPHIE_CHARACTERS = frozenset(range(33, 127)) - {ord(c) for c in "#$[]{}"}


def _sophie_literal(value: int) -> str:
    """Spell ``value`` after ``#`` or ``@``: its character, else ``$`` digits."""
    return chr(value) if value in _SOPHIE_CHARACTERS else f"${value}"


def sophie_labels(retained: list[list[int]]) -> list[dict[int, int]]:
    """Return one label per retained state, unique across all levels.

    This used to draw from two bands by level parity -- ``((1, 20), (21,
    40))`` -- on the reasoning that a fired block leaves the accumulator
    holding a *next*-level label, which no remaining test in the chain can
    match.  The reasoning holds for consecutive levels and that is not the
    relation that matters.  Unshared states are *inlined*, so one top-level
    block contains jumps originating at many different depths, and two
    levels of the same parity are both jump targets from inside it.  Level 2
    and level 4 then both got label ``1``, and since level 2 is emitted
    first, a jump meant for level 4 fired level 2 on the way past -- reading
    inputs the caller never supplied.

    The smallest table that does it is the five-input
    ``00000000000000010000000100000100``, whose program carries two ``@$1``
    blocks.  It is shape-dependent rather than size-dependent, so it hides
    from parity and dense tables and shows up on one-hot: over 500 random
    tables per arity, 1.6% collide at n=5, 11.2% at n=6, 35.0% at n=7 and
    87.6% at n=8, while all 65536 tables at n <= 4 are clean.

    Single-character values come first, then numbers from 1 that are not.
    """
    single = sorted(_SOPHIE_CHARACTERS - _SOPHIE_RESERVED)
    rest = (v for v in count(1) if v not in _SOPHIE_CHARACTERS)
    values = chain(single, rest)
    return [{state: next(values) for state in states} for states in retained]


def _sophie_hybrid(truth_table: str) -> str:
    """Emit a Sophie tree that labels only shared residual states.

    Canonical child pairs name states in O(T) RAM work without copying
    the subtables at every depth. First-occurrence order preserves labels.
    """
    n = _validate_truth_table(truth_table)
    levels, children, constants = _residual_ids(truth_table, n)
    references: list[dict[int, int]] = [{} for _ in levels]
    for k in range(n - 1):
        for state in levels[k]:
            if constants[state] is not None:
                continue
            for child in set(children[state]):
                references[k + 1][child] = references[k + 1].get(child, 0) + 1

    retained = [
        [
            state
            for state in states
            if k == 0
            or (
                constants[state] is None
                and references[k].get(state, 0) > 1
                and not (k == n - 1 and children[state] == (0, 1))
            )
        ]
        for k, states in enumerate(levels)
    ]
    labels = sophie_labels(retained)

    out: list[str] = []

    # A leaf runs on to the final ``,``: 48/49 fire no ``@L`` on the way.
    def body(k: int, state: int) -> None:
        if constants[state] is not None:
            out.append(";" * (n - k) + f"#{constants[state]}")
            return
        zero, one = children[state]
        if k + 1 == n:
            out.append(";" if one == 1 else ";@0{#1}{#0}")
            return

        def next_body(child: int) -> None:
            if child in labels[k + 1]:
                out.append("#" + _sophie_literal(labels[k + 1][child]))
            else:
                body(k + 1, child)

        if zero == one:
            out.append(";")
            next_body(zero)
        else:
            out.append(";@0{")
            next_body(zero)
            out.append("}{")
            next_body(one)
            out.append("}")

    for k, states in enumerate(retained):
        for state in states:
            if k:
                out.append("@" + _sophie_literal(labels[k][state]) + "{")
            body(k, state)
            if k:
                out.append("}")
    out.append(",")
    return "".join(out)
