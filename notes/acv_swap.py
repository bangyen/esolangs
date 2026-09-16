"""Linear SLOW ACV MAMMALIAN generator prototype, milestone A (n <= 3).

Probes 1b/1cd/1e validated the mechanisms.  Arrays: 0 payload ballast,
M=1 mid anchor, B=2 trigger queue (127 cells + head; fillers >= 128),
Q=3 second ballast, C=5 passthrough, pads 9-12, 21, 22.  Canonical heads
form the cycle 0->Q->C->M->B->0; every gadget keeps the global SEED
count at 0 mod 256.
"""

from esolangs.tools.helpers import _validate_truth_table

Q, C, M, B, P = 3, 5, 1, 2, 4
# heads are route-equivalent mod 23 AND reachable mod gcd(i+1, 256)
# cycle 0->Q->C->M->B->0; P->B for the outer level's replant hop.
# pads: 21->12->M (M-pump exit), 22->9->10->11->0 (single-level payload
# exit), 13->14->15->P (nested payload exit, into the outer body),
# 16->0 (outer counter exit, the final landing).
# The nested chains use only EVEN arrays: SEED adds (index + 1), so an
# even index has an odd step, coprime to 256, and every head value in the
# routing class is reachable.  Array 15 (step 16) could reach only one
# residue mod 16 and had no routable head at all.
# Swapped roles: cycle is 0->P->C->M->B->0 and Q is the frozen outer
# anchor (Q->B for the replant).  P is only ever pumped by the loop, which
# is free, so its 0.614 tok/unit raise cost never gets paid.
CANON = {0: 4, P: 1, C: 42, M: 24, B: 21, Q: 68,
         9: 24, 10: 1, 11: 12, 12: 12, 21: 14, 22: 10,
         8: 6, 14: 4, 18: 2, 20: 6, 6: 17}
T3, T1, T1N, TOUT = 3, 40, 41, 6
ROUTE3, ROUTE1 = 249, 250   # (2+249)%23 = 21, (2+250)%23 = 22
ROUTE1N = [6 + 23 * k for k in range(11)]     # (2+w)%23 = 8
ROUTE_OUT = [1 + 23 * k for k in range(12)]   # (5+w)%23 = 6
QCELLS = 170                # queue cells besides the head
# The outer level's arrays (P, the C counter, the 8->14->18->20->P
# and 6->0 pads) are only set up when this is on.  Adding them
# unconditionally moved every address and every residue and took
# the single-level build from 20/20 at n<=2 down to 4/20, so the
# default stays on the configuration that is gated.
NESTED_SETUP = True
CCELLS = 60                 # outer-counter cells besides the head

M_BODY = [
    "CONSUME", "EXCRETE",                        # rotation @Q
    "SPRINT", "SPRINT",                          # P->C->M
    *(["DIGEST", "EXCRETE"] * 2),
    "CONSUME", "CONSUME", "EXCRETE",             # churn last: exit cell
    "SPRINT",                                    # M->B
    "CONSUME", "SPRINT", "EXCRETE",              # queue test (divert idx 15)
    "SPRINT", "SPRINT",                          # B->0->Q
    "DIGEST", "LEAPFROG",                        # @Q loop | @M exit
]
# M divert: pad 21 -> 12 -> M: tokens after idx 15: EXCRETE@21,
# SPRINT(h14)->12, SPRINT(h12)->1=M?? (12+12)%23 = 1: yes.  Then
# DIGEST@M, LEAPFROG@M -> nonhead_M.

PAY_BODY = [
    "CONSUME", "EXCRETE",                        # rotation @M
    "SPRINT",                                    # M->B
    "CONSUME", "SPRINT", "EXCRETE",              # queue test (divert idx 4)
    "SPRINT",                                    # B->0
    *(["DIGEST", "EXCRETE"] * 2),
    "CONSUME", "CONSUME", "EXCRETE",             # churn last: exit cell
    "SPRINT",                                    # 0->P (partner)
    "CONSUME", "CONSUME", "EXCRETE",             # churn @P
    "DIGEST", "EXCRETE",                         # pump @P
    "SPRINT", "SPRINT",                          # P->C->M
    "DIGEST", "LEAPFROG",                        # @M loop | @0 exit
]
# The nested payload is the same token list; only the trigger value (and
# so which route cell SPRINT indexes) differs, sending the divert down
# 13->14->15->P into the outer body instead of 22->...->0.
PAY_BODY_NESTED = list(PAY_BODY)

OUTER_HEAD = [
    "CONSUME", "EXCRETE",              # rotation @P: kills acc, keeps S_P
    "SPRINT",                          # P->B
]
OUTER_TAIL = [
    "SPRINT", "SPRINT", "SPRINT",      # B->0->Q->C
    "CONSUME", "SPRINT", "EXCRETE",    # counter test @C (divert -> 16)
    "SPRINT",                          # C->M | 16->0
    "DIGEST", "LEAPFROG",              # @M re-enter inner | @0 final exit
]

# payload divert: pad 22 -> 9 -> 10 -> 11 -> 0: tokens after idx 4:
# EXCRETE@22, SPRINT(h10)->9, CONSUME/CONSUME/EXCRETE churn @9,
# DIGEST/EXCRETE x3 junk @9, SPRINT(h1)->10, churn @10, DIGEST/EXCRETE
# junk @10, SPRINT(h1)->11, SPRINT(h12)->0, DIGEST@0, LEAPFROG@0.

TOK = {"SEED": 0, "CONFLAGRATE": 1, "EXCRETE": 2, "CONSUME": 3,
       "FISSION": 4, "DIGEST": 5, "SPRINT": 6, "LEAPFROG": 7,
       "ACCEPT": 8, "PRONOUNCE": 9}


class World:
    """The 23 arrays plus cached per-array sums.

    DIGEST and ``nonhead`` are the hot path of every pump simulation and
    both fold a whole array, so the sums are maintained incrementally by
    ``step``; anything that touches an array around ``step``'s back has
    to call ``resum``.
    """

    __slots__ = ("arrays", "ptr", "acc", "sums")

    def __init__(self):
        self.arrays = [[0] for _ in range(23)]
        self.ptr = 0
        self.acc = 0
        self.sums = [0] * 23

    def clone(self):
        w = World.__new__(World)
        w.arrays = [list(a) for a in self.arrays]
        w.ptr = self.ptr
        w.acc = self.acc
        w.sums = list(self.sums)
        return w

    def resum(self, i):
        self.sums[i] = sum(self.arrays[i])

    def step(self, tok, bit=None):
        n = TOK[tok]
        if n == 0:
            for num, arr in enumerate(self.arrays):
                if arr:
                    old = arr[0]
                    arr[0] = (old + num + 1) % 256
                    self.sums[num] += arr[0] - old
        elif n == 2:
            self.arrays[self.ptr].append(self.acc % 256)
            self.sums[self.ptr] += self.acc % 256
            self.acc = 0
        elif n == 3:
            arr = self.arrays[self.ptr]
            if arr:
                self.acc = arr.pop((len(arr) - 1) // 2)
                self.sums[self.ptr] -= self.acc
        elif n == 5:
            self.acc ^= self.sums[self.ptr]
        elif n == 6:
            arr = self.arrays[self.ptr]
            if self.acc < len(arr):
                self.ptr = (self.ptr + arr[self.acc]) % 23
        elif n == 7:
            arr = self.arrays[self.ptr]
            if arr and arr[-1]:
                return self.acc - arr[0] - 1
        elif n == 8:
            val = ((48 + bit) ^ self.acc) % 256
            self.arrays[0].append(val)
            self.sums[0] += val
        return None

    def nonhead(self, i):
        arr = self.arrays[i]
        return self.sums[i] - (arr[0] if arr else 0)

    def seed_solve(self, target):
        """Smallest k so DIGEST after k SEEDs leaves ``acc % 256 == target``.

        Closed form for the clone-step-check probe loops: k SEEDs move the
        current head to ``(h0 + k*(ptr+1)) % 256`` and nothing else DIGEST
        reads, so no clone is needed.  Returns ``None`` when the residue
        class cannot reach ``target``.
        """
        arr = self.arrays[self.ptr]
        if not arr:
            return None
        h0 = arr[0]
        base = self.sums[self.ptr] - h0
        step = self.ptr + 1
        for k in range(256):
            if (self.acc ^ (base + (h0 + k * step) % 256)) % 256 == target:
                return k
        return None


class Fail(AssertionError):
    pass


class Builder:
    def __init__(self, table, n, shared=None):
        self.table = table
        self.n = n
        self.text = {}
        self.high = 0
        # Estimate caches shared across the scratch builders of one build:
        # "chain" maps levels -> last settled chain extent, "span" maps
        # levels -> last built subtree span.  Estimates only seed the
        # fixed points below; every accepted address comes from a dry run.
        self.shared = shared if shared is not None else {
            "chain": {}, "span": {0: 400},
        }

    # ---- text/emission ------------------------------------------------

    def lay(self, addr, toks):
        for i, t in enumerate(toks):
            if addr + i in self.text:
                raise Fail(f"collision at {addr + i}")
            self.text[addr + i] = t
        end = addr + len(toks)
        if end > self.high:
            self.high = end

    def merge(self, other):
        """Adopt a scratch builder's laid text (same collision rule)."""
        for a, t in other.text.items():
            if a in self.text:
                raise Fail(f"merge collision at {a}")
            self.text[a] = t
        if other.high > self.high:
            self.high = other.high

    def emit(self, w, cur, toks):
        self.lay(cur, toks)
        for t in toks:
            if w.step(t) is not None:
                raise Fail("stray LEAPFROG")
        return cur + len(toks)

    def dance(self, w, cur, stops):
        for s in stops:
            cur = self.emit(w, cur, ["SPRINT"])
            if w.ptr != s:
                raise Fail(f"dance: at {w.ptr}, wanted {s}")
        return cur

    def seeded_append(self, w, cur, arr, value):
        if not (w.ptr == arr and w.acc == 0 and 1 <= value <= 255):
            raise Fail("seeded_append pre")
        d = w.seed_solve(value)
        if d is None:
            raise Fail("no seed count")
        return self.emit(
            w, cur,
            ["SEED"] * d + ["DIGEST", "EXCRETE"] + ["SEED"] * (256 - d),
        )

    def _chunk(self, w, cur, arr, value):
        """SEED*c DIGEST EXCRETE appending exactly ``value`` (no balance)."""
        if w.ptr != arr:
            raise Fail(f"chunk on {w.ptr}, wanted {arr}")
        c = w.seed_solve(value)
        if c is None:
            raise Fail("chunk residue unreachable")
        return self.emit(w, cur, ["SEED"] * c + ["DIGEST", "EXCRETE"]), c

    def _seed_balance(self, w, cur, seeds):
        if seeds % 256:
            cur = self.emit(w, cur, ["SEED"] * (256 - seeds % 256))
        return cur

    def _free_chunk(self, w, cur, arr):
        """DIGEST EXCRETE with no residue solve: append whatever S%256 is.

        Two tokens instead of ~130.  The value is not chosen, so this only
        runs while the target is far; a zero append would both stall and
        leave a cell LEAPFROG cannot fire on, so that case pops a mid cell
        to reshuffle the low byte instead.
        """
        if w.ptr != arr:
            raise Fail(f"free chunk on {w.ptr}, wanted {arr}")
        test = w.clone()
        test.step("DIGEST")
        if test.acc % 256 == 0:
            if len(w.arrays[arr]) <= 6:
                raise Fail("free chunk stalled with nothing to pop")
            return self.emit(w, cur, ["CONSUME", "CONSUME", "EXCRETE"])
        return self.emit(w, cur, ["DIGEST", "EXCRETE"])

    def seeded_append_any(self, w, cur, arr, candidates):
        """Append the first of ``candidates`` the residue can reach.

        ``SEED`` adds ``arr + 1`` to this array's head, so the reachable
        appends are one residue class mod ``gcd(arr + 1, 256)``: array 5
        moves in steps of 6 and can only ever append one parity.  Route
        cells therefore come as every value congruent to the hop mod 23,
        not as a single constant.
        """
        for value in candidates:
            if not 1 <= value <= 255:
                continue
            if w.seed_solve(value) is not None:
                return self.seeded_append(w, cur, arr, value)
        raise Fail(f"no reachable append among {candidates[:4]}... on {arr}")

    def raise_at_least(self, w, cur, arr, floor):
        while w.nonhead(arr) < floor:
            cur = self._free_chunk(w, cur, arr)
        return cur

    def raise_to(self, w, cur, arr, target):
        """Free chunks while far, then one solved append for the gap."""
        if w.nonhead(arr) > target:
            raise Fail(f"raise backwards ({w.nonhead(arr)} > {target})")
        while target - w.nonhead(arr) > 255:
            before = w.nonhead(arr)
            cur = self._free_chunk(w, cur, arr)
            if w.nonhead(arr) > target:
                raise Fail("free chunk overshot")
            if w.nonhead(arr) == before:
                raise Fail("free chunk made no progress")
        gap = target - w.nonhead(arr)
        if gap:
            cur, c = self._chunk(w, cur, arr, gap)
            cur = self._seed_balance(w, cur, c)
        if w.nonhead(arr) != target:
            raise Fail("raise missed")
        return cur

    def dance(self, w, cur, stops):
        for s in stops:
            cur = self.emit(w, cur, ["SPRINT"])
            if w.ptr != s:
                raise Fail(f"dance: at {w.ptr}, wanted {s}")
        return cur

    def seeded_append(self, w, cur, arr, value):
        if not (w.ptr == arr and w.acc == 0 and 1 <= value <= 255):
            raise Fail("seeded_append pre")
        d = w.seed_solve(value)
        if d is None:
            raise Fail("no seed count")
        return self.emit(
            w, cur,
            ["SEED"] * d + ["DIGEST", "EXCRETE"] + ["SEED"] * (256 - d),
        )

    def _chunk(self, w, cur, arr, value):
        """SEED*c DIGEST EXCRETE appending exactly ``value`` (no balance)."""
        if w.ptr != arr:
            raise Fail(f"chunk on {w.ptr}, wanted {arr}")
        c = w.seed_solve(value)
        if c is None:
            raise Fail("chunk residue unreachable")
        return self.emit(w, cur, ["SEED"] * c + ["DIGEST", "EXCRETE"]), c

    def _seed_balance(self, w, cur, seeds):
        if seeds % 256:
            cur = self.emit(w, cur, ["SEED"] * (256 - seeds % 256))
        return cur

    def seeded_append_any(self, w, cur, arr, candidates):
        """Append the first of ``candidates`` the residue can reach.

        ``SEED`` adds ``arr + 1`` to this array's head, so the reachable
        appends are one residue class mod ``gcd(arr + 1, 256)``: array 5
        moves in steps of 6 and can only ever append one parity.  Route
        cells therefore come as every value congruent to the hop mod 23,
        not as a single constant.
        """
        for value in candidates:
            if not 1 <= value <= 255:
                continue
            if w.seed_solve(value) is not None:
                return self.seeded_append(w, cur, arr, value)
        raise Fail(f"no reachable append among {candidates[:4]}... on {arr}")

    def raise_at_least(self, w, cur, arr, floor):
        big = 256 - {0: 1, M: 2, B: 1, Q: 4}.get(arr, 2)
        seeds = 0
        while w.nonhead(arr) < floor:
            cur, c = self._chunk(w, cur, arr, big)
            seeds += c
        return self._seed_balance(w, cur, seeds)

    def raise_to(self, w, cur, arr, target):
        if w.nonhead(arr) > target:
            raise Fail(f"raise backwards ({w.nonhead(arr)} > {target})")
        big = 256 - {0: 1, M: 2, B: 1, Q: 4}.get(arr, 2)
        seeds = 0
        while target - w.nonhead(arr) > 255:
            cur, c = self._chunk(w, cur, arr, big)
            seeds += c
        gap = target - w.nonhead(arr)
        if gap:
            cur, c = self._chunk(w, cur, arr, gap)
            seeds += c
        cur = self._seed_balance(w, cur, seeds)
        if w.nonhead(arr) != target:
            raise Fail("raise missed")
        return cur

    # ---- loops ----------------------------------------------------------

    def pump_curve(self, w, body, watch, anchor):
        g = w.clone()
        arrb = g.arrays[B]
        for j in range(80, len(arrb)):
            if arrb[j] < 180:
                arrb[j] = 255
        g.resum(B)
        # the body starts at its anchor: ghost-dance there from B
        hops = 2 if anchor == P else 4
        for _ in range(hops):
            g.step("SPRINT")
        if g.ptr != anchor:
            raise Fail("curve ghost dance missed")
        out = []
        for _ in range(140):
            r = None
            for t in body:
                r = g.step(t)
            if r is None:
                break
            out.append(g.nonhead(watch))
        return out

    def fire_distance(self, w, trigger):
        arrb = w.arrays[B]
        mid = (len(arrb) - 1) // 2
        for j in range(mid, len(arrb)):
            if arrb[j] == trigger:
                return j - mid + 1
        raise Fail("no trigger ahead of the march")

    @staticmethod
    def _dry_run(w, body, start):
        for _ in range(200):
            r = None
            for t in body:
                r = w.step(t)
            if r is None:
                raise Fail("dry loop LEAPFROG failed")
            if r + 1 != start:
                return r + 1
        raise Fail("dry loop refused to exit")

    def run_loop(self, w, body, start):
        for _ in range(200):
            r = None
            for t in body:
                r = w.step(t)
            if r is None:
                raise Fail("loop LEAPFROG failed to fire")
            landing = r + 1
            if landing != start:
                return landing
        raise Fail("loop refused to exit")

    def purge_zeros(self, w, cur, arr, window=70):
        """Destroy zero cells due to surface at ``arr``'s middle soon."""
        assert w.ptr == arr
        guard = 0
        while True:
            guard += 1
            if guard > 400:
                raise Fail("purge did not settle")
            cells = w.arrays[arr]
            mid = (len(cells) - 1) // 2
            zone = cells[mid:mid + window]
            if 0 not in zone and all(zone):
                return cur
            cur = self.emit(w, cur, ["CONSUME", "CONSUME", "EXCRETE"])

    def _pump_gadget(self, w, cur, body, n_iter):
        """Plant, pre-march, dance, and pad up to the anchor; no laying.

        Returns ``(cur, loop_at)``.  The pad is part of the gadget on
        purpose: it runs rotation pairs on the anchor array, so leaving it
        out of a dry run made the probe and the real run diverge.
        """
        trigger = T3 if body is M_BODY else T1
        anchor = P if body is M_BODY else M
        cur = self.seeded_append(w, cur, B, trigger)
        dist = self.fire_distance(w, trigger)
        if dist < n_iter:
            raise Fail(f"trigger too close ({dist} < {n_iter})")
        for _ in range(dist - n_iter):
            cur = self.emit(w, cur, ["CONSUME", "EXCRETE"])
        path = [0, P] if anchor == P else [0, P, C, M]
        cur = self.dance(w, cur, path)
        loop_at = w.nonhead(anchor)
        if loop_at < cur:
            raise Fail(f"anchor behind text ({loop_at} < {cur})")
        gap = loop_at - cur
        if gap % 2:
            cur = self.emit(w, cur, ["DIGEST"])
            gap -= 1
        for _ in range(gap // 2):
            cur = self.emit(w, cur, ["CONSUME", "EXCRETE"])
        if cur != loop_at:
            raise Fail("pad arithmetic")
        return cur, loop_at

    def pump(self, w, cur, body, primary, target_min):
        """Single-level pump landing at or past ``target_min``.

        The iteration count is chosen by dry run on a scratch builder:
        the gadget's own text depends on it (the pre-march and the pad),
        so a candidate cannot be tested after emitting, and some counts
        leave the pumped array ending on a zero cell that ``LEAPFROG``
        will not fire on.
        """
        anchor = P if body is M_BODY else M
        target_min = max(target_min, w.nonhead(anchor) + len(body) + 8)
        curve = self.pump_curve(w, body, primary, anchor)
        if not curve or curve[-1] < target_min:
            reach = curve[-1] if curve else 0
            raise Fail(f"pump reach {reach} < {target_min}")
        first = next(i + 1 for i, v in enumerate(curve) if v >= target_min)
        chosen = None
        for cand in range(first, min(first + 40, len(curve) + 1)):
            scratch = Builder(self.table, self.n)
            probe = w.clone()
            try:
                _, loop_at = scratch._pump_gadget(probe, cur, body, cand)
                landing = Builder._dry_run(probe, body, loop_at)
            except Fail:
                continue
            if landing != probe.nonhead(primary) or landing < target_min:
                continue
            if landing < loop_at + len(body):
                continue
            chosen = cand
            break
        if chosen is None:
            raise Fail("no viable exit iteration")
        cur, loop_at = self._pump_gadget(w, cur, body, chosen)
        self.lay(loop_at, body)
        landing = self.run_loop(w, body, loop_at)
        if landing != w.nonhead(primary):
            raise Fail("landing != pumped value")
        if landing < loop_at + len(body):
            raise Fail("landing inside loop text")
        return landing

    def _nested_gadget(self, w, cur, rounds, margin, bshift=0):
        """Plant both triggers and park all three anchors; no laying yet.

        Returns ``(cur, a_in, a_out)``.  ``rounds`` picks how many times
        the outer loop re-enters the inner one, which is what multiplies
        reach past a single instance's ~87 iterations.
        """
        # Normalise the entry rather than assume it: a nonzero
        # accumulator XORs into every residue solve below and halves the
        # appends B can reach, and the plant has to happen on B.
        if w.acc:
            cur = self.emit(w, cur, ["EXCRETE"])
        if w.ptr != B:
            cur = shift_dance(self, w, cur, B)
        cur = self.seeded_append_any(w, cur, B, [T1N])
        # Rounds move the exit in ~87-iteration jumps, which is too coarse
        # to dodge a zero last cell on array 0; pre-marching B shifts the
        # inner trigger one iteration at a time and gives the fine knob.
        for _ in range(bshift):
            cur = self.emit(w, cur, ["CONSUME", "EXCRETE"])
        cur = self.dance(w, cur, [0, P, C])   # swapped cycle
        # Append first, then pre-march: an append lands at the array end,
        # so the march is what selects the firing round.
        cur = self.seeded_append_any(w, cur, C, [TOUT])
        mid_c = (len(w.arrays[C]) - 1) // 2
        dist_c = len(w.arrays[C]) - mid_c
        if rounds > dist_c:
            raise Fail(f"counter holds {dist_c} rounds, wanted {rounds}")
        for _ in range(dist_c - rounds):
            cur = self.emit(w, cur, ["CONSUME", "EXCRETE"])
        cur = self.dance(w, cur, [M])
        # Raise freely and take wherever the anchor lands: an exact raise
        # needs a reachable residue, and M's SEED step is 2, so half of
        # the gaps cannot be hit at all.  The slot address is an output
        # here, not an input -- the same way the single-level pump reads
        # its loop address off the anchor.
        # Fix the inner address first, with room for the emission still
        # to come, then floor the outer slot above it.  Both anchors only
        # rise, so committing either one late strands the other: raising
        # M after P pushed M past the outer slot, and raising P after
        # fixing a_in left the cursor 5,000 tokens beyond its own pad.
        cur = self.raise_at_least(w, cur, M, cur + margin)
        a_in = w.nonhead(M)
        cur = shift_dance(self, w, cur, Q)
        cur = self.raise_at_least(
            w, cur, Q, a_in + len(PAY_BODY) + margin // 2
        )
        a_out = w.nonhead(Q)
        cur = shift_dance(self, w, cur, M)
        if cur > a_in:
            raise Fail(f"nested gadget overran its slot ({cur} > {a_in})")
        import os
        if os.environ.get("ACV_TRACE"):
            print(f"      gadget: a_in={a_in} a_out={a_out} cur={cur} "
                  f"nonhead_M={w.nonhead(M)} nonhead_P={w.nonhead(P)}")
        if cur > a_in:
            raise Fail(f"nested gadget overran its slot ({cur} > {a_in})")
        gap = a_in - cur
        if gap % 2:
            cur = self.emit(w, cur, ["DIGEST"])
            gap -= 1
        for _ in range(gap // 2):
            cur = self.emit(w, cur, ["CONSUME", "EXCRETE"])
        return cur, a_in, a_out

    def pump_nested(self, w, cur, target_min):
        """Two-level payload pump landing at or past ``target_min``.

        Each round is worth ~87 inner iterations and a single instance
        caps there, so the round count is the only way to reach a subtree
        bigger than ~49000 tokens.  Rounds are chosen by dry run: the
        gadget's text depends on the count (the counter pre-march), so a
        candidate cannot be tested after emitting, and some counts leave
        array 0 ending on a zero cell that ``LEAPFROG`` will not fire on.
        """
        margin = 18000

        def attempt(rounds, bshift):
            scratch = Builder(self.table, self.n)
            probe = w.clone()
            _, a_in, a_out = scratch._nested_gadget(
                probe, cur, rounds, margin, bshift
            )
            scratch.lay(a_in, PAY_BODY)
            landing, _ = scratch.run_nested(probe, a_in, a_out)
            ok = (
                landing == probe.nonhead(0)
                and probe.ptr == 0
                and landing >= target_min
            )
            return ok, landing

        # Two cheap probes give the per-round yield, so the scan starts
        # near the needed count instead of walking up from 2 (each
        # candidate simulates the whole two-level run).  The yield
        # accelerates, so the linear estimate overshoots; scanning from a
        # few below keeps the landing near-minimal.
        lands = {}
        for r in (2, 4):
            try:
                _, lands[r] = attempt(r, 0)
            except Fail:
                pass
        if 2 in lands and 4 in lands and lands[4] > lands[2]:
            per_round = (lands[4] - lands[2]) / 2
            r_est = 4 + max(0, int((target_min - lands[4]) / per_round))
        else:
            r_est = 2
        best = max(lands.values(), default=0)
        for rounds in range(max(2, r_est - 4), max(r_est + 40, 44)):
            capacity_hit = False
            for bshift in range(0, 12):
                try:
                    ok, landing = attempt(rounds, bshift)
                except Fail as exc:
                    if "counter holds" in str(exc):
                        capacity_hit = True
                        break
                    continue
                best = max(best, landing)
                if not ok:
                    continue
                cur, a_in, a_out = self._nested_gadget(
                    w, cur, rounds, margin, bshift
                )
                self.lay(a_in, PAY_BODY)
                landing, _ = self.run_nested(w, a_in, a_out)
                if landing != w.nonhead(0):
                    raise Fail("nested landing != pumped nonhead")
                if landing < target_min:
                    raise Fail("nested landing short of the slot")
                return landing
            if capacity_hit:
                break
        raise Fail(f"pump reach exhausted: best {best} < {target_min}")

    def outer_body(self, w_at_entry):
        """The outer loop's tokens, solved against the arrival state.

        The replant appends ``S_B % 256``, so the rotation and the hop to
        B are simulated before the residue solve.  ``S_B`` is periodic
        across rounds -- the inner loop only recycles B, the fired
        trigger leaves on the pad chain, and the replant puts exactly it
        back -- so one solve serves every round.
        """
        probe = w_at_entry.clone()
        for t in OUTER_HEAD:
            probe.step(t)
        if probe.ptr != B:
            raise Fail(f"outer head landed on {probe.ptr}, not B")
        d = probe.seed_solve(T1N)
        if d is None:
            raise Fail("replant residue unreachable")
        return (
            OUTER_HEAD
            + ["SEED"] * d
            + ["DIGEST", "EXCRETE"]
            + ["SEED"] * (256 - d)
            + OUTER_TAIL
        )

    def run_nested(self, w, a_in, a_out):
        """Run the laid two-level loop; return the final landing.

        The outer body is written on first arrival rather than up front:
        its replant residue depends on ``S_B`` after the inner loop has
        already run, which is not known at lay time.
        """
        w.ptr = M
        w.acc = w.sums[M]
        ind = a_in
        body_out = None
        rounds = 0
        for _ in range(4_000_000):
            if a_in <= ind < a_in + len(PAY_BODY):
                lo, body = a_in, PAY_BODY
            elif body_out is not None and a_out <= ind < a_out + len(body_out):
                lo, body = a_out, body_out
            elif ind == a_out:
                body_out = self.outer_body(w)
                self.lay(a_out, body_out)
                lo, body = a_out, body_out
            else:
                return ind, rounds
            tok = body[ind - lo]
            r = w.step(tok)
            if tok == "LEAPFROG":
                if r is None:
                    arr = w.arrays[w.ptr]
                    raise Fail(
                        f"LEAPFROG dead ind={ind} ptr={w.ptr} "
                        f"last={arr[-1] if arr else None} "
                        f"body={'inner' if lo == a_in else 'outer'} "
                        f"rounds={rounds}"
                    )
                nxt = r + 1
                if lo == a_in and nxt == a_out:
                    rounds += 1
                ind = nxt
            else:
                ind += 1
        raise Fail("nested loop did not exit")

    # ---- tree ------------------------------------------------------------

    def leaf(self, w, cur, bit):
        cur = self.emit(w, cur, ["EXCRETE"])
        d = w.seed_solve(48 + bit)
        if d is None:
            raise Fail("leaf residue")
        toks = ["SEED"] * d + ["DIGEST", "PRONOUNCE", "EXCRETE", "LEAPFROG"]
        self.lay(cur, toks)
        for t in toks[:-1]:
            w.step(t)
        r = w.step("LEAPFROG")
        if r is None or r >= 0:
            raise Fail("leaf did not halt")
        return cur + len(toks)

    # ---- node plumbing ---------------------------------------------------

    @staticmethod
    def _align(t1, head):
        """Smallest address >= ``t1`` whose read residue lands on 48."""
        while (t1 + 1 + head) % 256 != 48:
            t1 += 1
        return t1

    def _dry_read(self, w, cur, t1):
        """Raise to ``t1 + 1`` and lay the read, on a scratch builder.

        Returns ``(sb, wzero, wone, cur_after)``: the scratch builder
        holding the laid text, the two branch worlds just past the read,
        and the text cursor after the read gadget.  The scratch is exact,
        not an estimate: once the addresses settle, its text is merged
        as-is and its worlds carried forward, so nothing runs twice.
        """
        sb = Builder(self.table, self.n, shared=self.shared)
        wz = w.clone()
        c2 = sb.raise_to(wz, cur, 0, t1 + 1)
        sb.lay(c2, ["DIGEST", "ACCEPT", "LEAPFROG"])
        wz.step("DIGEST")
        if wz.acc % 256 != 48:
            raise Fail("ACCEPT residue")
        wone = wz.clone()
        wone.step("ACCEPT", 1)
        r = wone.step("LEAPFROG")
        if r is None or r + 1 != t1 + 1:
            raise Fail("read jump target")
        wz.step("ACCEPT", 0)
        if wz.step("LEAPFROG") is not None:
            raise Fail("zero branch jumped")
        return sb, wz, wone, c2 + 3

    def chain0(self, zero, cur, pay_min):
        """The 0-branch chain: dances, raises, and the payload pump."""
        cur = self.emit(zero, cur, ["EXCRETE"])          # kill acc
        cur = self.dance(zero, cur, [P])
        cur = self.purge_zeros(zero, cur, P)
        if zero.nonhead(P) < cur + 900:
            cur = self.raise_at_least(zero, cur, P, cur + 1000)
        cur = self.dance(zero, cur, [C, M])
        cur = self.purge_zeros(zero, cur, M)
        # The M-pump is gone: it existed to walk M forward for the glue,
        # but M is one of the three arrays a builder raise is cheap on
        # (0.014 tokens per unit), so raising it directly is both shorter
        # and free of the pump's exit-iteration search, which the
        # two-pair body could not satisfy anyway.
        cur = self.raise_at_least(zero, cur, M, cur + 800)
        cur = self.dance(zero, cur, [B])
        try:
            return self.pump(zero, cur, PAY_BODY, 0, pay_min)
        except Fail:
            # One instance saturates a few thousand tokens in; the outer
            # level re-enters it, which is what covers a real subtree.
            return self.pump_nested(zero, cur, pay_min)

    def subtree(self, w, cur, depth, row):
        """Build the subtree read at ``cur``; return its text extent.

        Every address here is settled by dry run rather than by a static
        bound (the old CHAIN_CAP/GADGET_SPAN/sub_cap trio, which broke at
        n >= 2): the 1-subtree address ``t1`` is fixed-pointed against
        the 0-chain's actual laid extent, and the pump's target against
        the 1-subtree's actual extent.  A node's two branches carry
        independent machine states but share one text space, so the
        vertical order is forced -- chain below ``t1``, 1-subtree at
        ``t1 + 1``, 0-subtree at the pump landing above it (the pump
        raises array 0 *from* ``t1 + 1``; anchors only rise).
        """
        if w.nonhead(0) not in (cur, cur + 1):
            raise Fail(f"arrival: nonhead_0 {w.nonhead(0)} vs {cur}")
        if w.ptr != 0:
            raise Fail("arrival pointer not @0")
        if depth == self.n:
            return self.leaf(
                w, cur, int(self.table[int(row, 2) if row else 0])
            )
        levels = self.n - depth
        cur = self.emit(w, cur, ["EXCRETE"])            # kill arrival acc
        head = w.arrays[0][0] % 256
        span_est = self.shared["span"].get(
            levels - 1,
            2 * self.shared["span"].get(levels - 2, 400) + 60000,
        )
        chain_est = self.shared["chain"].get(levels, 60000)
        # ---- settle t1 against the chain's actual extent -------------
        t1 = self._align(cur + chain_est + SLACK, head)
        for _ in range(12):
            sb, wz, wone, c2 = self._dry_read(w, cur, t1)
            try:
                sb.chain0(wz, c2, t1 + 1 + span_est + 2 * SLACK)
            except Fail:
                # The span estimate can overshoot the pump's reach; the
                # gadget's extent barely depends on the target, so a
                # minimal-target dry gives the same settling answer.
                sb, wz, wone, c2 = self._dry_read(w, cur, t1)
                sb.chain0(wz, c2, 0)
            # Accept a window, not an exact hit: the chain's extent
            # wiggles a few hundred with round choices, so demanding
            # equality can oscillate between two aligned values.
            if sb.high + 256 <= t1 <= sb.high + 2 * SLACK + 512:
                break
            t1 = self._align(sb.high + SLACK, head)
        else:
            raise Fail("t1 did not settle against the chain")
        # ---- settle the pump target against the 1-subtree ------------
        sb1 = end1 = None
        sb1_t1 = None
        for _ in range(8):
            sb, wz, wone, c2 = self._dry_read(w, cur, t1)
            if sb1_t1 != t1:
                sb1 = Builder(self.table, self.n, shared=self.shared)
                end1 = sb1.subtree(
                    wone.clone(), t1 + 1, depth + 1, row + "1"
                )
                sb1_t1 = t1
                self.shared["span"][levels - 1] = end1 - t1 - 1
            landing0 = sb.chain0(wz, c2, end1 + SLACK)
            if sb.high <= t1 + 1:
                break
            t1 = self._align(sb.high + SLACK, head)
        else:
            raise Fail("pump target did not settle against the 1-subtree")
        self.shared["chain"][levels] = sb.high - cur
        import os
        if os.environ.get("ACV_TRACE"):
            print(
                f"  node {row or 'root':>6} levels={levels}: cur={cur} "
                f"t1={t1} chain_end={sb.high} end1={end1} "
                f"landing0={landing0} (climb {landing0 - t1 - 1})"
            )
        # The dry runs are exact, so adopt them: text merged, the caller's
        # world advanced to the 0-branch state the chain left behind.
        self.merge(sb)
        self.merge(sb1)
        w.arrays, w.ptr, w.acc, w.sums = wz.arrays, wz.ptr, wz.acc, wz.sums
        end0 = self.subtree(w, landing0, depth + 1, row + "0")
        return max(end0, end1)


# Cushion between a settled extent and the next address chosen above
# it: absorbs the wiggle between a dry run and its replay (the raise's
# token count moves ~1/64 per unit of t1, round choices move the gadget
# by a few hundred).  Every hard bound is a dry-run actual; this only
# pads them.
SLACK = 3000


def ballast_pairs(b, w, cur, arr, count):
    done = 0
    while done < count:
        if w.ptr != arr:
            raise Fail(f"free chunk on {w.ptr}, wanted {arr}")
        test = w.clone()
        test.step("DIGEST")
        if test.acc % 256 == 0:
            if len(w.arrays[arr]) > 4:
                cur = b.emit(w, cur, ["CONSUME", "CONSUME", "EXCRETE"])
            else:
                cur = b.emit(w, cur, ["SEED"] * 128)
                cur = b.emit(w, cur, ["SEED"] * 128)
                raise Fail("ballast stuck at zero")
            continue
        cur = b.emit(w, cur, ["DIGEST", "EXCRETE"])
        done += 1
    return cur


def set_head(b, w, cur, arr, value, exact=True):
    """Give ``arr`` head ``value``; with ``exact`` false, any value in its
    class mod 23 will do, since only the class decides SPRINT's hop.

    Needed because SEED adds ``arr + 1`` per token, so array 15 moves in
    steps of 16 and can reach only one residue mod 16: the head that
    routes it has to be chosen from the whole class, not fixed.
    """
    if exact:
        cur = b.seeded_append(w, cur, arr, value)
    else:
        cur = b.seeded_append_any(
            w, cur, arr, [value + 23 * k for k in range(11)]
        )
    b.lay(cur, ["CONSUME"])
    w.step("CONSUME")
    if w.acc % 256 != 0 or w.arrays[arr][0] % 23 != value % 23:
        raise Fail("set_head")
    if exact and w.arrays[arr][0] != value:
        raise Fail("set_head exact")
    w.acc = 0  # popped head is 0 by construction
    return cur + 1


def shift_dance(b, w, cur, target):
    """Reach ``target`` from the current array with one SEED shift."""
    a = w.ptr
    probe = w.clone()
    for s in range(256):
        test = probe.clone()
        test.step("SPRINT")
        if test.ptr == target:
            break
        probe.step("SEED")
    else:
        raise Fail("no shift reaches the target")
    toks = ["SEED"] * s + ["SPRINT"] + ["SEED"] * ((256 - s) % 256)
    cur = b.emit(w, cur, toks)
    if w.ptr != target:
        raise Fail("shift dance missed")
    return cur


def setup(b, w):
    cur = 0
    cur = set_head(b, w, cur, 0, CANON[0])
    cur = b.dance(w, cur, [P])
    cur = set_head(b, w, cur, P, CANON[P])
    cur = ballast_pairs(b, w, cur, P, 8)
    cur = b.dance(w, cur, [C])
    cur = set_head(b, w, cur, C, CANON[C])
    cur = b.dance(w, cur, [M])
    cur = set_head(b, w, cur, M, CANON[M])
    cur = ballast_pairs(b, w, cur, M, 8)
    cur = b.dance(w, cur, [B])
    cur = set_head(b, w, cur, B, CANON[B])
    # queue: 127 cells, routes at index 3 and 64
    idx = 1
    while idx <= QCELLS:
        if idx == 3:
            cur = b.seeded_append(w, cur, B, ROUTE3)
            idx += 1
            continue
        if idx == T1:
            cur = b.seeded_append(w, cur, B, ROUTE1)
            idx += 1
            continue
        if idx == T1N and NESTED_SETUP:
            cur = b.seeded_append_any(w, cur, B, ROUTE1N)
            idx += 1
            continue
        # batched decay fillers: seed once to 255, then pairs while the
        # appended value stays a filler (>= 128)
        d = w.seed_solve(255)
        if d is None:
            raise Fail("filler residue unreachable")
        toks = ["SEED"] * d
        cur = b.emit(w, cur, toks)
        run = 0
        reserved = (3, T1, T1N) if NESTED_SETUP else (3, T1)
        while idx <= QCELLS and idx not in reserved:
            test = w.clone()
            test.step("DIGEST")
            value = test.acc % 256
            if value < 180:
                break
            cur = b.emit(w, cur, ["DIGEST", "EXCRETE"])
            idx += 1
            run += 1
        cur = b.emit(w, cur, ["SEED"] * (256 - d))
        if not run:
            raise Fail("filler batch stuck")
    # outer anchor P and its counter queue on C
    if not NESTED_SETUP:
        return _finish_pads(b, w, cur, (9, 10, 11, 12, 21, 22))
    cur = shift_dance(b, w, cur, Q)
    cur = set_head(b, w, cur, Q, CANON[Q])
    cur = ballast_pairs(b, w, cur, Q, 10)
    cur = shift_dance(b, w, cur, C)
    cidx = 1
    while cidx <= CCELLS:
        if cidx == TOUT:
            cur = b.seeded_append_any(w, cur, C, ROUTE_OUT)
        else:
            cur = b.seeded_append_any(w, cur, C, [250, 251, 252, 253])
        cidx += 1
    return _finish_pads(b, w, cur, (9, 10, 11, 12, 6, 8, 14, 18, 20, 21, 22))


def _finish_pads(b, w, cur, pads):
    for pad in pads:
        cur = shift_dance(b, w, cur, pad)
        # The original pads take their exact head: relaxing them to the
        # mod-23 class changes their sums, which moves every residue the
        # single-level path solves against.  Only the new even-array pads
        # need the class, because their SEED step cannot reach the exact
        # value at all.
        cur = set_head(
            b, w, cur, pad, CANON[pad], exact=pad not in (6, 8, 14, 18, 20)
        )
        for _ in range(5 if pad in (9, 10, 8, 14, 18) else 2):
            cur = b.emit(w, cur, ["DIGEST", "EXCRETE"])
            if w.arrays[pad][-1] == 0:
                raise Fail("pad cell zero")
    return shift_dance(b, w, cur, 0)


def seed_odd(b, w, cur, arr, count):
    """Append odd high cells so the pump cannot settle on an even sum.

    A free chunk appends `S % 256` and that value doubles, so an array
    built only from doubling goes even throughout and `S % 256` sticks at
    0.  Popping an odd cell flips the parity back.  Simulated over 4,000
    iterations this is the difference between 2,556 and 325,312 of reach.
    """
    for i in range(count):
        cur = b.seeded_append_any(
            w, cur, arr, [253, 251, 249, 247, 245, 243]
        )
    return cur


def preposition(b, w, cur, root_guess):
    cur = b.dance(w, cur, [P])
    cur = b.raise_at_least(w, cur, P, root_guess + 200)
    cur = b.dance(w, cur, [C, M])
    cur = b.raise_at_least(w, cur, M, root_guess - 900)
    # P is the outer level's anchor and gets the same treatment: a free
    # chunk appends S % 256, so an array left at a low sum appends tiny
    # values and raising it later costs ~1.6 tokens per unit -- P at 555
    # spent 23,300 tokens climbing to 39,163 before this.
    if NESTED_SETUP:
        cur = shift_dance(b, w, cur, Q)
        cur = b.raise_at_least(w, cur, Q, root_guess - 900)
        cur = shift_dance(b, w, cur, 0)
    else:
        # Back to array 0: the root raise below reads the *current* array,
        # so leaving the pointer on M made it solve M's residues (step 2,
        # 128 reachable values) and refuse every exact append.
        cur = b.dance(w, cur, [B])
        cur = b.dance(w, cur, [0])
    return cur


def generate(table, root_guess=120000, ccells=None):
    """Build ``table``; the counter is resized when the pump runs dry.

    ``CCELLS`` caps the outer pump's round count, so the reachable climb
    caps with it; a build that fails on reach is retried with a doubled
    counter rather than tuned by hand.  The counter costs setup text
    only, so oversizing is cheap and undersizing is a clean Fail.
    """
    global CCELLS
    if ccells is None:
        ccells = CCELLS
    for _ in range(6):
        CCELLS = ccells
        try:
            return _generate(table, root_guess)
        except Fail as exc:
            if "reach exhausted" not in str(exc):
                raise
            ccells *= 2
    raise Fail("pump reach did not settle at any counter size")


def _generate(table, root_guess):
    import os
    trace = os.environ.get("ACV_TRACE")
    n = _validate_truth_table(table)
    # The raise's text cost is ~0.5 tokens per unit raised, so the naive
    # update root_guess = cur + 2 contracts at only ~0.49 a round and
    # needs a wide attempt budget from a large initial error (n=3's
    # second counter rung settles at attempt 17).  A secant step settles
    # in ~4 -- but the different root it picks built a program whose row
    # 110 EXECUTES WRONG (empty output) while every builder-side check
    # passed, so the naive walk stays until that fragility is understood:
    # correctness is address-sensitive and only the executed artifact
    # counts.
    for attempt in range(40):
        b = Builder(table, n)
        w = World()
        cur = setup(b, w)
        cur = preposition(b, w, cur, root_guess)
        # Odd cells before anything pumps array 0: without them its sum
        # goes even throughout and the pump dies at ~2,500 tokens.
        cur = shift_dance(b, w, cur, 0)
        cur = seed_odd(b, w, cur, 0, 24)
        root = max(root_guess, cur + 2)
        cur_before = cur
        cur = b.raise_to(w, cur, 0, root)
        pad = root - cur
        if trace:
            print(f"root attempt {attempt}: cur_before={cur_before} "
                  f"root={root} cur_after={cur} pad={pad}")
        if pad < 0:
            root_guess = cur + 2
            continue
        if pad % 2:
            cur = b.emit(w, cur, ["DIGEST"])
            pad -= 1
        for _ in range(pad // 2):
            cur = b.emit(w, cur, ["CONSUME", "EXCRETE"])
        if cur != root:
            root_guess = cur + 2
            continue
        w.acc = 0
        b.subtree(w, root, 0, "")
        end = max(b.text) + 1
        return " ".join(b.text.get(i, "SEED") for i in range(end))
    raise Fail("root fixed point did not settle")


if __name__ == "__main__":
    program = generate("01")
    print("n=1 built:", len(program.split()), "tokens")
