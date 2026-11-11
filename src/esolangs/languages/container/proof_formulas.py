"""Executed command and snapshot-bit bounds."""


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Identify the threshold route among default tree and threshold builds."""
    return {"C": int(program.startswith("T="))}


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """The stated workspace bound, evaluated for n and the program.

    Every declared container stays in the snapshot: 8 bits a name character
    plus its value, which ``2n + 2`` ticks raise by at most its positive
    deltas each; a zero value still costs a bit.  The EXIT code is at most
    EXIT's peak, and input progress and the read count at most one a tick.
    """
    if program.startswith("T="):
        # Fixed port names, six-bit IN/OUT, countdown and two read cursors.
        return {"C": 1, "V": 0, "E": 0}
    bl = int.bit_length
    ticks = 2 * n + 2
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
    values = sum(8 * len(key) + max(bl(peak), 1) for key, peak in peaks.items())
    return {"C": 0, "V": values, "E": peaks.get("EXIT", 0)}
