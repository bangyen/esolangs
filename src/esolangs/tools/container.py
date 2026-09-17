"""Boolean-function generator for Container."""

from esolangs.tools.forbin import (
    _forbin_name,
)
from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table


def _container_tree(truth_table: str) -> str:
    """Build a Container program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Container is a synchronous rule system: every tick each container's value
    becomes ``max(old + sum of deltas of satisfied ``X>=Y``/``X<=Y`` rules,
    0)``, the empty-named container reads a line of input into ``IN`` when it
    turns on, ``PRINT`` outputs ``OUT`` when it turns on, and ``EXIT`` halts
    when its value changes.  There is no per-tick conditional, so the
    generator timestamps everything with the tick counter ``T``:

    * The empty container pulses on even ticks ``0..2(n-1)`` (``+1 T>=2k``,
      ``-2 T>=2k+1``, ``+1 T>=2k+2``), reading one bit per pulse.
    * For each bit ``k``, two armed gates (65, dipping to 49; and 47, dipping
      to 48) make their ``IN`` comparisons hold for
      exactly the tick the bit is in ``IN``, testing bit ``k`` once.
    * A prefix survivor creates its two children while bit ``k`` is active;
      the mismatching child is cancelled in that same tick.  The parent then
      expires, so each tree edge costs constant work instead of retesting the
      whole prefix at every leaf.
    * At tick ``2n`` an output gate dips to 1, so the surviving row adds the
      table entry of the surviving row to ``OUT``; ``PRINT`` fires and
      ``EXIT`` halts.

    The last block costs one line per row the table sends to 1, so a dense
    table is summed from its **zero** rows instead: ``OUT`` starts at 49 and
    each surviving zero row subtracts one, printing ``49 - S``.  The clamp at
    zero never bites, since the value stays at 48 or 49.  Worth up to 12.7%
    at ``n == 4`` (1356 characters down to 1184 for fifteen ones of sixteen);
    the per-row survivor blocks above are fixed and unaffected.
    """
    n = _validate_truth_table(truth_table)
    ones = truth_table.count("1")
    invert = ones > 2**n - ones
    wanted = "0" if invert else "1"

    # Every generated container has a unique name, but their reference counts
    # differ sharply.  Assign shortest alphabetic names by actual frequency.
    uses: dict[tuple[str, int, int], int] = {("root", 0, 0): 6}
    for bit in range(n):
        uses[("low", bit, 0)] = 1 + 2**bit
        uses[("high", bit, 0)] = 1 + 2**bit
    for depth in range(1, n + 1):
        for prefix in range(2**depth):
            uses[("node", depth, prefix)] = (
                6 if depth < n else 2 + (truth_table[prefix] == wanted)
            )
    uses[("output", 0, 0)] = 1 + truth_table.count(wanted)

    reserved = {"EXIT", "IN", "OUT", "PRINT", "T"}
    identifiers = (_forbin_name(i) for i in range(len(uses) + len(reserved)))
    ordered = sorted(uses, key=lambda key: (-uses[key], key))
    names: dict[tuple[str, int, int], str] = {}
    for key in ordered:
        name = next(identifiers)
        while name in reserved:
            name = next(identifiers)
        names[key] = name

    root = names[("root", 0, 0)]
    output_gate = names[("output", 0, 0)]

    lines = ["T:", "+1 T>=T"]
    lines.append(":")  # the empty-named container reads input
    lines.append("+1 T>=0")
    lines.append("-2 T>=1")
    for k in range(1, n):
        lines.append(f"+2 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
    lines.append(f"+1 T>={2 * n}")
    lines.append("IN=50:")  # a value no real byte matches
    for k in range(n):
        low = names[("low", k, 0)]
        high = names[("high", k, 0)]
        lines.append(f"{low}=65:")
        lines.append(f"-16 T>={2 * k}")
        lines.append(f"+32 T>={2 * k + 1}")
        lines.append(f"-16 T>={2 * k + 2}")
        lines.append(f"{high}=47:")
        lines.append(f"+1 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
        lines.append(f"+1 T>={2 * k + 2}")
    lines.append(f"{root}=2:")
    lines.append(f"-1 {root}>=1")
    for depth in range(1, n + 1):
        bit = depth - 1
        for prefix in range(2**depth):
            parent = root if depth == 1 else names[("node", depth - 1, prefix >> 1)]
            child = names[("node", depth, prefix)]
            lines.append(f"{child}:")
            # A node is born at 2, decays to 1, then pulses its children.
            # The paired parent rules therefore fire only at exactly 1.
            lines.append(f"+2 {parent}>=1")
            lines.append(f"-2 {parent}>=2")
            gate = names[("high" if prefix & 1 else "low", bit, 0)]
            mismatch = f"IN<={gate}" if prefix & 1 else f"IN>={gate}"
            lines.append(f"-2 {mismatch}")
            lines.append(f"-1 {child}>=1")
    lines.append(f"{output_gate}=2:")
    lines.append(f"-1 T>={2 * n - 1}")
    lines.append(f"+1 T>={2 * n}")
    # OUT is 48 plus one ``+1`` per row the table sends to 1, so a dense
    # table pays for nearly every row.  Evaluating the *zero* rows costs one
    # line each and starts from 49, subtracting: ``49 - S`` is the
    # complement, and since ``S`` is 0 or 1 the value stays at 48 or 49, so
    # the container's clamp at zero never bites.  Whichever row-set is
    # smaller wins; ties keep the plain form.
    lines.append("OUT:")
    lines.append(f"+{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n}")
    lines.append(f"-{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n + 1}")
    delta = "-1" if invert else "+1"
    for row in range(2**n):
        if truth_table[row] == wanted:
            lines.append(f"{delta} {names[('node', n, row)]}>={output_gate}")
    lines.append("PRINT:")
    lines.append(f"+1 T>={2 * n}")
    lines.append("EXIT=1:")
    lines.append(f"-1 T>={2 * n + 1}")
    return "\n".join(lines)


def _container_packed(truth_table: str) -> str:
    """Build an O(T)-size Container program for the given truth table.

    The table is one decimal integer whose digits, least significant first,
    are its rows.  Two banks repeatedly divide it by ten: one loses ten per
    tick while the other gains one.  After the input-built row counter has
    requested enough divisions, the remaining digit is the answer.  The two
    division networks are fixed; only the table literal and the binary input
    weights grow, totalling O(T) source and construction work.
    """
    n = _validate_truth_table(truth_table)
    lines = ["T:", "+1 T>=T", ":", "+1 T>=0", "-2 T>=1"]
    for k in range(1, n):
        lines.extend((f"+2 T>={2 * k}", f"-2 T>={2 * k + 1}"))
    lines.append(f"+1 T>={2 * n}")
    lines.append("IN=50:")

    # Lk equals 49 for exactly the tick after input k was read, and 65 at
    # every other useful tick.  Thus IN>=Lk adds its weight exactly for '1'.
    for k in range(n):
        lines.extend(
            (
                f"L{k}=65:",
                f"-16 T>={2 * k}",
                f"+32 T>={2 * k + 1}",
                f"-16 T>={2 * k + 2}",
            )
        )

    # One division exposes row zero as the units digit; the binary input
    # index adds the number of further divisions.
    lines.append("COUNT=1:")
    for k in range(n):
        lines.append(f"+{2 ** (n - 1 - k)} IN>=L{k}")
    lines.extend(("-1 NA>=1", "-1 NB>=1"))

    # Reversing the spelling, rather than converting bases, puts row zero in
    # the units place in one linear string pass.  Leading zeroes may vanish
    # in the interpreter's integer parse; they denote zero high rows anyway.
    packed = truth_table[::-1].lstrip("0") or "0"
    lines.extend(
        (
            f"A={packed}:",
            "-10 WA>=1",
            "+1 WB>=1",
            "-1 NB>=1",
            "B:",
            "+1 WA>=1",
            "-10 WB>=1",
            "-1 NA>=1",
            "START:",
            f"+1 T>={2 * n}",
            f"-2 T>={2 * n + 1}",
            f"+1 T>={2 * n + 2}",
            # NA/NB are one-tick, positive-count continuations.  Subtracting
            # on COUNT<=0 cancels the event in the same synchronous update.
            "NA:",
            "+1 START>=1",
            "+1 DB>=1",
            "-1 COUNT<=0",
            "-1 NA>=1",
            "NB:",
            "+1 DA>=1",
            "-1 COUNT<=0",
            "-1 NB>=1",
            "SA:",
            "+1 DA>=1",
            "-1 COUNT>=1",
            "-1 SA>=1",
            "SB:",
            "+1 DB>=1",
            "-1 COUNT>=1",
            "-1 SB>=1",
            "FA:",
            "+1 NA>=1",
            "-1 DA>=1",
            "FB:",
            "+1 NB>=1",
            "-1 DB>=1",
            # A work pulse persists while its active dividend is at least 10.
            "WA:",
            "+1 FA>=1",
            "-1 A<=9",
            "-2 WA>=1",
            "WB:",
            "+1 FB>=1",
            "-1 B<=9",
            "-2 WB>=1",
            # Completion is the complementary pulse: active and below ten.
            "DA:",
            "+1 FA>=1",
            "-1 A>=10",
            "-2 DA>=1",
            "DB:",
            "+1 FB>=1",
            "-1 B>=10",
            "-2 DB>=1",
            # Filter the stopping bank's digit into a one pulse.
            "OA:",
            "+1 SA>=1",
            "-1 A<=0",
            "-1 OA>=1",
            "OB:",
            "+1 SB>=1",
            "-1 B<=0",
            "-1 OB>=1",
            "DELAY:",
            "+1 SA>=1",
            "+1 SB>=1",
            "-1 DELAY>=1",
            "OUT=48:",
            "+1 OA>=1",
            "+1 OB>=1",
            "PRINT:",
            "+1 DELAY>=1",
            "-1 PRINT>=1",
            "EXIT:",
            "+1 PRINT>=1",
        )
    )
    return "\n".join(lines)


def container(truth_table: str) -> str:
    """Build a Container program, switching to the linear packed decoder."""
    n = _validate_truth_table(truth_table)
    if n <= 6:
        return _container_tree(truth_table)
    return _container_packed(truth_table)
