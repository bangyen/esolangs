"""Check a recursively confined cell-preserving prefix certificate."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from balanced_certificate import Matrix, _product, _sum
from divergence_certificate import _atom_image, _check_image, _validate
from divergence_certificate import _next as _base
from grammar_certificate import check_grammar

type State = tuple[bool, int, int, int, int, int, int]
type Loop = tuple[bool, bool, int, bool]


def _loops() -> list[Loop]:
    result = [(False, False, 3, True)]
    for reads in range(2):
        for printing in range(2):
            for confined in range(4):
                if not reads or not confined:
                    result.append((bool(reads), bool(printing), confined, False))
    return result


def _next(state: State, column: int) -> State | None:
    read, tail, first, count, right, left, prefix = state
    loop = _loops()[column - 6] if column >= 6 else None
    base_column = 6 + int(loop[1]) + 2 * int(loop[0]) if loop else column
    base = _base((read, tail, first, count), base_column)
    if base is None:
        return None
    phases = []
    for phase, direction, mask in ((right, 1, 1), (left, -1, 2)):
        if loop:
            allowed = (
                bool(loop[2] & mask) if phase == 0 else phase == 1 and loop[2] == 3
            )
            phase = phase if allowed else 2
        elif column == 1:
            phase = 2
        elif column in (4, 5) and phase != 2:
            phase += direction * (1 if column == 5 else -1)
            if not 0 <= phase <= 1:
                phase = 2
        phases.append(phase)
    if prefix < 5:
        height = prefix if prefix <= 2 else 2 - prefix
        if loop:
            if height == 0:
                prefix = 6 if loop[3] else 5
            else:
                required = 1 if height > 0 else 2
                allowed = bool(loop[2] & required) if abs(height) == 1 else loop[2] == 3
                if not allowed:
                    prefix = 5
        elif column == 1 or (height == 0 and column in (2, 3)):
            prefix = 5
        elif column in (4, 5):
            height += 1 if column == 5 else -1
            prefix = (height if height >= 0 else 2 - height) if abs(height) <= 2 else 5
    return (*base, phases[0], phases[1], prefix)


def _states() -> list[State]:
    pending: list[State] = [(False, 0, 0, 0, 0, 0, 0)]
    reached = set(pending)
    for state in pending:
        for column in range(6 + len(_loops())):
            target = _next(state, column)
            if target is not None and target not in reached:
                reached.add(target)
                pending.append(target)
    return sorted(reached)


def check_certificate(
    rows: list[list[int]],
    classes: list[State],
    matrices: list[Matrix],
    scale: int,
    bound: tuple[int, int],
) -> None:
    """Check confinement types, forbidden prefixes and all exact inequalities."""
    numerator, _ = _validate(rows, matrices, scale, bound)
    if classes != _states() or len(matrices) != len(classes):
        raise ValueError("invalid preserving atom classes")
    kinds = _loops()
    bodies: list[Matrix] = [[{} for _ in rows] for _ in kinds]
    for state, matrix in zip(classes, matrices, strict=True):
        read, tail, first, count, right, left, prefix = state
        if prefix == 6 or (first, count) == (2, 1) or (tail == 3 and not read):
            continue
        kind = (read, first == 1, int(right == 0) + 2 * int(left == 0), count == 0)
        position = kinds.index(kind)
        bodies[position] = _sum(bodies[position], matrix)
    transitions = [
        [{row[column]: 1} if row[column] >= 0 else {} for row in rows]
        for column in range(8)
    ]
    atoms = transitions[:6] + [
        _product(_product(transitions[6], body), transitions[7]) for body in bodies
    ]
    index = {state: position for position, state in enumerate(classes)}
    edges = [
        [
            index[target] if (target := _next(state, column)) is not None else -1
            for column in range(len(atoms))
        ]
        for state in classes
    ]
    _check_image(
        _atom_image(rows, matrices, atoms, edges, scale, bound),
        matrices,
        numerator**2 * scale,
    )


def main() -> None:
    """Verify the exported positive system and factor-DFA language."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", type=Path)
    data = json.loads(parser.parse_args().certificate.read_text())
    matrices = [
        [{int(end): value for end, value in row.items()} for row in matrix]
        for matrix in data["matrices"]
    ]
    check_certificate(
        data["rows"],
        [tuple(state) for state in data["classes"]],
        matrices,
        data["scale"],
        tuple(data["bound"]),
    )
    pairs = check_grammar(data["rows"], ".,-+<>[]", data["factors"], [])
    print(
        f"exact preserving-prefix supersolution {data['bound']}; "
        f"grammar verified at {pairs} pairs"
    )


if __name__ == "__main__":
    main()
