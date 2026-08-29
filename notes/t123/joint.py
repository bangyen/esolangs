r"""Test whether termination and input-dependent re-execution can coexist.

Separately, each is easy: a narrower sweep found 74 of 90 layouts with an
input-dependent pass count, and plain affine templates halt on every row.
No sweep here has found one layout with both.

This measures the joint condition over a wider family and reports the
breakdown, so the obstruction is characterised rather than guessed: for
each layout, whether every row halts, whether the pass counts differ, and
how often the two coincide.
"""

import itertools
from collections import Counter

from reexec import trace


def classify(template, limit=600):
    """Return (all_halt, counts_differ) or None if a row reads."""
    counts = []
    halts = []
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        _, events, _, _, halted = trace(template, bits, limit=limit)
        if any(kind == "read" for kind, _ in events):
            return None
        counts.append(sum(1 for kind, _ in events if kind == "back"))
        halts.append(halted)
    return all(halts), len(set(counts)) > 1


def main():
    """Cross-tabulate termination against input-dependent re-execution."""
    dips = ["1", "11", "121", "1121", "12"]
    rights = ["2", "22", "222", "2222"]
    bodies = ["", "1", "2", "11", "12", "21", "111", "121", "112", "211",
              "1111", "1211", "1121"]
    closes = ["", "1", "2", "11", "12", "21"]
    tally = Counter()
    both = []
    for dip, right, body, close in itertools.product(
            dips, rights, bodies, closes):
        tpl = f"{dip}3{right}{{X0}}{body}{{X1}}{close}3"
        got = classify(tpl)
        if got is None:
            tally["reads"] += 1
            continue
        halts, differs = got
        tally[f"halts={halts} differs={differs}"] += 1
        if halts and differs:
            both.append(tpl)
    total = sum(tally.values())
    print(f"{total} layouts classified\n")
    for label, count in tally.most_common():
        print(f"  {count:5} ({100 * count / total:5.1f}%)  {label}")
    print(f"\nlayouts with both properties: {len(both)}")
    for tpl in both[:10]:
        print(f"  {tpl!r}")


if __name__ == "__main__":
    main()
