"""Snapshot-bit bounds."""


def workspace(n: int, program: str) -> int:
    """Pending frames at N_d; unary readers hold one frame at n or n+2.

    Anonymous roots preserve parser order, hence every other snapshot index.
    """
    text = "".join(program.split())
    if text.startswith(">(Input>"):
        if "Constant" not in text:
            last = n + 2 if "Divide48" in text else n
            return 10 + last.bit_length() + n.bit_length()
        return 10 + (n + 1).bit_length() + n.bit_length()
    bl = int.bit_length

    def nodes(j: int) -> int:
        """Most parser nodes at depth j: 4 per unequal-halves subtable, 1 else."""
        if j == n:
            return 4
        s, p = 1 << (n - j), 1 << j
        b = min(p, (1 << s) - (1 << (s // 2)))
        return 4 * b + min(p - b, 1 << (s // 2))

    ws = [nodes(j) for j in range(n + 1)]
    return bl(n) + 12 + sum(bl(1 + sum(ws[d + 1 :]) + ws[d] - 4) + 10 for d in range(n))


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Identify unary readers and count the sends beyond the plain reader."""
    text = "".join(program.split())
    if not text.startswith(">(Input>"):
        return {"U": 0, "R": 0}
    if "Constant" in text:
        return {"U": 1, "R": 1}
    return {"U": 1, "R": 2 * int("Divide48" in text)}
