"""The 123 replay oracle: re-execute an emitted program and judge it.

Test-only.  The generator emits by rule; this replays the emitted code
against every row so a construction that spells the wrong thing fails.
"""

from esolangs.tools.one_two_three_construct import _ONE, _RING, ConstructError


def _jump_tables(code: str) -> tuple[list[int], list[int]]:
    """Per ``3`` position, where a backward and a forward jump land.

    Computed once; the interpreter rescans per jump.
    """
    threes = [i for i, c in enumerate(code) if c == "3"]
    back = [0] * len(code)
    fwd = [0] * len(code)
    prev = -1
    for i in threes:
        back[i] = prev + 1  # just after the previous 3, or the start
        prev = i
    nxt = len(code)
    for i in reversed(threes):
        fwd[i] = nxt + 1 if nxt < len(code) else len(code)
        nxt = i
    return back, fwd


def _code_runs(code: str) -> tuple[list[int], list[str], list[int]]:
    """Index ``code`` into maximal ``1``/``2`` runs.

    ``(run_id_at, char_of_run, end_of_run)``, so a run is one step.
    """
    run_at = [-1] * len(code)
    chars: list[str] = []
    ends: list[int] = []
    i = 0
    while i < len(code):
        c = code[i]
        if c not in "12":
            i += 1
            continue
        j = i
        while j < len(code) and code[j] == c:
            j += 1
        for k in range(i, j):
            run_at[k] = len(chars)
        chars.append(c)
        ends.append(j)
        i = j
    return run_at, chars, ends


def _replay_ones(pos: int, tape: int, w: int) -> tuple[int, int]:
    """Apply ``"1"*w``, per the interpreter's rule for ``1``.

    Above the ring one XOR; inside, laps of period 4 are a parity and
    ``w % 4`` steps remain.
    """
    while w > 0:
        if pos >= 0:
            head = min(w, pos + 1)
            tape ^= ((1 << head) - 1) << (pos - head + 1 + _RING)
            pos -= head
            w -= head
            # No wrap check here: ``head`` is capped at ``pos + 1``, so this
            # walk stops at -1 at the lowest and cannot reach -4.  The cell-0
            # wrap belongs to the inside-the-ring loop below, which is the
            # only place the pointer steps one at a time.
            continue
        laps, rest = divmod(w, 4)
        if laps:
            if laps & 1:
                tape ^= 0b1111  # a lap flips cells -3..0 once each
            w = rest
            continue
        for _ in range(w):
            tape ^= 1 << (pos + _RING)
            pos -= 1
            if pos == -4:
                pos = 0
        w = 0
    return pos, tape


def _replay_twos(pos: int, tape: int, w: int) -> tuple[int, int]:
    """Apply ``"2"*w``; the first step decides whether the ring is left.

    ``2`` at -3 raises where the interpreter raises :class:`EOFError`; -1
    and -2 land on 0.
    """
    if w <= 0:
        return pos, tape
    if pos == -3:
        raise ConstructError("replay: '2' at -3 reads stdin")
    if pos in (-1, -2):
        pos = 0
        w -= 1
    return pos + w, tape


def _replay_verdict(code: str) -> str:
    """Execute one instantiated program: ``"0"`` halts, ``"1"`` loops.

    Written against the interpreter's rules, not the builder's model.
    Per-command stepping cost 95s per five-input table; runs are closed
    form.  Cycle detection stays exact: ``ip`` strictly increases within a
    run and across a forward jump, so sampling at backward jumps and the
    loopback witnesses every loop, with Brent's method.
    """
    if not any(c in "123" for c in code):
        return "0"  # a command-less program halts with no output
    back, fwd = _jump_tables(code)
    run_at, run_ch, run_end = _code_runs(code)
    size = len(code)
    ip = pos = tape = 0
    power = lam = 1
    saved: tuple[int, int, int] | None = None
    # Events, not commands: only jumps and loopbacks are counted, and a
    # run of any length is one step.  There is deliberately no event or
    # command cap here: the answer is a real halt or an exact state revisit,
    # never a fuel-limit inference.  Constructed programs only touch a finite
    # tape prefix, so one of those two outcomes must eventually occur.
    while True:
        if ip >= size:
            # End of the program: halt below location 0, else loop.
            if pos < 0:
                return "0"
            ip = 0
        elif code[ip] == "3":
            if pos < 0:
                ip += 1  # below location 0 a 3 is a NOP
                continue
            if not tape >> (pos + _RING) & 1:
                ip = fwd[ip]  # FALSE skips forward; ip still increases
                continue
            ip = back[ip]
        else:
            r = run_at[ip]
            if r < 0:  # unrecognized characters are NOPs
                ip += 1
                continue
            fn = _replay_ones if run_ch[r] == _ONE else _replay_twos
            pos, tape = fn(pos, tape, run_end[r] - ip)
            ip = run_end[r]
            continue
        state = (ip, pos, tape)
        if saved == state:
            return "1"
        if power == lam:
            saved, power, lam = state, power * 2, 0
        lam += 1
