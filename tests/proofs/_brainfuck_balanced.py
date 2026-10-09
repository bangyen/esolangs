"""Rebuild the balanced-body certificate for the bi-infinite tape."""

from functools import lru_cache

from tests.proofs._brainfuck_count import automaton, local_patterns, minimize

BOUND = (691, 100)
ROTATION_BOUND = (69, 10)
SCALE = 10**6
type Matrix = list[dict[int, int]]


def patterns() -> set[str]:
    """Return sound local factors through length six and their left mirrors."""
    factors = {word for word in local_patterns() if len(word) <= 6}
    mirror = str.maketrans("<>", "><")
    return factors | {word.translate(mirror) for word in factors} | {"<>"}


def _image(
    rows: list[list[int]], nonempty: Matrix, bodies: Matrix
) -> tuple[Matrix, Matrix]:
    numerator, denominator = BOUND
    divisor = numerator**2 * SCALE
    next_nonempty, next_bodies = [], []
    for state, row in enumerate(rows):
        atoms: dict[int, int] = {}
        for target in row[:6]:
            if target < 0:
                continue
            atoms[target] = atoms.get(target, 0) + SCALE
            for end, value in nonempty[target].items():
                atoms[end] = atoms.get(end, 0) + value
        loops: dict[int, int] = {}
        if row[6] >= 0:
            for middle, value in bodies[row[6]].items():
                end = rows[middle][7]
                if end >= 0:
                    loops[end] = loops.get(end, 0) + value
        common = {
            end: numerator * denominator * SCALE * value for end, value in atoms.items()
        }
        for middle, left in loops.items():
            for end, right in nonempty[middle].items():
                common[end] = common.get(end, 0) + denominator**2 * left * right
        sequence = dict(common)
        for end, value in loops.items():
            sequence[end] = sequence.get(end, 0) + denominator**2 * SCALE * value
        common[state] = common.get(state, 0) + numerator**2 * SCALE**2
        next_nonempty.append(
            {end: (value + divisor - 1) // divisor for end, value in sequence.items()}
        )
        next_bodies.append(
            {end: (value + divisor - 1) // divisor for end, value in common.items()}
        )
    return next_nonempty, next_bodies


@lru_cache(maxsize=1)
def certificate() -> tuple[list[list[int]], Matrix, Matrix]:
    """Return a rebuilt DFA and rational supersolution; abort at a construction cap."""
    rows = minimize(automaton(patterns(), []))
    if len(rows) > 256:
        raise RuntimeError("balanced certificate state budget exceeded")
    nonempty: Matrix = [{} for _ in rows]
    bodies: Matrix = [{state: SCALE} for state in range(len(rows))]
    for _ in range(1500):
        new_nonempty, new_bodies = _image(rows, nonempty, bodies)
        if new_nonempty == nonempty and new_bodies == bodies:
            return rows, nonempty, bodies
        if any(
            value > 100 * SCALE
            for matrix in (new_nonempty, new_bodies)
            for row in matrix
            for value in row.values()
        ):
            raise RuntimeError("balanced certificate value budget exceeded")
        nonempty, bodies = new_nonempty, new_bodies
    raise RuntimeError("balanced certificate iteration budget exceeded")


def _rotation_image(
    rows: list[list[int]], nonempty: Matrix, nonprint: Matrix, bodies: Matrix
) -> tuple[Matrix, Matrix, Matrix]:
    numerator, denominator = ROTATION_BOUND
    divisor = numerator**3 * SCALE
    next_nonempty: Matrix = []
    next_nonprint: Matrix = []
    next_bodies: Matrix = []
    for state, row in enumerate(rows):
        atoms: dict[int, int] = {}
        other: dict[int, int] = {}
        for column, target in enumerate(row[:6]):
            if target < 0:
                continue
            atoms[target] = atoms.get(target, 0) + SCALE
            if column:
                other[target] = other.get(target, 0) + SCALE
            for end, value in nonempty[target].items():
                atoms[end] = atoms.get(end, 0) + value
                if column:
                    other[end] = other.get(end, 0) + value
        loops: dict[int, int] = {}
        print_loops: dict[int, int] = {}
        if row[6] >= 0:
            for middle, value in bodies[row[6]].items():
                end = rows[middle][7]
                if end >= 0:
                    loops[end] = loops.get(end, 0) + value
            printing = rows[row[6]][0]
            if printing >= 0:
                sequences = dict(nonempty[printing])
                sequences[printing] = sequences.get(printing, 0) + SCALE
                for middle, value in sequences.items():
                    end = rows[middle][7]
                    if end >= 0:
                        print_loops[end] = print_loops.get(end, 0) + value
        common: dict[int, int] = {}
        for matrix, suffix, multiplier in (
            (loops, nonempty, denominator**2 * numerator),
            (print_loops, nonprint, denominator**3),
        ):
            for middle, left in matrix.items():
                for end, right in suffix[middle].items():
                    common[end] = common.get(end, 0) + multiplier * left * right
        tails = {
            end: denominator**2 * numerator * SCALE * value
            for end, value in loops.items()
        }
        for end, value in print_loops.items():
            tails[end] = tails.get(end, 0) + denominator**3 * SCALE * value
        sequence, tail, body = dict(common), dict(common), dict(common)
        atom_scale = numerator**2 * denominator * SCALE
        for end, value in atoms.items():
            sequence[end] = sequence.get(end, 0) + atom_scale * value
        for end, value in other.items():
            tail[end] = tail.get(end, 0) + atom_scale * value
            body[end] = body.get(end, 0) + atom_scale * value
        for end, value in tails.items():
            sequence[end] = sequence.get(end, 0) + value
            tail[end] = tail.get(end, 0) + value
        body[state] = body.get(state, 0) + numerator**3 * SCALE**2
        for image, result in (
            (sequence, next_nonempty),
            (tail, next_nonprint),
            (body, next_bodies),
        ):
            result.append(
                {end: (value + divisor - 1) // divisor for end, value in image.items()}
            )
    return next_nonempty, next_nonprint, next_bodies


@lru_cache(maxsize=1)
def rotation_certificate() -> tuple[list[list[int]], Matrix, Matrix, Matrix]:
    """Return a capped supersolution excluding print rotation at every depth."""
    rows = minimize(automaton(patterns(), []))
    if len(rows) > 256:
        raise RuntimeError("rotation certificate state budget exceeded")
    nonempty: Matrix = [{} for _ in rows]
    nonprint: Matrix = [{} for _ in rows]
    bodies: Matrix = [{state: SCALE} for state in range(len(rows))]
    for _ in range(1500):
        image = _rotation_image(rows, nonempty, nonprint, bodies)
        if image == (nonempty, nonprint, bodies):
            return rows, nonempty, nonprint, bodies
        if any(
            value > 100 * SCALE
            for matrix in image
            for row in matrix
            for value in row.values()
        ):
            raise RuntimeError("rotation certificate value budget exceeded")
        nonempty, nonprint, bodies = image
    raise RuntimeError("rotation certificate iteration budget exceeded")


if __name__ == "__main__":
    import argparse
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from balanced_certificate import check_certificate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--rotation", action="store_true")
    args = parser.parse_args()
    extra = {}
    if args.rotation:
        rows, nonempty, nonprint, bodies = rotation_certificate()
        bound = ROTATION_BOUND
        extra = {"nonprint": nonprint}
        check_certificate(rows, nonempty, bodies, SCALE, bound, nonprint=nonprint)
    else:
        rows, nonempty, bodies = certificate()
        bound = BOUND
        check_certificate(rows, nonempty, bodies, SCALE, bound)
    if args.export:
        args.export.write_text(
            json.dumps(
                {
                    "rows": rows,
                    "nonempty": nonempty,
                    "bodies": bodies,
                    "scale": SCALE,
                    "bound": bound,
                    "factors": sorted(patterns()),
                    **extra,
                }
            )
        )
    print(f"{len(rows)} states: exact balanced upper certificate {bound[0]}/{bound[1]}")
