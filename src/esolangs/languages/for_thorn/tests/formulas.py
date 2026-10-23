"""Forþ's emitted characters: the scope heap's level counts."""


def _const_len(value: int) -> int:
    """Length of ``_forth_const(value)``: a digit, then ``F*d+`` per base-15 digit."""
    length = 1
    while value >= 15:
        value //= 15
        length += 4
    return length


def _chars(n: int, _: str) -> int:
    """Characters at most, over the m <= n essential inputs.

    A scope is a step (label and ``+``) and braces, 4, plus its body.  At level d
    a_d scopes dispatch (7); the other s_d - a_d fold to a literal (5), call a
    twin (3 + a distance literal, kept only under 17 characters) or, at level m,
    are leaves.  A twin is on the same level, so its distance is below 2^d, and
    a_d is the fresh ids: at most the non-constant subtables of that level,
    2^(2^(m-d)) - 2.  Where a twin can lie too far to call, every scope may
    dispatch.  A step longer than a digit needs 15^k - 1 absent heap indices
    between two scopes, disjoint across steps.  Reads are 5 an essential input,
    4 an ignored one; a constant table is ``0{3F*3+}`` and n full reads.
    """
    best = 8 + 5 * n + 5
    for m in range(1, n + 1):
        total, s, scopes = 0, 1, 0
        for d in range(m):
            far = 3 + _const_len(2**d - 1) >= 17
            a = s if far else min(s, 2 ** (2 ** (m - d)) - 2)
            other = 0 if far else max(5, 3 + _const_len(2**d - 1))
            total += a * 11 + (s - a) * (4 + other)
            scopes += s
            s = 2 * a
        total += s * 9
        scopes += s
        steps = sum(
            min(scopes, (2 ** (m + 1) - 2) // (15**k - 1))
            for k in range(1, m + 2)
            if 15**k - 1 <= 2 ** (m + 1)
        )
        # The root step is one character; each longer step adds 4 per base-15 digit.
        best = max(best, total - 1 + 4 * steps + 5 * m + 4 * (n - m) + 5)
    return best


FORMULAS = {"scaling": (_chars, False, (2, 3, 4, 5, 6, 7, 8))}
