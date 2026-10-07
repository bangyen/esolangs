"""Count balanced words with unrestricted nonzero-tail divergence removed."""

from collections import defaultdict

# State: any read, last-loop suffix (none/plain/print-first/one sign),
# first atom (empty/print/loop/other), atom count capped at two.
type State = tuple[bool, int, int, int]
type Counts = dict[State, int]
EMPTY: State = (False, 0, 0, 0)


def _append(state: State, atom: str, *, reads: bool) -> State | None:
    read, tail, first, count = state
    if atom == "." and tail == 2:
        return None
    if atom in ("L", "M"):
        tail = 1 if atom == "L" else 2
    elif atom == "s":
        tail = 3 if tail in (1, 2) else 0
    elif atom != ".":
        tail = 0
    if not count:
        first = 1 if atom == "." else 2 if atom in ("L", "M") else 3
    return read or reads, tail, first, min(count + 1, 2)


def typed_counts(limit: int) -> tuple[list[Counts], list[dict[tuple[bool, bool], int]]]:
    """Return sequence and loop-body coefficients; no finite factors are removed."""
    sequences: list[Counts] = [{EMPTY: 1}]
    bodies: list[dict[tuple[bool, bool], int]] = [{(False, False): 1}]
    for size in range(1, limit + 1):
        current: defaultdict[State, int] = defaultdict(int)
        atoms = [(1, ".", False, 1), (1, ",", True, 1)]
        atoms.extend([(1, "s", False, 2), (1, "m", False, 2)])
        for width in range(2, size + 1):
            for (read, printing), multiplicity in bodies[width - 2].items():
                atoms.append((width, "M" if printing else "L", read, multiplicity))
        for width, atom, read, multiplicity in atoms:
            for state, count in sequences[size - width].items():
                target = _append(state, atom, reads=read)
                if target is not None:
                    current[target] += count * multiplicity
        sequences.append(dict(current))
        body: defaultdict[tuple[bool, bool], int] = defaultdict(int)
        for (read, tail, first, count), value in current.items():
            if first == 2 and count == 1:
                continue
            if not read and tail == 3:
                continue
            body[read, first == 1] += value
        bodies.append(dict(body))
    return sequences, bodies
