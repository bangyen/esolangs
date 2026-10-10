"""Sophie's retired constructions, kept as oracles for its generator."""

# These independent construction oracles deliberately mirror generated programs.
# pylint: disable=duplicate-code

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table


def _residual_levels(truth_table: str, n: int) -> list[list[str]]:
    """Return the distinct residual subtables at each level, in first-seen order."""
    levels = [[truth_table]]
    for k in range(n):
        half = 2 ** (n - k - 1)
        states = (part for s in levels[-1] for part in (s[:half], s[half:]))
        levels.append(list(dict.fromkeys(states)))
    return levels


#: Label bands for the *pure* DAG below, which the shipped generator no
#: longer shares.
#:
#: Two bands by level parity are enough here and were not enough there, and
#: the difference is inlining.  This emits one block per state at every
#: level, in level order, so every jump goes from level k to level k + 1 and
#: the accumulator only ever holds a next-level label while control is
#: passing the current level's blocks -- which draw from the other band.
#: The shipped generator inlines unshared states, so one top-level block
#: carries jumps originating at many depths, two same-parity levels are both
#: targets from inside it, and the earlier one fires first.  See
#: :func:`~esolangs.tools.sophie.sophie_labels`.
_SOPHIE_BANDS = ((1, 20), (21, 40))


def _sophie_tree(truth_table: str) -> str:
    """Emit the nested-branch Sophie program; see :func:`sophie`."""
    n = _validate_truth_table(truth_table)

    def build(path: list[int]) -> str:
        depth = len(path)
        row = 0
        for bit in path:
            row = row * 2 + bit
        # A short path has its unconsumed bits still to come, so it names
        # the start of the run they span rather than a row outright.
        row <<= n - depth
        if depth == n or len(set(truth_table[row : row + 2 ** (n - depth)])) == 1:
            # Sophie reads inside the tree -- a node is ``;`` then its
            # branch -- so a folded leaf still spends the reads it skipped.
            # A program whose input count depended on its table would
            # desync a caller feeding several programs from one stream.
            reads = ";" * (n - depth)
            return f"{reads}#${_ASCII_ZERO + int(truth_table[row])},&"
        return ";" + "@$48{" + build([*path, 0]) + "}" + "{" + build([*path, 1]) + "}"

    return build([])


def _sophie_dag(truth_table: str) -> str:
    """Emit the state-machine Sophie program; see :func:`sophie`."""
    n = _validate_truth_table(truth_table)
    levels = _residual_levels(truth_table, n)

    def label(level: int, state: str) -> int:
        return _SOPHIE_BANDS[level % 2][0] + levels[level].index(state)

    out: list[str] = []
    for k in range(n):
        width = 2 ** (n - k - 1)
        blocks: list[str] = []
        for state in levels[k]:
            zero, one = state[:width], state[width:]
            if k + 1 == n:
                # The children are single characters -- the answers.
                body = (
                    f";@$48{{#${_ASCII_ZERO + int(zero)},&}}"
                    f"{{#${_ASCII_ZERO + int(one)},&}}"
                )
            elif zero == one:
                # Merged children: this bit cannot change the answer, so the
                # read still happens and the label is set unconditionally.
                body = f";#${label(k + 1, zero)}"
            else:
                body = f";@$48{{#${label(k + 1, zero)}}}{{#${label(k + 1, one)}}}"
            blocks.append(body if k == 0 else f"@${label(k, state)}{{{body}}}")
        out.append("".join(blocks))
    return "".join(out)
