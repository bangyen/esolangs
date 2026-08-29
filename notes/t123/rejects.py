r"""Measure how much of the two-channel space dies, and to what.

``livecheck.py`` confirms the two-channel guards are live -- bodies execute
and rows take different paths -- so ``twochannel.py``'s zero is a genuine
search result rather than the dead-code artifact that spoiled the earlier
sweeps.

But the same trace shows rows hitting the read position, which disqualifies
a candidate outright.  This counts the rejection reasons, so the coverage
the sweep actually achieved is measured rather than assumed: a sweep whose
candidates nearly all die to reads has explored far less than its raw count
suggests.
"""

import itertools
from collections import Counter

from tmpl import run
from twochannel import instantiate_mixed, lengths_ok


def outcome(template, limit=4000):
    """Classify a template by how its four rows behave."""
    kinds = set()
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        out, status = run(instantiate_mixed(template, bits), limit)
        if status == "read":
            kinds.add("read")
        elif status == "loop":
            kinds.add("loop")
        elif len(out) != 1:
            kinds.add(f"printed {len(out)}")
        elif out not in "01":
            kinds.add("non-digit")
        else:
            kinds.add("ok")
    if kinds == {"ok"}:
        return "all rows clean"
    return " + ".join(sorted(kinds))


def main():
    """Count rejection reasons across the two-channel sweep."""
    tally = Counter()
    prefixes = ["1" * k for k in range(1, 5)]
    bodies = ["", "1", "2", "12", "21", "121", "212", "112", "221"]
    tails = ["1" * k + "2" + "1" for k in range(0, 13)]
    for pre, gap, body, tail in itertools.product(
            prefixes, ["", "1", "2", "12", "21"], bodies, tails):
        tpl = f"{pre}3{{X0}}{body}3{gap}{{X1}}{tail}"
        if not lengths_ok(tpl):
            continue
        tally[outcome(tpl)] += 1
    total = sum(tally.values())
    print(f"{total} templates classified\n")
    for kind, count in tally.most_common(12):
        print(f"  {count:5} ({100 * count / total:5.1f}%)  {kind}")


if __name__ == "__main__":
    main()
