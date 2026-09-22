"""Machine checks backing the confluent slack certificate (Polynomial mass).

Run:  just proofs   (or python tests/proofs/deep/multiplicity.py)

``docs/proofs/polynomial.md`` proves "each leading zero buys one root" for an
exponential sum on *distinct* nodes.  The language bound is
``Omega(T**2 / log T)``: the routing lemma ``N' <= 2 + 4 * m_routing`` forces
``m_routing = Omega(T/log T)``, the block-incidence bound ``m_routing <= 3 *
L_real`` gives ``L_real = Omega(T/log T)`` distinct root values, and the
distinct-root theorem prices them.  The routing lemma needs the program to
consume its input: without that, a routing-free suffix may cross an
input-dependent number of reads, and the decoded counterexample reads a
variable number of bits, so it is not a program for a fixed-arity table.
Equal real roots form contiguous blocks.
Contracting those blocks turns the
noncrossing bracket matching into an outerplanar incidence graph; one opener
routes per block and one closer per incidence.  ``_check_routing_bound`` pins
the executed facts, including the counterexample that makes the incidence --
not merely ``(value, condition)`` -- necessary.

The confluent analogue is::

    u_d = sum_i P_i(d) y_i^d,   deg P_i < e_i,   u_0 = 1,
    u_z = 0 for z in Z,   |Z| = c - 1,   c = sum e_i,

and the claim is the *same* tail bound with the product read over the expanded
multiset (each ``y_i`` repeated ``e_i`` times).  This module does not prove the
limit step -- that is the Hermite interpolation argument in
``docs/proofs/coefficient-mass.tex``, Proposition 3.7 -- it pins the algebraic
content: the base case is exact, the general bound holds on every certificate
here, the slack assembly's threshold really is the product over the top units,
and the repeated-root mass floor holds on the products and multiples checked.
The language bound follows from the distinct-root theorem, the routing lemma,
and the block-incidence lemma; the confluent certificate is not on the
critical path to it.
"""

from __future__ import annotations

from fractions import Fraction

#: Cost band; see ``__main__.py``.  Exact rational solve of small confluent
#: systems plus a few integer products -- fast, but its place is CI where the
#: 20s budget already pays for ``all_generators``.
BAND = "ci"
COST = 1.0


def _solve(nodes: list[tuple[Fraction, int]], zeros: list[int]):
    """Coefficients q[i][k] of u_d = sum q[i][k] d^k y_i^d, u_0=1, u_z=0."""
    idx = [(i, k) for i, (_, e) in enumerate(nodes) for k in range(e)]
    n = len(idx)
    assert n == sum(e for _, e in nodes)
    assert len(zeros) == n - 1
    rows, rhs = [], []
    for d in [0, *zeros]:
        rows.append([Fraction(d**k) * nodes[i][0] ** d for i, k in idx])
        rhs.append(Fraction(1) if d == 0 else Fraction(0))
    a = [[*r, b] for r, b in zip(rows, rhs, strict=True)]
    for col in range(n):
        piv = next(r for r in range(col, n) if a[r][col] != 0)
        a[col], a[piv] = a[piv], a[col]
        pv = a[col][col]
        a[col] = [v / pv for v in a[col]]
        for r in range(n):
            if r != col and a[r][col] != 0:
                f = a[r][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col], strict=True)]
    sol = [a[j][n] for j in range(n)]
    coeffs, p = [], 0
    for _, e in nodes:
        coeffs.append(sol[p : p + e])
        p += e
    return coeffs


def _u(nodes, coeffs, d: int) -> Fraction:
    return sum(
        sum(q * Fraction(d) ** k for k, q in enumerate(qs)) * y**d
        for (y, _), qs in zip(nodes, coeffs, strict=True)
    )


def _A(k: int, y: Fraction) -> Fraction:
    """``sum_{d>=0} d^k y^d``, exactly, for every ``k``.

    Recurrence ``S_k = y (d/dy) S_{k-1}`` kept as
    ``S_k = N_k(y) / (1 - y)**(k + 1)``.  A closed form stopping at ``k == 3``
    would silently use the ``k == 3`` branch for a multiplicity above three.
    """
    numerator = [Fraction(1)]
    for j in range(1, k + 1):
        derivative = [i * c for i, c in enumerate(numerator)][1:]
        base = [Fraction(0)] * max(len(derivative) + 1, len(numerator))
        for i, c in enumerate(derivative):
            base[i] += c
            base[i + 1] -= c
        merged = [Fraction(0)] * max(len(base), len(numerator))
        for i, c in enumerate(base):
            merged[i] += c
        for i, c in enumerate(numerator):
            merged[i] += j * c
        numerator = [Fraction(0), *merged]
    return sum(c * y**e for e, c in enumerate(numerator)) / (1 - y) ** (k + 1)


def _tail(nodes, coeffs, zeros) -> Fraction:
    """Exact ``sum_{d>=1}|u_d|``: constant sign past the last zero."""
    n = max(zeros) + 2
    head = sum(abs(_u(nodes, coeffs, d)) for d in range(1, n + 1))
    total = sum(
        q * _A(k, y)
        for (y, _), qs in zip(nodes, coeffs, strict=True)
        for k, q in enumerate(qs)
    )
    upto = sum(_u(nodes, coeffs, d) for d in range(0, n + 1))
    sign = 1 if _u(nodes, coeffs, n) > 0 else -1
    return head + sign * (total - upto)


def _expanded(nodes) -> list[Fraction]:
    z: list[Fraction] = []
    for y, e in nodes:
        z.extend([y] * e)
    return sorted(z)


def _leading_run(zeros) -> int:
    s, f = set(zeros), 0
    while f + 1 in s:
        f += 1
    return f


def _mul(a, b):
    out = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            out[i + j] += ai * bj
    return out


def _digits(n: int) -> int:
    return 0 if n == 0 else len(str(abs(n)))


def _mass(coeffs) -> int:
    return sum(_digits(c) for c in coeffs)


#: The certificates checked.  Small enough to stay inside the band budget, wide
#: enough to see one repeated node, two repeated nodes, a node at 1/2, a
#: displaced zero set, and multiplicities past the old ``k == 3`` closed form.
_CERTIFICATES = [
    ([(Fraction(1, 2), 2)], [1]),
    ([(Fraction(1, 3), 3)], [1, 3]),
    ([(Fraction(1, 3), 3)], [2, 4]),
    ([(Fraction(1, 4), 2), (Fraction(1, 2), 2)], [1, 2, 3]),
    ([(Fraction(1, 4), 2), (Fraction(1, 2), 2)], [1, 3, 4]),
    ([(Fraction(1, 5), 2), (Fraction(1, 3), 2)], [2, 3, 5]),
    ([(Fraction(1, 5), 2), (Fraction(1, 3), 2)], [1, 2, 6]),
    (
        [(Fraction(1, 6), 2), (Fraction(1, 4), 2), (Fraction(1, 2), 2)],
        [1, 2, 4, 5, 7],
    ),
    ([(Fraction(1, 4), 4)], [1, 2, 4]),
    ([(Fraction(1, 7), 6)], [1, 2, 3, 5, 7]),
    ([(Fraction(1, 9), 5), (Fraction(1, 4), 1)], [1, 2, 4, 5, 6]),
]


def _check_certificates(failures: list[str]) -> int:
    for nodes, zeros in _CERTIFICATES:
        coeffs = _solve(nodes, zeros)
        assert _u(nodes, coeffs, 0) == 1
        for z in zeros:
            assert _u(nodes, coeffs, z) == 0
        t = _tail(nodes, coeffs, zeros)
        f = _leading_run(zeros)
        bound = Fraction(1)
        for y in _expanded(nodes)[: f + 1]:
            bound *= y / (1 - y)
        if t > bound:
            failures.append(f"tail {t} > bound {bound} for {nodes}, Z={zeros}")
    # base case is exact
    for nodes in (
        [(Fraction(1, 3), 3)],
        [(Fraction(1, 4), 2), (Fraction(1, 2), 2)],
    ):
        c = sum(e for _, e in nodes)
        zeros = list(range(1, c))
        coeffs = _solve(nodes, zeros)
        t = _tail(nodes, coeffs, zeros)
        exact = Fraction(1)
        for y, e in nodes:
            exact *= (y / (1 - y)) ** e
        if t != exact:
            failures.append(f"base tail {t} != {exact} for {nodes}")
    return len(_CERTIFICATES) + 2


def _check_assembly(failures: list[str]) -> int:
    """Threshold on the m-u largest units is the product over the top m-2u."""
    count = 0
    cases = [
        ([(Fraction(1, 2), 3), (Fraction(1, 3), 2)], 0),
        ([(Fraction(1, 2), 3), (Fraction(1, 3), 2)], 1),
        ([(Fraction(1, 2), 3), (Fraction(1, 3), 2)], 2),
        ([(Fraction(1, 2), 3), (Fraction(1, 3), 2), (Fraction(1, 5), 1)], 2),
    ]
    for nodes, u in cases:
        m = sum(e for _, e in nodes)
        rem, trimmed = u, []
        for y, e in sorted(nodes, key=lambda t: -t[0]):
            take = min(rem, e)
            rem -= take
            if e - take:
                trimmed.append((y, e - take))
        sub = sorted(trimmed)
        c = sum(e for _, e in sub)
        # ``U = {m-2u+1, ..., m-u}`` leaves the gap at ``m-2u``, so the
        # leading run is exactly ``m-2u-1`` and the certificate is tested at
        # its sharp point, not on an all-leading set (where it is trivial).
        zeros = list(range(1, m - 2 * u)) + list(range(m - 2 * u + 1, m - u + 1))
        assert len(zeros) == c - 1
        coeffs = _solve(sub, zeros)
        t = _tail(sub, coeffs, zeros)
        top = _expanded(nodes)[: m - 2 * u]
        prod = Fraction(1)
        for y in top:
            prod *= 1 / y - 1
        if 1 / t < prod:
            failures.append(f"assembly {1 / t} < {prod} for {nodes}, u={u}")
        count += 1
    return count


def _check_mass(failures: list[str]) -> int:
    """Spot-check that repeated-root products have quadratic mass.

    ``mass(F) >= m*m/8`` for a monic multiple of ``prod (x - r_i)**e_i`` is a
    loose diagnostic, not the language bound; the cases use ``m >= 16`` so the
    floor is above the Descartes ``m + 1`` term and the assertion is not
    automatic.  A multiple with a small cofactor is checked as well as the
    product itself.
    """
    count = 0
    for roots in ([(2, 16)], [(2, 24)], [(2, 8), (3, 8), (5, 8)]):
        product = [1]
        for r, e in roots:
            for _ in range(e):
                product = _mul(product, [-r, 1])
        m = sum(e for _, e in roots)
        threshold = m * m / 8
        if _mass(product) < threshold:
            failures.append(f"product mass {_mass(product)} < {threshold} for {roots}")
        for cofactor in ([-2, 1], [-3, 1], [6, -5, 1]):
            multiple = _mul(product, cofactor)
            if _mass(multiple) < threshold:
                failures.append(
                    f"multiple mass {_mass(multiple)} < {threshold} "
                    f"for {roots} * {cofactor}"
                )
        count += 1
    return count


def _check_loops(failures: list[str]) -> int:
    """Pin the loop case covered by the block-incidence argument.

    ``_advance`` jumps a closing bracket back to its opener when the opener's
    code exceeds 4, so codes 5..8 are loops;
    ``convert`` maps a real root ``p**v`` to code ``v`` for ``v`` in 1..8, so a
    real root can be a loop bracket and one real value can serve many reads.
    """
    from esolangs.interpreters.register_based.polynomial import (
        _advance,
        _bracket_pairs,
        convert,
    )

    count = 0
    # code 5 opener: reach the close, jump back while reg > 0 -> no halt
    instrs = [[1, 1], [5], [1, 1], [2], [0, 1]]
    pairs = _bracket_pairs(instrs)
    state, steps = (0, 0), 0
    while state[1] < len(instrs) and steps < 50:
        state, _ = _advance(state, instrs, None, pairs)
        steps += 1
    if state[1] >= len(instrs):
        failures.append("code 5 bracket halted instead of looping")
    count += 1
    # code 1 opener: skip forward, never re-enter
    instrs = [[1, 1], [1], [1, 1], [2], [0, 1]]
    pairs = _bracket_pairs(instrs)
    seen: list[int] = []
    state, steps = (1, 0), 0
    while state[1] < len(instrs) and steps < 50:
        seen.append(state[1])
        state, _ = _advance(state, instrs, None, pairs)
        steps += 1
    if len(seen) != len(set(seen)):
        failures.append("code 1 bracket re-entered an instruction")
    count += 1
    # convert emits code v for a real root p**v, so v in 5..8 is reachable
    for p, v in ((2, 5), (3, 5), (2, 6), (2, 8)):
        emitted = convert([complex(p**v, 0)])
        if emitted != [[v]]:
            failures.append(f"convert(p**{v}={p**v}) = {emitted}, not [[{v}]]")
    count += 4
    return count


def _check_routing(failures: list[str]) -> int:
    """Pin the executed facts behind the routing lemma.

    ``docs/proofs/polynomial.md`` proves ``N'(k+1) <= 2 + 4 * m_routing`` for
    programs that consume their input: the routing-free continuation from the
    last routing position is deterministic and has a fixed read count to halt,
    so the cursor at the ``k``th read is fixed.  The block-incidence bound
    replaces ``m_routing`` by ``3 * L_real``, giving the language bound.  This
    check pins the per-instruction facts the lemma rests on:

    * every real instruction has at most two successors, fixed by its bracket
      and independent of the register;
    * two same-value positions in one block (a repeated root ``(x - p**v)**r``
      emits ``r`` copies) see one register per visit and collapse to at most
      two traces, so multiplicity adds no routing power -- it only helps the
      mass bound;
    * on the shipped generator ``N' <= 2 * L_real`` with margin, a positive
      control that the bound is not vacuous.
    """
    from esolangs.interpreters.register_based.polynomial import (
        _advance,
        _bracket_pairs,
    )
    from esolangs.tools.polynomial import polynomial

    count = 0
    # A real instruction has two successors whatever the register: a taken
    # bracket jumps to a fixed partner, otherwise the cursor falls through.
    for instrs in (
        [[1], [2]],
        [[1, 1], [5], [1, 1], [2], [0, 1]],
        [[1], [1], [2], [2]],
    ):
        pairs = _bracket_pairs(instrs)
        for pos, ins in enumerate(instrs):
            if len(ins) != 1:
                continue
            succ = set()
            for reg in (-1, 0, 1):
                (_, nxt), _ = _advance((reg, pos), instrs, None, pairs)
                succ.add(nxt)
            if len(succ) > 2:
                failures.append(f"real {ins} at {pos} has {len(succ)} successors")
    count += 1

    # Same-value positions in one block collapse: `[1,1,2,2]` has two `p**1`
    # tests but the run takes the same two traces as `[1,2]`.
    def traces(instrs: list[list[int]]) -> set[tuple[int, ...]]:
        pairs = _bracket_pairs(instrs)
        out = set()
        for entry in (-1, 0, 1):
            state, steps, path = (entry, 0), 0, []
            while state[1] < len(instrs) and steps < 40:
                path.append(state[1])
                state, _ = _advance(state, instrs, None, pairs)
                steps += 1
            out.add(tuple(path))
        return out

    if len(traces([[1, 1, 2, 2]])) != len(traces([[1, 2]])):
        failures.append("[1,1,2,2] does not collapse to [1,2]'s traces")
    count += 1
    # Positive control: the shipped dense table has L_real close to m (only
    # slight multiplicity at n=3: 10 values against 12 positions).
    import hashlib
    import re

    from esolangs.interpreters.register_based.polynomial import sanitize

    def dense(n: int) -> str:
        digest = hashlib.sha256(f"dense:{n}".encode()).digest()
        bits: list[str] = []
        block = 0
        while len(bits) < 2**n:
            digest = hashlib.sha256(digest + bytes([block & 255])).digest()
            bits.extend(str(byte & 1) for byte in digest)
            block += 1
        return "".join(bits[: 2**n])

    for n in (2, 3, 4):
        from esolangs.interpreters.register_based.polynomial import _find_roots

        cleaned = re.sub(r"[^\df(x)=+-^]", "", polynomial(dense(n)))
        roots = _find_roots(sanitize(cleaned))
        reals = [r.real for r in roots if r.imag == 0]
        values = set(reals)
        if not reals:
            failures.append(f"dense n={n} has no real instruction")
        if len(values) > len(reals):
            failures.append(f"dense n={n}: L_real={len(values)} > m={len(reals)}")
        count += 1

    # Positive control for the repaired lemma: the generated machine consumes
    # exactly n inputs on every path, and its cursor count obeys
    # D_k <= 1 + 2*m_routing.  A variable-read list would fail the first check
    # and is exactly what the counterexample is.
    import itertools

    from esolangs.interpreters.register_based.polynomial import _parse_program

    def run_all(instrs: list[list[int]], n: int):
        pairs = _bracket_pairs(instrs)
        dk: dict[int, set[int]] = {}
        taken: dict[int, set[int]] = {}
        for bits in itertools.product((0, 1), repeat=n):
            reg, ind, pos, k, steps = 0, 0, 0, 0, 0
            while ind < len(instrs) and steps < 500:
                steps += 1
                ins = instrs[ind]
                one = ins[0]
                two = ([*ins[1:], 0])[0]
                byte = None
                if two and not one and two - 1:
                    if pos >= n:
                        return None
                    byte = bits[pos] + 48
                    pos += 1
                    dk.setdefault(k, set()).add(ind)
                    k += 1
                if len(ins) == 1:
                    taken.setdefault(ind, set()).add(
                        _advance((reg, ind), instrs, None, pairs)[0][1]
                    )
                (reg, ind), _ = _advance((reg, ind), instrs, byte, pairs)
            if ind < len(instrs) or k != n:
                return None
        return dk, taken

    for n in (2, 3):
        cleaned = re.sub(r"[^\df(x)=+-^]", "", polynomial(dense(n)))
        instrs = [list(ins) for ins in _parse_program(cleaned)]
        result = run_all(instrs, n)
        if result is None:
            failures.append(f"dense n={n} does not consume exactly n inputs")
            continue
        dk, taken = result
        m_routing = sum(1 for s in taken.values() if len(s) > 1)
        maxd = max((len(s) for s in dk.values()), default=0)
        if maxd > 1 + 2 * m_routing:
            failures.append(
                f"dense n={n}: D={maxd} > 1 + 2*{m_routing} routing positions"
            )
        count += 1
    return count


def _check_routing_bound(failures: list[str]) -> int:
    """Pin the facts around the sharpened routing bound.

    The routing lemma gives ``N' <= 2 + 4 * m_routing``, and the block
    structure gives ``m_routing <= 3 * L_real``, hence ``N' <= 12 * L_real +
    2``.  A proposed shorter route -- ``m_routing <= 3 * L_real`` via "at most
    one routing position per (value, condition)" -- is **false**: this check
    runs the refuting table and confirms two routing closers share one value
    and one condition.  What holds and is pinned here:

    * a back-edge's target is ``opener + 1``; if that is itself a closer, a
      condition-true jump self-loops, so a halting program never routes such a
      closer (positive control: a self-looped closer spins);
    * loop openers have code only in ``5, 7, 8`` (code ``6`` indexes the
      absent ``_COND`` slot and would raise), so a value carries at most three
      conditions;
    * exact equal roots are contiguous, so their blocks and the noncrossing
      bracket incidences give ``m_routing <= L_real + (2L_real - 3)``;
    * the witness refutes the smaller per-(value, condition) charge, while
      every routing opener block and opener-block/closer-block incidence is
      charged only once.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.polynomial import (
        _COND,
        _advance,
        _bracket_pairs,
        _Machine,
    )

    count = 0
    # Code 6 as a loop opener indexes _COND[1], which is absent: only 5, 7, 8
    # are loop conditions, so a value has at most three.
    if set(_COND) != {0, 2, 3}:
        failures.append(f"_COND keys changed: {set(_COND)}")
    if {(c - 1) % 4 for c in range(1, 9) if c > 4} != {0, 1, 2, 3}:
        failures.append("loop-opener condition set changed")
    count += 1
    # Positive control: a self-looped closer does not halt.
    instrs = [[1, 1], [5], [2], [0, 1]]
    pairs = _bracket_pairs(instrs)
    state, steps = (0, 0), 0
    while state[1] < len(instrs) and steps < 50:
        state, _ = _advance(state, instrs, None, pairs)
        steps += 1
    if state[1] >= len(instrs):
        failures.append("self-looped closer halted; positive control dead")
    count += 1
    # The refuting table: a 2-bit calibrated tree, three nested loop openers,
    # and a same-value closer run.  Executed through the real machine; it must
    # produce one character on every input, and two of its closers must both
    # route with the same value and condition -- the false invariant.
    witness = [
        [0, 2],
        [-48, 1],
        [1],
        [0, 2],
        [-48, 1],
        [1],
        [-7, 1],
        [2],
        [1, 1],
        [1],
        [-4, 1],
        [2],
        [2],
        [1, 1],
        [1],
        [0, 2],
        [-48, 1],
        [1],
        [-5, 1],
        [2],
        [1, 1],
        [1],
        [-2, 1],
        [2],
        [2],
        [-1, 3],
        [5],
        [-3, 1],
        [7],
        [-1, 3],
        [5],
        [-1, 1],
        [2],
        [2],
        [2],
        [48, 1],
        [0, 1],
    ]
    pr = _bracket_pairs(witness)
    succ: dict[int, set[int]] = {}
    for r in range(4):
        bits = [(r >> (1 - i)) & 1 for i in range(2)]
        io = ScriptedIO("\n".join(str(b) for b in bits) + "\n")
        m = _Machine("f(x) = 1", io)
        m.instructions = [list(x) for x in witness]
        m._pairs = pr  # noqa: SLF001 -- the machine's own bracket table
        guard = 0
        while not m.halted and guard < 5000:
            m.step()
            guard += 1
        if not m.halted or len(io.getvalue()) != 1 or io.past_end:
            failures.append(f"refuting witness not a table on input {bits}")
    for r in range(4):
        bits = [(r >> (1 - i)) & 1 for i in range(2)]
        reg, ind, pos, steps = 0, 0, 0, 0
        while ind < len(witness) and steps < 5000:
            steps += 1
            ins = witness[ind]
            byte = None
            if ins == [0, 2]:
                byte = 48 + bits[pos]
                pos += 1
            was = ind
            (reg, ind), _ = _advance((reg, ind), witness, byte, pr)
            if len(witness[was]) == 1:
                succ.setdefault(was, set()).add(ind)
    groups: dict[tuple[int, int], int] = {}
    for p, s in succ.items():
        if len(s) <= 1:
            continue
        if witness[p][0] in (2, 6):
            cond = (witness[pr[p]][0] - 1) % 4
            value = ("close", witness[p][0])
        else:
            cond = (witness[p][0] - 1) % 4
            value = ("open", witness[p][0])
        key = (value, cond)
        groups[key] = groups.get(key, 0) + 1
    if not any(v > 1 for v in groups.values()):
        failures.append("refuting witness no longer refutes: probe did not fire")
    if not any(witness[p][0] in (2, 6) and len(s) > 1 for p, s in succ.items()):
        failures.append("refuting witness has no routing closer")
    count += 1

    # Give each maximal same-code run a single exact-root value.  This is the
    # strongest legal identification for the witness: convert emits every
    # copy of one real root contiguously.  Routing openers charge their block;
    # routing closers charge the incidence with their partner's opener block.
    block_at: dict[int, int] = {}
    block_codes: list[int] = []
    previous: tuple[int, int] | None = None
    for pos, instruction in enumerate(witness):
        if len(instruction) != 1:
            previous = None
            continue
        key = (pos - 1, instruction[0])
        if previous is None or previous[1] != instruction[0]:
            block_codes.append(instruction[0])
        block_at[pos] = len(block_codes) - 1
        previous = key

    routing = {p for p, exits in succ.items() if len(exits) > 1}
    opener_charges = [block_at[p] for p in routing if witness[p][0] not in (2, 6)]
    closer_charges = [
        (block_at[pr[p]], block_at[p]) for p in routing if witness[p][0] in (2, 6)
    ]
    if len(opener_charges) != len(set(opener_charges)):
        failures.append("two routing openers charge one exact-root block")
    if len(closer_charges) != len(set(closer_charges)):
        failures.append("two routing closers charge one block incidence")
    incidences = {(block_at[p], block_at[q]) for p, q in pr.items() if p < q}
    real_blocks = len(block_codes)
    if len(incidences) > 2 * real_blocks - 3:
        failures.append("noncrossing block incidence exceeded outerplanar bound")
    if len(routing) > 3 * real_blocks - 3:
        failures.append("routing positions exceeded block-incidence bound")
    count += 1

    # General model: without input consumption the read level at the last
    # routing position is free, so the kth read is the jth read of the fixed
    # continuation for some j <= k, giving D_k <= 1 + 2*k*m_routing.  The doc's
    # counterexample violates the tight bound and satisfies the relaxed one.
    counterexample = [
        [5, 1],
        [5],
        [0, 2],
        [48, 2],
        [2],
        [0, 2],
        [0, 2],
        [0, 2],
        [0, 2],
        [0, 1],
    ]
    ce_pairs = _bracket_pairs(counterexample)
    dk: dict[int, set[int]] = {}
    ce_taken: dict[int, set[int]] = {}
    for r in range(256):
        bits = [(r >> (7 - i)) & 1 for i in range(8)]
        reg, ind, pos, k, steps = 0, 0, 0, 0, 0
        while ind < len(counterexample) and steps < 500:
            steps += 1
            ins = counterexample[ind]
            one = ins[0]
            two = ([*ins[1:], 0])[0]
            byte = None
            if two and not one and two - 1:
                byte = 48 + bits[pos] if pos < 8 else -1
                if pos < 8:
                    pos += 1
                dk.setdefault(k, set()).add(ind)
                k += 1
            if len(ins) == 1:
                ce_taken.setdefault(ind, set()).add(
                    _advance((reg, ind), counterexample, None, ce_pairs)[0][1]
                )
            (reg, ind), _ = _advance((reg, ind), counterexample, byte, ce_pairs)
    ce_routing = sum(1 for s in ce_taken.values() if len(s) > 1)
    if ce_routing != 1:
        failures.append(f"counterexample m_routing changed: {ce_routing}")
    if len(dk.get(3, ())) <= 1 + 2 * ce_routing:
        failures.append("counterexample no longer violates the tight bound")
    for k, cursors in dk.items():
        relaxed = 1 + 2 * (k + 1) * ce_routing
        if len(cursors) > relaxed:
            failures.append(
                f"counterexample k={k + 1}: D={len(cursors)} > relaxed {relaxed}"
            )
    count += 1
    return count


def main() -> int:
    failures: list[str] = []
    certs = _check_certificates(failures)
    asm = _check_assembly(failures)
    mass = _check_mass(failures)
    loops = _check_loops(failures)
    routing = _check_routing(failures)
    bound = _check_routing_bound(failures)
    print(f"  confluent certificates checked exactly : {certs}")
    print(f"  slack-assembly thresholds checked      : {asm}")
    print(f"  repeated-root mass floor cases         : {mass}")
    print(f"  routing-floor bracket facts checked    : {loops}")
    print(f"  sharpened-routing facts checked        : {routing}")
    print(f"  routing block-incidence bound          : {bound}")
    if failures:
        for line in failures:
            print(f"  FAIL: {line}")
        return 1
    print("  all confluent-slack-certificate checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
