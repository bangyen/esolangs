r"""Combine the two routes and count the tables 123 actually reaches.

Two constructions, each with its own ceiling:

* **printing** (`affine_all.py`) builds the eight *affine* tables, since
  flips are XOR and a straight-line program computes
  ``c XOR (subset of inputs)``;
* **termination** (`whichrows.py`) reaches *monotone* tables, since a set
  bit can only add a pass to the guard and the looping set is therefore
  upward-closed.

This states both sets explicitly and reports the union, so the count in
``docs/walls.md`` is derived rather than asserted.
"""

from termconv import NAMES

AFFINE = ["0000", "1111", "0011", "1100", "0101", "1010", "0110", "1001"]
TERMINATION = ["0000", "1111", "0111", "0101", "0011"]


def main():
    """Print each route's reach and their union."""
    aff = set(AFFINE)
    term = set(TERMINATION)
    both = aff | term
    print(f"printing route (affine):     {len(aff)} tables")
    print(f"  {', '.join(NAMES[t] for t in sorted(aff))}")
    print(f"\ntermination route (monotone): {len(term)} tables")
    print(f"  {', '.join(NAMES[t] for t in sorted(term))}")
    print(f"\noverlap: {len(aff & term)} "
          f"({', '.join(NAMES[t] for t in sorted(aff & term))})")
    print(f"union:   {len(both)}/16")
    missing = [t for t in sorted(NAMES) if t not in both]
    print(f"\nnot reached ({len(missing)}): "
          f"{', '.join(NAMES[t] for t in missing)}")


if __name__ == "__main__":
    main()
