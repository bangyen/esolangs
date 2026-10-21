"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return 2 * n + 2


def workspace(n: int, program: str) -> int:
    """The stated workspace bound, evaluated for n and the program.

    Every declared container stays in the snapshot: 8 bits a name character
    plus its value, which ``2n + 2`` ticks raise by at most its positive
    deltas each; a zero value still costs a bit.  The EXIT code is at most
    EXIT's peak, and input progress and the read count at most one a tick.
    """
    bl = int.bit_length
    ticks = execution(n, program)
    peaks: dict[str, int] = {}
    name = ""
    for raw in program.splitlines():
        line = raw.strip()
        if ":" in line:
            head, _, start = line[:-1].partition("=")
            name = head
            peaks[name] = int(start or 0)
        elif line:
            delta = int(line.split()[0])
            peaks[name] += ticks * max(delta, 0)
    exit_code = max(bl(peaks.get("EXIT", 0)), 1)
    values = sum(8 * len(key) + max(bl(peak), 1) for key, peak in peaks.items())
    return values + exit_code + 2 * bl(ticks)
