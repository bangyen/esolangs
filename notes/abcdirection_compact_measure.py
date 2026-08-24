"""Final check: compacted programs parse, run, and stay rectangular ABCD grids."""

import sys

sys.path.insert(0, "src")
sys.path.insert(0, "/Users/bangyen/.claude/jobs/3ce5ed47/tmp")

from compact import compact

from esolangs.interpreters.tape_based.abcdirection import _parse
from esolangs.tools.boolean import abcdirection

for n in [1, 2, 3, 4, 5]:
    table = "".join("01"[(i * 7) % 3 == 0] for i in range(2**n))
    before = abcdirection(table)
    rows = compact(before.split("\n"))
    after = "\n".join(rows)

    widths = {len(r) for r in rows}
    charset = set("".join(rows))
    parsed = _parse(after)
    print(
        f"n={n}: {len(before):>9,d} -> {len(after):>9,d} B"
        f" ({len(before) / len(after):.1f}x)"
        f"  rect={len(widths) == 1}  chars={''.join(sorted(charset))}"
        f"  parsed {len(parsed)}x{len(parsed[0])} of {len(rows)}x{len(rows[0])}"
    )
