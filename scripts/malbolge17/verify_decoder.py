"""Verify a shared-state group decoder for the seventeen-input Malbolge design.

A decoder file describes ``S`` states shared by ``NR`` rows of a group of
``K`` cells, each cell read as one of seven meanings.  Row ``s`` starts at
``start[s]``; state ``q`` reads cell ``pos[q][s]`` and maps the meaning to
``-1`` (print 0), ``-2`` (print 1) or a later state.  The decoder is valid when
every one of the ``2**NR`` answer vectors is realised by some cell contents,
and, with ``--no-repeat``, no row ever reads the same cell twice (a read
rewrites its cell).  Usage: ``verify_decoder.py FILE [--no-repeat]``.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

_MEANINGS = 7


def _load(
    path: str,
) -> tuple[int, int, int, list[int], list[list[int]], list[list[int]]]:
    lines = [line for line in Path(path).read_text().splitlines() if line.strip()]
    head = lines[0].split()
    rows, cells, states = int(head[1]), int(head[3]), int(head[5])
    start = [int(x) for x in lines[1].split()[1:]]
    delta: list[list[int]] = []
    pos: list[list[int]] = []
    for q in range(states):
        left, right = lines[2 + q].split("| pos")
        delta.append([int(x) for x in left.split("|")[1].split()])
        pos.append([int(x) for x in right.split()])
    return rows, cells, states, start, delta, pos


def verify(path: str, *, no_repeat: bool) -> bool:
    """Return whether the decoder in ``path`` realises every answer vector."""
    rows, cells, states, start, delta, pos = _load(path)
    if any(t >= 0 and t <= q for q in range(states) for t in delta[q]):
        raise ValueError("transitions must go to a later state")
    seen: set[int] = set()
    repeats = 0
    for values in itertools.product(range(_MEANINGS), repeat=cells):
        answer = 0
        for s in range(rows):
            q, read = start[s], []
            while True:
                cell = pos[q][s]
                read.append(cell)
                t = delta[q][values[cell]]
                if t < 0:
                    answer |= (t == -2) << s
                    break
                q = t
            repeats += len(read) != len(set(read))
        seen.add(answer)
    ok = len(seen) == 1 << rows and not (no_repeat and repeats)
    print(
        f"{path}: {len(seen)}/{1 << rows} vectors, {repeats} repeat-read paths",
        "OK" if ok else "FAIL",
    )
    return ok


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--no-repeat"]
    sys.exit(
        0 if all(verify(a, no_repeat="--no-repeat" in sys.argv) for a in args) else 1
    )
