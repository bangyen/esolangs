"""Rebuild the balanced-body certificate for the bi-infinite tape."""

from functools import lru_cache

from tests.proofs._brainfuck_count import automaton, local_patterns, minimize

BOUND = (691, 100)
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


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    from scripts.balanced_certificate import check_certificate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    rows, nonempty, bodies = certificate()
    check_certificate(rows, nonempty, bodies, SCALE, BOUND)
    if args.export:
        args.export.write_text(
            json.dumps(
                {
                    "rows": rows,
                    "nonempty": nonempty,
                    "bodies": bodies,
                    "scale": SCALE,
                    "bound": BOUND,
                    "factors": sorted(patterns()),
                }
            )
        )
    print(f"{len(rows)} states: exact balanced upper certificate {BOUND[0]}/{BOUND[1]}")
