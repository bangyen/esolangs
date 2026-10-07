"""Covers :mod:`esolangs.tools.slow_acv_mammalian`."""

import random
from functools import cache
from math import gcd

import pytest

from esolangs import tools as boolean
from esolangs.tools.slow_acv_mammalian import (
    _greedy_advance,
    _stash_chunk,
    _Sums,
    _trampoline,
    _trampoline_len,
    _w_raise,
    _w_raise_len,
)
from tests.witness_tables import witnesses


class TestSlowAcvMammalian:
    """The decision tree LEAPFROG makes possible."""

    def test_constant_tables_still_read_every_input(self) -> None:
        """A constant table consumes all ``n`` inputs."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        for table in ("0000", "1111", "0110"):
            program = boolean.slow_acv_mammalian(table)
            assert program.split().count("ACCEPT") == 2  # one per input
            io_obj = ScriptedIO("0\n" * 8)
            run_until_halt_or_cycle(_Machine(program, io_obj))
            assert io_obj.position() == 2

    def test_routing_is_accounted_for_array_by_array(self) -> None:
        """Every ``SPRINT`` belongs to a named errand, and none is spare."""
        for table, n, pools in (("01", 1, 0), ("0110", 2, 1), ("01101001", 3, 2)):
            tokens = boolean.slow_acv_mammalian(table).split()
            arms = 2 * (n - pools) + 3 * pools
            assert tokens.count("SPRINT") == 4 + 2 * pools + 2 + arms + 1 + len(table)
            assert "CONFLAGRATE" not in tokens

    def test_a_node_opens_the_accumulator_on_a_clean_digit(self) -> None:
        """``ACCEPT`` is entered with ``acc % 256 == 48``, whatever the state."""
        from esolangs.tools.slow_acv_mammalian import _node

        for array, acc in (
            ([0], 0),
            ([3, 255, 255], 0),
            ([200, 17, 9], 128),
            ([254, 1, 77, 30], 99999),
        ):
            _, fell, taken, _ = _node(list(array), acc)
            assert (fell[1] ^ sum(fell[0])) % 256 == 48
            assert (taken[1] ^ sum(taken[0])) % 256 == 48

    def test_the_landing_is_start_minus_15(self) -> None:
        """A 1-bit resumes exactly 15 tokens short of the array sum."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.slow_acv_mammalian import _node, _seeded

        for array, acc in (([3, 255, 255, 255], 7), ([90, 200, 200, 255], 4242)):
            tokens, _, taken, landing = _node(list(array), acc)
            wrap = (256 - array[0]) % 256
            start = sum([*_seeded(array, wrap), acc % 256])
            assert landing == start - 15
            padded = [*tokens, *["SEED"] * (landing + 2 - len(tokens))]
            machine = _Machine(" ".join(padded), ScriptedIO("1\n"), io_modulus=256)
            machine.lst = (tuple(array), *machine.lst[1:])
            machine.acc = acc
            while not machine.halted and machine.ind < len(tokens):
                machine.step()
            assert machine.ind == landing
            assert list(machine.lst[0]) == taken[0]
            assert machine.acc == taken[1]

    def test_the_trampoline_jump_ignores_the_head(self) -> None:
        """The trampoline lands on its target from any head value."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.slow_acv_mammalian import _trampoline

        target = 900
        for head in (0, 130, 255):
            array = [head, 255, 255, 200]
            tokens, out_array, out_acc = _trampoline(list(array), 5000, target)
            padded = [*tokens, *["SEED"] * (target + 2 - len(tokens))]
            machine = _Machine(" ".join(padded), ScriptedIO(""), io_modulus=256)
            machine.lst = (tuple(array), *machine.lst[1:])
            machine.acc = 5000
            while not machine.halted and machine.ind < len(tokens):
                machine.step()
            assert machine.ind == target, f"head {head}"
            assert list(machine.lst[0]) == out_array
            assert machine.acc == out_acc

    def test_the_shortest_hop_still_fires(self) -> None:
        """A hop of one token appends ``b == 1``, the least firing byte."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.slow_acv_mammalian import _trampoline

        array = [5, 255, 255, 255]
        target = sum(array) - array[0] + 1
        tokens, out_array, _ = _trampoline(list(array), 0, target)
        assert out_array[-1] == 1
        machine = _Machine(
            " ".join([*tokens, *["SEED"] * (target + 2 - len(tokens))]),
            ScriptedIO(""),
            io_modulus=256,
        )
        machine.lst = (tuple(array), *machine.lst[1:])
        while not machine.halted and machine.ind < len(tokens):
            machine.step()
        assert machine.ind == target

    def test_only_the_construction_s_own_opcodes_appear(self) -> None:
        """Eight opcodes, and ``FISSION`` is not one of them."""
        program = boolean.slow_acv_mammalian("0110")
        used = set(program.split())
        assert used == {
            "SEED",
            "EXCRETE",
            "DIGEST",
            "ACCEPT",
            "PRONOUNCE",
            "LEAPFROG",
            "SPRINT",
            "CONSUME",
        }

    def test_a_pooled_weight_is_blind_to_what_array_16_holds(self) -> None:
        """The pool banks its byte from any starting sum, unchanged."""
        import importlib

        module = importlib.import_module("esolangs.tools.slow_acv_mammalian")
        banked = set()
        for offset in (0, 1, 17, 255, 256, 4097):
            st = module._Sums()  # noqa: SLF001
            _ = module._build_pool(st, 32, 4)  # noqa: SLF001
            st.nw += offset
            before = st.nw
            module._pool_bank(st, 32, 4)  # noqa: SLF001
            banked.add(st.nw - before)
        assert banked == {32}

    @pytest.mark.parametrize("amount", [0, 100, 256, 600, 2000])
    def test_a_weight_raise_is_exact_on_the_machine(self, amount: int) -> None:
        """``_w_raise`` moves array 16's non-head sum by exactly its ask."""
        import importlib

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        module = importlib.import_module("esolangs.tools.slow_acv_mammalian")
        st = module._Sums()  # noqa: SLF001
        st.ptr, st.hw, st.nw = 16, 9, 255
        tokens = module._w_raise(st, amount)  # noqa: SLF001
        machine = _Machine(" ".join(tokens), ScriptedIO(""), io_modulus=256)
        machine.ptr = 16
        machine.lst = tuple((9, 200, 55) if k == 16 else (0,) for k in range(23))
        while not machine.halted:
            machine.step()
        array = machine.lst[16]
        assert sum(array) - array[0] == 255 + amount
        assert (st.nw, st.hw) == (255 + amount, array[0])

    def test_the_dispatch_lands_every_row_on_its_own_leaf(self) -> None:
        """Each run halts inside the leaf slot its inputs selected."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.slow_acv_mammalian import _LEAF_UNIT, _weights

        table = "01101001"
        program = boolean.slow_acv_mammalian(table)
        tokens = program.split()
        leaf_base = len(tokens) - _LEAF_UNIT * len(table)
        weights = _weights(3)
        for row in range(8):
            bits = [(row >> (2 - i)) & 1 for i in range(3)]
            machine = _Machine(program, ScriptedIO("".join(f"{b}" for b in bits)))
            while not machine.halted:
                machine.step()
            banked = sum(w for w, b in zip(weights, bits, strict=True) if b)
            assert machine.ind - leaf_base - banked in range(_LEAF_UNIT)

    def test_the_emitted_size_is_pinned_and_linear(self) -> None:
        """Exact sizes per arity, and the leaf table is the whole growth."""
        tables = ("01", "0110", "01101001")
        sizes = [len(boolean.slow_acv_mammalian(table)) for table in tables]
        assert sizes == [11_451, 20_253, 26_326]
        sizes = [
            len(boolean.slow_acv_mammalian(table, io_modulus=256)) for table in tables
        ]
        assert sizes == [13_276, 23_330, 28_055]

    def test_a_slot_is_the_same_width_for_either_digit(self) -> None:
        """The table's stride is a leaf, and a leaf does not read the sum."""
        sizes = {
            len(boolean.slow_acv_mammalian(table))
            for table in ("0000", "1111", "0110", "1001", "0111")
        }
        assert len(sizes) == 1


class TestFastLanding:
    """The O(1) sizing helpers agree with the O(weight) builds they replace."""

    @pytest.mark.parametrize(
        ("hw0", "nw0", "amount"),
        [
            (0, 0, 0),  # no raise at all
            (5, 100, 10),  # inside the two exact chunks, no greedy phase
            (5, 100, 1_000),  # a handful of greedy chunks, no cycle
            (200, 50_000, 5_000_000),  # forces a residue cycle
            (1, 1, 10**7),  # forces a residue cycle from a different start
        ],
    )
    def test_w_raise_len_matches_the_real_build(
        self, hw0: int, nw0: int, amount: int
    ) -> None:
        st = _Sums()
        st.hw, st.nw, st.ptr = hw0, nw0, 16
        real_tokens = _w_raise(st, amount)

        fast_len, fast_hw = _w_raise_len(hw0, nw0, amount)
        assert fast_len == len(real_tokens)
        assert fast_hw == st.hw

    def test_greedy_advance_cycle_matches_a_full_walk(self) -> None:
        """A target past 256 chunks must exercise the cycle-jump branch."""
        _, chunks, advance, final_r = _greedy_advance(17, 10**6)
        assert chunks > 256  # otherwise this case is not testing the jump
        assert advance >= 10**6

        # Cross-check against the slow reference the construction ships.
        st = _Sums()
        st.hw, st.nw, st.ptr = 0, 17, 16
        _w_raise(st, 10**6 + 510)
        assert (st.hw + st.nw) % 256 == final_r

    @pytest.mark.parametrize(
        ("h0", "n0", "acc", "target"),
        [
            (5, 0, 0, 1),  # zero chunks: the initial gap already fits
            (5, 10, 4, 20),  # one chunk
            (5, 10, 4, 500),  # two chunks
            (5, 10, 4, 100_000),  # past two chunks: the closed-form tail
            (200, 50_000, 999, 300_000),  # a longer closed-form tail
        ],
    )
    def test_trampoline_len_matches_the_real_build(
        self, h0: int, n0: int, acc: int, target: int
    ) -> None:
        array = [h0, n0]
        real_tokens, _, _ = _trampoline(array, acc, target)
        assert _trampoline_len(array, acc, target) == len(real_tokens)

    def test_trampoline_stash_chunk_count_is_one_past_the_second(self) -> None:
        """The closed-form tail's premise, pinned directly."""
        array, acc = [11, 23], 7
        counts = []
        for _ in range(6):
            chunk, array, acc = _stash_chunk(array, acc)
            counts.append(len(chunk) - 2)
        assert counts[2:] == [1, 1, 1, 1]


def test_unreachable_arm_is_declined_but_invariants_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    from esolangs.tools import slow_acv_mammalian as generate

    module = importlib.import_module(generate.__module__)
    assert module._try_arm(_Sums(), _Sums(), 8, None, 0) is None  # noqa: SLF001
    assert module._try_arm(_Sums(), _Sums(), 8, None, 1000) is not None  # noqa: SLF001

    def broken(*_args: object) -> None:
        raise AssertionError("broken tuning invariant")

    monkeypatch.setattr(module, "_tune", broken)
    with pytest.raises(AssertionError, match="broken tuning invariant"):
        module._try_arm(_Sums(), _Sums(), 8, None, 1000)  # noqa: SLF001


def test_explicit_default_moduli_preserve_generation() -> None:
    from esolangs.tools.slow_acv_mammalian import slow_acv_mammalian

    baseline = slow_acv_mammalian("01")
    slow_acv_mammalian("01", io_modulus=256)
    assert slow_acv_mammalian("01", cell_modulus=256, io_modulus=255) == baseline


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"cell_modulus": 254}, "cell_modulus must be 255 or 256"),
        ({"io_modulus": 254}, "io_modulus must be 255 or 256"),
    ],
)
def test_generator_rejects_unverified_moduli(settings, message: str) -> None:
    from esolangs.tools.slow_acv_mammalian import slow_acv_mammalian

    with pytest.raises(ValueError, match=message):
        slow_acv_mammalian("01", **settings)


@pytest.mark.parametrize("table", witnesses(3)[:2])
@pytest.mark.parametrize("cell_modulus", [255, 256])
@pytest.mark.parametrize("io_modulus", [255, 256])
def test_moduli_generate_every_small_table(
    table: str, cell_modulus: int, io_modulus: int
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import run
    from esolangs.tools.slow_acv_mammalian import slow_acv_mammalian

    source = slow_acv_mammalian(table, cell_modulus=cell_modulus, io_modulus=io_modulus)
    n = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:0{n}b}")
        run(source, io, cell_modulus=cell_modulus, io_modulus=io_modulus)
        assert io.getvalue() == expected
        assert io.reads == n


@pytest.mark.medium
@pytest.mark.parametrize("n", [5])
@pytest.mark.parametrize("cell_modulus", [255, 256])
@pytest.mark.parametrize("io_modulus", [255, 256])
def test_moduli_generate_asymmetric_tables(
    n: int, cell_modulus: int, io_modulus: int
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import run
    from esolangs.tools.slow_acv_mammalian import slow_acv_mammalian

    rng = random.Random(20261003 + n)
    table = "".join(str(rng.getrandbits(1)) for _ in range(1 << n))
    source = slow_acv_mammalian(table, cell_modulus=cell_modulus, io_modulus=io_modulus)
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:0{n}b}")
        run(source, io, cell_modulus=cell_modulus, io_modulus=io_modulus)
        assert io.getvalue() == expected
        assert io.reads == n


# The public-generator sweep already executes compact chains above its switch
# arity. Keep direct coverage only for chains the public route does not choose.
@pytest.mark.parametrize(
    ("table", "modulus", "io_modulus"),
    [
        (table, modulus, io_modulus)
        for modulus in (255, 256)
        for io_modulus in (255, 256)
        for n in range(1, 4)
        if modulus == 256 or n < (3 if io_modulus == 255 else 2)
        for table in witnesses(n)[:2]
    ],
)
def test_coprime_chain_generates_every_small_table(
    table: str, modulus: int, io_modulus: int
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import run
    from esolangs.tools._mammalian_compact import compact_chain

    n = len(table).bit_length() - 1
    source = compact_chain(table, n, modulus=modulus, io_modulus=io_modulus)
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:0{n}b}")
        run(source, io, cell_modulus=modulus, io_modulus=io_modulus)
        assert io.getvalue() == expected
        assert io.reads == n


@pytest.mark.medium
@pytest.mark.parametrize("n", [5])
@pytest.mark.parametrize("io_modulus", [255, 256])
def test_coprime_chain_generates_asymmetric_tables(n: int, io_modulus: int) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import run
    from esolangs.tools._mammalian_compact import compact_chain

    rng = random.Random(20261003 + n)
    table = "".join(str(rng.getrandbits(1)) for _ in range(1 << n))
    source = compact_chain(table, n, modulus=256, io_modulus=io_modulus)
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:0{n}b}")
        run(source, io, cell_modulus=256, io_modulus=io_modulus)
        assert io.getvalue() == expected
        assert io.reads == n


def test_coprime_chain_rejects_backward_targets() -> None:
    from esolangs.tools._mammalian_compact import _Chain, _State

    chain = _Chain(255)
    with pytest.raises(ValueError, match="precedes"):
        chain.raise_to(_State(), -1)
    with pytest.raises(ValueError, match="precedes"):
        chain.jump(_State(), 0)


@pytest.mark.parametrize("modulus", [255, 256])
@pytest.mark.parametrize("io_modulus", [255, 256])
def test_chain_greedy_chunks_keep_their_short_continuation(
    modulus: int, io_modulus: int
) -> None:
    from esolangs.tools._mammalian_compact import _Chain, _State

    chain = _Chain(modulus, io_modulus=io_modulus)
    for head in range(modulus):
        for rest in range(io_modulus):
            state = _State(head=head, ptr=chain.weight)
            state.rest[chain.weight] = rest
            chain.seed(state, chain.greedy_seeds(state))
            value = (chain.head(state) + rest) % io_modulus
            assert value >= io_modulus - chain.step
            state.rest[chain.weight] += value
            assert chain.greedy_seeds(state) <= 2


@pytest.mark.parametrize("ptr", [0, 1])
@pytest.mark.parametrize("head", [0, 254])
@pytest.mark.parametrize("extra", [0, 512])
def test_mixed_chain_appends_all_missing_head_values(
    ptr: int, head: int, extra: int
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
    from esolangs.tools._mammalian_compact import _Chain, _State

    chain = _Chain(255, io_modulus=256)
    for value in range(256):
        rest = value + 1 + extra
        state = _State(head=head, ptr=ptr)
        state.rest[ptr] = rest
        tokens = chain.append(state, value)
        assert len(tokens) <= 2 * 254 + pow(ptr + 1, -1, 255) + 4
        machine = _Machine(
            " ".join(tokens), ScriptedIO(), cell_modulus=255, io_modulus=256
        )
        arrays = [((array + 1) * head % 255,) for array in range(23)]
        chunks, tail = divmod(rest, 254)
        arrays[ptr] += (*[254] * chunks, tail)
        machine.lst, machine.ptr = tuple(arrays), ptr
        for _ in tokens:
            machine.step()
        assert machine.lst[ptr][-1] == value
        assert sum(machine.lst[ptr][1:]) == state.rest[ptr] == rest + value
        assert machine.lst[ptr][0] == chain.head(state)
        assert machine.acc == state.acc == 0


@pytest.fixture(scope="module")
def stepped_chain_program():
    from esolangs.tools._mammalian_compact import compact_chain

    @cache
    def build(inputs: int, modulus: int, io_modulus: int):
        rng = random.Random(20261003 + inputs)
        table = "".join(str(rng.getrandbits(1)) for _ in range(1 << inputs))
        source = compact_chain(table, inputs, modulus=modulus, io_modulus=io_modulus)
        return table, source

    return build


@pytest.fixture(scope="module")
def native_pooled_program():
    rng = random.Random(20261009)
    table = "".join(str(rng.getrandbits(1)) for _ in range(64))
    return table, boolean.slow_acv_mammalian(table, io_modulus=255)


@pytest.mark.parametrize("modulus", [255, 256])
@pytest.mark.parametrize("io_modulus", [255, 256])
@pytest.mark.parametrize(
    ("inputs", "row"),
    # The first and last rows at each arity, and one between.
    [(4, 15), (6, 37)],
)
def test_coprime_chain_runs_in_stepped_interpreter(
    modulus: int, io_modulus: int, inputs: int, row: int, stepped_chain_program
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

    table, source = stepped_chain_program(inputs, modulus, io_modulus)
    token_count = len(source.split())
    io = ScriptedIO(f"{row:0{inputs}b}")
    machine = _Machine(source, io, cell_modulus=modulus, io_modulus=io_modulus)
    for _ in range(token_count):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert io.getvalue() == table[row]
    assert io.reads == inputs


@pytest.mark.parametrize("row", [0, 37, 63])
def test_native_255_pooled_blocks_in_stepped_interpreter(
    row: int, native_pooled_program
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

    table, source = native_pooled_program
    io = ScriptedIO(f"{row:06b}")
    machine = _Machine(source, io, io_modulus=255)
    for _ in range(len(source.split())):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert io.getvalue() == table[row]
    assert io.reads == 6


@pytest.mark.parametrize("modulus", [255, 256])
@pytest.mark.parametrize("io_modulus", [255, 256])
# The near corner, and the far one where every coordinate is large.
@pytest.mark.parametrize(
    ("head", "pos", "weight", "bit"), [(0, 0, 1, 0), (254, 65_536, 65_536, 1)]
)
def test_chain_regions_cover_distant_nodes_and_large_weights(
    modulus: int, io_modulus: int, head: int, pos: int, weight: int, bit: int
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
    from esolangs.tools._mammalian_compact import _Chain, _State

    chain = _Chain(modulus, io_modulus=io_modulus)
    state = _State(head=head, acc=io_modulus + 48)
    state.rest[chain.weight] = 3 * io_modulus + 17
    tokens, expected = chain.level(state.clone(), weight, pos, None)
    machine = _Machine(
        " ".join(["SEED"] * pos + tokens),
        ScriptedIO(str(bit)),
        cell_modulus=modulus,
        io_modulus=io_modulus,
    )
    maximum = io_modulus - 1
    machine.lst = []
    for array, rest in enumerate(state.rest):
        chunks, tail = divmod(rest, maximum)
        machine.lst.append(
            [
                (array + 1) * head % modulus,
                *[maximum] * chunks,
                *([tail] if tail else []),
            ]
        )
    machine.ind, machine.acc = pos, state.acc
    for _ in range(len(tokens) + 1):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert machine.acc == expected.acc
    expected.rest[chain.weight] += bit * weight
    for array, cells in enumerate(machine.lst):
        assert cells[0] == (array + 1) * expected.head % modulus
        assert sum(cells[1:]) == expected.rest[array]


@pytest.mark.parametrize("modulus", [255, 256])
@pytest.mark.parametrize("io_modulus", [255, 256])
# The smallest weight, a power of two, a non-power, the largest chunk, and -1
# for io_modulus - 1.
@pytest.mark.parametrize("weight", [1, 28, -1])
@pytest.mark.parametrize("compact", [False, True])
def test_compact_pool_retrieves_weight_and_routes(
    modulus: int, io_modulus: int, weight: int, *, compact: bool
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
    from esolangs.tools._mammalian_compact import _Chain, _State

    chain = _Chain(modulus, io_modulus=io_modulus)
    pool = chain.pools[-1]
    if weight == -1:
        weight = io_modulus - 1
    state = _State()
    tokens = chain.plant_pool(state, weight, pool, compact=compact)
    tokens += chain.route(state, pool)
    tokens += ["CONSUME", "SPRINT", "EXCRETE"]
    machine = _Machine(
        " ".join(tokens), ScriptedIO(), cell_modulus=modulus, io_modulus=io_modulus
    )
    for _ in tokens:
        machine.step()
    assert machine.ptr == chain.weight
    assert machine.acc == 0
    assert sum(machine.lst[chain.weight][1:]) == weight
    assert len(machine.lst[pool]) in (weight + 1, 2 * weight + 2)
    assert machine.lst[pool][0] == (pool + 1) * state.head % modulus
    assert sum(machine.lst[pool][1:]) == (chain.weight - pool) % 23


@pytest.mark.parametrize(("modulus", "budget"), [(255, 63_845), (256, 62_600)])
def test_pool_compaction_preserves_three_input_size(modulus: int, budget: int) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import run
    from esolangs.tools._mammalian_compact import compact_chain

    table = "00101101"
    source = compact_chain(table, 3, modulus=modulus)
    assert len(source) <= budget
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:03b}")
        run(source, io, cell_modulus=modulus, io_modulus=modulus)
        assert io.getvalue() == expected
        assert io.reads == 3


def test_cell_255_tree_rejects_backward_sum_targets() -> None:
    from esolangs.tools._mammalian255 import _State

    with pytest.raises(AssertionError, match="precedes"):
        _State(rest=1).raise_to(0)
    with pytest.raises(AssertionError, match="positive tail"):
        _State().jump(0)


@pytest.mark.parametrize("head", [0, 254])
@pytest.mark.parametrize("extra", [0, 512])
def test_cell_255_appends_every_value_with_a_missing_head(
    head: int, extra: int
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
    from esolangs.tools._mammalian255 import _State

    for value in range(255):
        rest = value + 1 + extra
        state = _State(head=head, rest=rest, io_modulus=256)
        tokens = state.append(value)
        machine = _Machine(
            " ".join(tokens), ScriptedIO(), cell_modulus=255, io_modulus=256
        )
        chunks, tail = divmod(rest, 254)
        machine.lst = ((head, *[254] * chunks, tail), *machine.lst[1:])
        for _ in tokens:
            machine.step()
        assert machine.lst[0][-1] == value
        assert sum(machine.lst[0][1:]) == state.rest == rest + value
        assert machine.lst[0][0] == state.head
        assert machine.acc == state.acc == 0


@pytest.mark.parametrize("io_modulus", [255, 256])
def test_cell_255_tree_runs_in_stepped_interpreter(io_modulus: int) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
    from esolangs.tools._mammalian255 import decision_tree

    table = "00101101"
    source = decision_tree(table, 3, io_modulus=io_modulus)
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:03b}")
        machine = _Machine(source, io, cell_modulus=255, io_modulus=io_modulus)
        for _ in range(len(source.split())):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert io.getvalue() == expected
        assert io.reads == 3


@pytest.mark.parametrize("head", [0, 255])
@pytest.mark.parametrize("acc", [0, 507])
@pytest.mark.parametrize("target", [700, 66000])
def test_modulo_255_trampoline_length_and_execution(
    head: int, acc: int, target: int
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
    from esolangs.tools.slow_acv_mammalian import _trampoline, _trampoline_len

    array = [head, 254]
    tokens, predicted, predicted_acc = _trampoline(array, acc, target, io_modulus=255)
    assert len(tokens) == _trampoline_len(array, acc, target, io_modulus=255)
    machine = _Machine(" ".join(tokens), ScriptedIO(), io_modulus=255)
    machine.lst = (tuple(array), *machine.lst[1:])
    machine.acc = acc
    for _ in range(len(tokens) + 1):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert machine.ind == target
    assert machine.lst[0] == tuple(predicted)
    assert machine.acc == predicted_acc


@pytest.mark.parametrize("target", [0, 254, 255, 507])
def test_modulo_255_trampoline_rejects_a_target_consumed_by_normalization(
    target: int,
) -> None:
    from esolangs.tools.slow_acv_mammalian import (
        _trampoline,
        _trampoline_len,
        _UnreachableError,
    )

    for build in (_trampoline, _trampoline_len):
        with pytest.raises(_UnreachableError):
            build([0, 254], 253, target, io_modulus=255)


def test_modulo_255_greedy_window_covers_every_head_and_sum_residue() -> None:
    for head in range(256):
        for rest in range(255):
            assert any(
                (((head + 17 * seeds) % 256) + rest) % 255 >= 238 for seeds in range(16)
            )


def test_modulo_255_merge_rejects_a_one_branch_past_the_target() -> None:
    from esolangs.tools.slow_acv_mammalian import _try_arm

    one = _Sums(io_modulus=255)
    zero = _Sums(io_modulus=255)
    one.n0 = 1000
    assert _try_arm(one, zero, 8, None, 500) is None


@pytest.mark.parametrize(
    ("modulus", "step"),
    [(m, s) for m in (255, 256) for s in (1, 7, 22) if gcd(s, m) == 1],
)
def test_short_routing_is_earliest(modulus: int, step: int) -> None:
    from esolangs.tools._mammalian_compact import _routing_seeds

    for head in range(modulus):
        earliest = {}
        for count in range(modulus):
            want = ((head + step * count) % modulus) % 23
            earliest.setdefault(want, count)
        for want, count in earliest.items():
            assert _routing_seeds(head, step, want, modulus) == count


@pytest.mark.parametrize("head", [0])
@pytest.mark.parametrize("rest", [0, 255])
@pytest.mark.parametrize("remaining", [256, 65_536])
def test_missing_head_raise_uses_reachable_nonfinal_chunks(
    head: int, rest: int, remaining: int
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
    from esolangs.tools._mammalian_compact import _Chain, _State

    chain = _Chain(255, io_modulus=256)
    state = _State(head=head)
    state.rest[0] = rest
    tokens = chain.raise_to(state, rest + remaining)
    machine = _Machine(" ".join(tokens), ScriptedIO(), cell_modulus=255, io_modulus=256)
    machine.lst = [[(array + 1) * head % 255] for array in range(23)]
    chunks, tail = divmod(rest, 254)
    machine.lst[0].extend([254] * chunks + [tail])
    while not machine.halted:
        machine.step()
    assert sum(machine.lst[0][1:]) == state.rest[0] == rest + remaining
    assert machine.acc == state.acc == 0
    for array, cells in enumerate(machine.lst):
        assert cells[0] == (array + 1) * state.head % 255
    if rest % 256 == 0:
        assert machine.lst[0][chunks + 2] == 254


@pytest.mark.parametrize("modulus", [255, 256])
def test_read_calibration_reaches_earliest_safe_head(modulus: int) -> None:
    from esolangs.tools._mammalian_compact import _read_seeds

    for total in range(64):
        for head in range(modulus):
            count = _read_seeds(head, total, modulus)
            expected = next(
                step
                for step in range(modulus)
                if (head + step) % modulus <= modulus - 17
                and (total + (head + step) % modulus - 16) % 64 in range(0, 15, 2)
            )
            assert count == expected
            calibrated = (head + count) % modulus
            for carry in (0, 65_536):
                first = total + carry + calibrated
                second = first + 16
                assert first ^ second == 48
                for bit in (0, 1):
                    assert (48 ^ (second + bit)) - (calibrated + 16) == (
                        total + carry - 16 + bit
                    )


@pytest.mark.parametrize("row", [0, 1, 1024, 2046, 2047])
def test_equal_modulus_eleven_input_read_calibration(row: int) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
    from esolangs.tools.slow_acv_mammalian import slow_acv_mammalian

    rng = random.Random(20261014)
    table = "".join(str(rng.getrandbits(1)) for _ in range(2048))
    source = slow_acv_mammalian(table, cell_modulus=255, io_modulus=255)
    io = ScriptedIO(f"{row:011b}")
    machine = _Machine(source, io, cell_modulus=255, io_modulus=255)
    steps, peak = 0, 23
    while not machine.halted:
        machine.step()
        steps += 1
        peak = max(peak, sum(map(len, machine.lst)))
    assert io.getvalue() == table[row]
    assert io.reads == 11
    # Pre-setup fastest sampled path took 11,148 steps; peak was 731 cells.
    assert steps < 11_148
    assert peak <= 731
    assert len(source) <= 345_354
