"""Covers :mod:`esolangs.languages.slow_acv_mammalian.generator`."""

import random
import re
from functools import cache
from math import gcd

import pytest

from esolangs.generation.wrap import balance_score
from esolangs.languages import generators as boolean
from esolangs.languages.slow_acv_mammalian.generator import (
    _merge_address,
    _stash_chunk,
    _stash_run,
    _trampoline,
)
from esolangs.languages.slow_acv_mammalian.wrapping import (
    _balance_mammalian,
    _mammalian,
)
from tests.support.witness_tables import witnesses


@pytest.mark.medium
@pytest.mark.parametrize("essential", range(1, 8))
@pytest.mark.parametrize("io_modulus", [255, 256])
def test_mod255_projected_chain_runs_nonadjacent_input_coordinates(
    essential, io_modulus
) -> None:
    import esolangs
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import compact_chain

    used = [*range(essential - 1), 7]
    # Parity makes every selected coordinate essential, including both ends.
    table = "".join(
        str(sum((row >> (7 - bit)) & 1 for bit in used) % 2) for row in range(256)
    )
    program = compact_chain(
        table, 8, modulus=255, io_modulus=io_modulus, project_inputs=True
    )
    settings = esolangs.DialectSettings(cell_modulus=255, io_modulus=io_modulus)
    for row in (0, 1, 85, 128, 170, 255):
        bits = [int(bit) for bit in f"{row:08b}"]
        output = esolangs.run(
            "SLOW ACV MAMMALIAN",
            program,
            stdin=esolangs.encode_inputs("SLOW ACV MAMMALIAN", bits),
            settings=settings,
        )
        assert esolangs.read_answer("SLOW ACV MAMMALIAN", output) == table[row]


@pytest.mark.medium
# Small tree, mod-256 chain, projected 8-input chain; no single case reaches all.
@pytest.mark.parametrize(
    ("inputs", "io_modulus", "kind"),
    [(2, 255, "first"), (3, 256, "last"), (8, 255, "ends")],
)
def test_mod255_ignored_inputs_keep_reads_and_the_smaller_candidate(
    inputs, io_modulus, kind
) -> None:
    import esolangs
    from esolangs.generation.wrap import balance_program, balance_score
    from esolangs.languages.slow_acv_mammalian.generator import _unprojected_255
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from esolangs.vm import run_until_halt_or_cycle

    used = {"first": [0], "last": [inputs - 1], "ends": [0, inputs - 1]}[kind]
    table = "".join(
        str(sum((row >> (inputs - 1 - bit)) & 1 for bit in used) % 2)
        for row in range(1 << inputs)
    )
    settings = esolangs.DialectSettings(cell_modulus=255, io_modulus=io_modulus)
    legacy = _unprojected_255(table, inputs, io_modulus)
    program = esolangs.generate("SLOW ACV MAMMALIAN", table, settings=settings)
    assert len(program) <= len(legacy)
    if inputs >= 3 or io_modulus == 256:
        assert program.split().count("ACCEPT") == inputs
    if inputs == 8 and io_modulus == 255:
        assert len(program) < len(legacy)  # positive control for projection
    balanced = esolangs.generate(
        "SLOW ACV MAMMALIAN", table, settings=settings, balance=True
    )
    assert balance_score(balanced) <= balance_score(
        balance_program(legacy, "slow_acv_mammalian")
    )
    rows = range(1 << inputs) if inputs <= 3 else (0, 1, 128, 255)
    for row in rows:
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("SLOW ACV MAMMALIAN", bits)
        for candidate in (legacy, program, balanced):
            io_obj = ScriptedIO(stdin + "0")
            run_until_halt_or_cycle(
                _Machine(candidate, io_obj, cell_modulus=255, io_modulus=io_modulus)
            )
            assert io_obj.position() == inputs
            assert (
                esolangs.read_answer("SLOW ACV MAMMALIAN", io_obj.getvalue())
                == table[row]
            )


class TestSlowAcvMammalian:
    """The decision tree LEAPFROG makes possible."""

    def test_constant_tables_still_read_every_input(self) -> None:
        """A constant table consumes all ``n`` inputs."""
        from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
        from esolangs.runtime.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_cycle

        for table in ("0000", "1111", "0110"):
            program = boolean.slow_acv_mammalian(table)
            assert program.split().count("ACCEPT") == 2  # one per input
            io_obj = ScriptedIO("0\n" * 8)
            run_until_halt_or_cycle(_Machine(program, io_obj))
            assert io_obj.position() == 2

    def test_a_node_opens_the_accumulator_on_a_clean_digit(self) -> None:
        """``ACCEPT`` is entered with ``acc % 256 == 48``, whatever the state."""
        from esolangs.languages.slow_acv_mammalian.generator import _node

        for array, acc in (
            ([0], 0),
            ([3, 255, 255], 0),
            ([200, 17, 9], 128),
            ([254, 1, 77, 30], 99999),
        ):
            _, fell, taken, _ = _node(list(array), acc)
            assert (fell[1] ^ sum(fell[0])) % 256 == 48
            assert (taken[1] ^ sum(taken[0])) % 256 == 48

    def test_the_landing_is_the_rest_minus_15(self) -> None:
        """A 1-bit resumes 15 tokens short of the non-head sum, whatever the head."""
        from esolangs.languages.slow_acv_mammalian.generator import _node
        from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
        from esolangs.runtime.io import ScriptedIO

        for array, acc in (
            ([3, 255, 255, 255], 7),
            ([90, 200, 200, 255], 4242),
            ([230, 200, 200, 255], 0),  # the aim would wrap the head
        ):
            tokens, _, taken, landing = _node(list(array), acc)
            assert landing == sum(array[1:]) + acc % 256 - 15
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
        from esolangs.languages.slow_acv_mammalian.generator import _trampoline
        from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
        from esolangs.runtime.io import ScriptedIO

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
        from esolangs.languages.slow_acv_mammalian.generator import _trampoline
        from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
        from esolangs.runtime.io import ScriptedIO

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

    def test_a_pooled_weight_is_blind_to_what_array_16_holds(self) -> None:
        """The pool banks its byte from any starting sum, unchanged."""
        import importlib

        module = importlib.import_module(
            "esolangs.languages.slow_acv_mammalian.generator"
        )
        banked = set()
        for offset in (0, 1, 17, 255, 256, 4097):
            st = module._Sums()  # noqa: SLF001
            _ = module._build_pool(st, 32, 4)  # noqa: SLF001
            st.nw += offset
            before = st.nw
            module._pool_bank(st, 32, 4)  # noqa: SLF001
            banked.add(st.nw - before)
        assert banked == {32}

    @pytest.mark.parametrize("amount", [0, 100, 255, 256, 600, 2000])
    def test_a_weight_raise_is_exact_on_the_machine(self, amount: int) -> None:
        """``_w_raise`` moves array 16's non-head sum by exactly its ask."""
        import importlib

        from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
        from esolangs.runtime.io import ScriptedIO

        module = importlib.import_module(
            "esolangs.languages.slow_acv_mammalian.generator"
        )
        st = module._Sums()  # noqa: SLF001
        st.ptr, st.hw, st.nw = 16, 9, 255
        tokens = module._w_raise(st, amount)  # noqa: SLF001
        machine = _Machine(" ".join(tokens), ScriptedIO(""), io_modulus=256)
        machine.ptr = 16
        machine.lst = tuple((9, 200, 55) if k == 16 else (0,) for k in range(23))
        commands = 0
        while not machine.halted:
            machine.step()
            commands += 1
        assert commands == len(tokens)
        array = machine.lst[16]
        assert sum(array) - array[0] == 255 + amount
        assert (st.nw, st.hw) == (255 + amount, array[0])

    def test_the_dispatch_lands_every_row_on_its_own_leaf(self) -> None:
        """Each run halts inside the leaf slot its inputs selected."""
        from esolangs.languages.slow_acv_mammalian.generator import _LEAF_UNIT, _weights
        from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
        from esolangs.runtime.io import ScriptedIO

        table = "01101001"
        program = boolean.slow_acv_mammalian(table)
        # The table leads, behind the jump from the empty machine.
        span = _LEAF_UNIT * len(table)
        leaf_base = _merge_address(0, 0, span, 255) - span
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
        assert sizes == [11_962, 18_823, 24_713]
        sizes = [
            len(boolean.slow_acv_mammalian(table, io_modulus=256)) for table in tables
        ]
        assert sizes == [12_002, 18_888, 24_798]

    @pytest.mark.parametrize("io_modulus", [255, 256])
    @pytest.mark.parametrize("table", ["01101001", "0110100110010110" * 4])
    def test_the_programs_run_whether_leapfrog_resumes_at_or_after_its_target(
        self, table: str, io_modulus: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every jump target is preceded by a no-op, so the reading is moot."""
        from esolangs.languages.slow_acv_mammalian import interpreter
        from esolangs.languages.slow_acv_mammalian.interpreter import (
            DEFAULT_MODULI,
            _Machine,
        )
        from esolangs.languages.slow_acv_mammalian.interpreter import (
            _advance as advance,
        )
        from esolangs.runtime.io import ScriptedIO

        def at_target(state, n, byte=None, *, moduli=DEFAULT_MODULI):
            out = advance(state, n, byte, moduli=moduli)
            fired = n == 7 and not out[4] and out[3] != state[3] + 1
            return (*out[:3], out[3] - 1, out[4]) if fired else out

        program = boolean.slow_acv_mammalian(table, io_modulus=io_modulus)
        bits = len(table).bit_length() - 1
        rng = random.Random(5)
        for row in rng.sample(range(len(table)), 6):
            answers = []
            for step in (advance, at_target):
                monkeypatch.setattr(interpreter, "_advance", step)
                io = ScriptedIO(f"{row:0{bits}b}")
                machine = _Machine(program, io, io_modulus=io_modulus)
                while not machine.halted:
                    machine.step()
                answers.append(io.getvalue())
            assert answers == [table[row]] * 2

    def test_a_slot_is_the_same_width_for_either_digit(self) -> None:
        """The table's stride is a leaf, and a leaf does not read the sum."""
        from esolangs.languages.slow_acv_mammalian.generator import _program

        sizes = {len(_program(table)) for table in ("0110", "1001", "0111")}
        assert len(sizes) == 1


class TestClosedForms:
    """The solved lengths and addresses agree with the builds they size."""

    @pytest.mark.parametrize("io_modulus", [255, 256])
    def test_stash_run_matches_the_real_chunks(self, io_modulus: int) -> None:
        rng = random.Random(io_modulus)
        for _ in range(200):
            head, rest, chunks = (
                rng.randrange(256),
                rng.randrange(9000),
                rng.randrange(6),
            )
            array, tokens = [head, rest], 0
            for _ in range(chunks):
                chunk, array = _stash_chunk(array, 0, io_modulus=io_modulus)
                array = [array[0], sum(array[1:])]
                tokens += len(chunk)
            assert _stash_run(head, rest, chunks, io_modulus) == (tokens, *array)

    @pytest.mark.parametrize("io_modulus", [255, 256])
    def test_merge_address_is_the_first_window_end_holding_its_jump(
        self, io_modulus: int
    ) -> None:
        """The replaced slot search, kept as the spec: try each window end in turn."""
        byte = io_modulus - 1
        rng = random.Random(io_modulus)
        for _ in range(300):
            head, rest = rng.randrange(256), rng.randrange(5000)
            start = rest + rng.randrange(-600, 1500)

            array = [head, rest]
            first = next(
                cont
                for cont in (rest + byte * (m + 1) for m in range(20))
                if cont - start
                >= len(_trampoline(array, 0, cont, io_modulus=io_modulus)[0])
            )
            assert _merge_address(head, rest, start, io_modulus) == first

    def test_trampoline_stash_chunk_count_is_one_past_the_second(self) -> None:
        """The closed-form tail's premise, pinned directly."""
        array, acc = [11, 23], 7
        counts = []
        for _ in range(6):
            chunk, array = _stash_chunk(array, acc)
            acc = 0
            counts.append(len(chunk) - 2)
        assert counts[2:] == [1, 1, 1, 1]


def test_explicit_default_moduli_preserve_generation() -> None:
    from esolangs.languages.slow_acv_mammalian.generator import slow_acv_mammalian

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
    from esolangs.languages.slow_acv_mammalian.generator import slow_acv_mammalian

    with pytest.raises(ValueError, match=message):
        slow_acv_mammalian("01", **settings)


@pytest.mark.parametrize("table", witnesses(3)[:1])
@pytest.mark.parametrize("cell_modulus", [255, 256])
@pytest.mark.parametrize("io_modulus", [255, 256])
def test_moduli_generate_every_small_table(
    table: str, cell_modulus: int, io_modulus: int
) -> None:
    from esolangs.languages.slow_acv_mammalian.generator import slow_acv_mammalian
    from esolangs.languages.slow_acv_mammalian.interpreter import run
    from esolangs.runtime.io import ScriptedIO

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
    from esolangs.languages.slow_acv_mammalian.generator import slow_acv_mammalian
    from esolangs.languages.slow_acv_mammalian.interpreter import run
    from esolangs.runtime.io import ScriptedIO

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
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import compact_chain
    from esolangs.languages.slow_acv_mammalian.interpreter import run
    from esolangs.runtime.io import ScriptedIO

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
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import compact_chain
    from esolangs.languages.slow_acv_mammalian.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    rng = random.Random(20261003 + n)
    table = "".join(str(rng.getrandbits(1)) for _ in range(1 << n))
    source = compact_chain(table, n, modulus=256, io_modulus=io_modulus)
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:0{n}b}")
        run(source, io, cell_modulus=256, io_modulus=io_modulus)
        assert io.getvalue() == expected
        assert io.reads == n


def test_coprime_chain_rejects_backward_targets() -> None:
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import _Chain, _State

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
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import _Chain, _State

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
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import _Chain, _State
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

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
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import compact_chain

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
    [(6, 37)],
)
def test_coprime_chain_runs_in_stepped_interpreter(
    modulus: int, io_modulus: int, inputs: int, row: int, stepped_chain_program
) -> None:
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

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
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

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
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import _Chain, _State
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

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
# The smallest weight and the largest, -1 for io_modulus - 1.
@pytest.mark.parametrize("weight", [1, -1])
@pytest.mark.parametrize("compact", [False, True])
def test_compact_pool_retrieves_weight_and_routes(
    modulus: int, io_modulus: int, weight: int, *, compact: bool
) -> None:
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import _Chain, _State
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

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


@pytest.mark.parametrize(("modulus", "budget"), [(255, 65_757), (256, 64_158)])
def test_pool_compaction_preserves_three_input_size(modulus: int, budget: int) -> None:
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import compact_chain
    from esolangs.languages.slow_acv_mammalian.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    table = "00101101"
    source = compact_chain(table, 3, modulus=modulus)
    assert len(source) <= budget
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:03b}")
        run(source, io, cell_modulus=modulus, io_modulus=modulus)
        assert io.getvalue() == expected
        assert io.reads == 3


def test_cell_255_tree_rejects_backward_sum_targets() -> None:
    from esolangs.languages.slow_acv_mammalian._mammalian255 import _State

    with pytest.raises(AssertionError, match="precedes"):
        _State(rest=1).raise_to(0)
    with pytest.raises(AssertionError, match="positive tail"):
        _State().jump(0)


@pytest.mark.parametrize("head", [0, 254])
@pytest.mark.parametrize("extra", [0, 512])
@pytest.mark.parametrize(
    "values", [(0, 1, 253, 254), pytest.param(range(255), marks=pytest.mark.slow)]
)
def test_cell_255_appends_every_value_with_a_missing_head(
    head: int, extra: int, values: tuple[int, ...] | range
) -> None:
    from esolangs.languages.slow_acv_mammalian._mammalian255 import _State
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    for value in values:
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
    from esolangs.languages.slow_acv_mammalian._mammalian255 import decision_tree
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

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
@pytest.mark.parametrize("target", [700, 66000])
def test_modulo_255_trampoline_execution(head: int, target: int) -> None:
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    array, acc = [head, 254], 507
    tokens, predicted, predicted_acc = _trampoline(array, acc, target, io_modulus=255)
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
    from esolangs.languages.slow_acv_mammalian.generator import _UnreachableError

    with pytest.raises(_UnreachableError):
        _trampoline([0, 254], 253, target, io_modulus=255)


def test_modulo_255_greedy_window_covers_every_head_and_sum_residue() -> None:
    for head in range(256):
        for rest in range(255):
            assert any(
                (((head + 17 * seeds) % 256) + rest) % 255 >= 238 for seeds in range(16)
            )


def test_compact_print_pairs_are_the_first_coprime_pair() -> None:
    """The search ``_PRINTS`` replaced, kept as the spec."""
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import _PRINTS

    for modulus, pair in _PRINTS.items():
        units = [a for a in range(23) if gcd(a + 1, modulus) == 1]
        weight = units[1]
        found = next(
            (first, (first + seeds * (weight + 1)) % 23, seeds)
            for seeds in range(1, 23)
            for first in units
            if first not in (0, weight)
            and (first + seeds * (weight + 1)) % 23 in units
            and (first + seeds * (weight + 1)) % 23 not in (0, weight, first)
        )
        assert pair == found


@pytest.mark.parametrize(
    ("modulus", "step"),
    [(m, s) for m in (255, 256) for s in (1, 7, 22) if gcd(s, m) == 1],
)
def test_short_routing_is_earliest(modulus: int, step: int) -> None:
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import _routing_seeds

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
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import _Chain, _State
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

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
    from esolangs.languages.slow_acv_mammalian._mammalian_compact import _read_seeds

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


@pytest.mark.parametrize("row", [0, 1024, 2047])
def test_equal_modulus_eleven_input_read_calibration(row: int) -> None:
    from esolangs.languages.slow_acv_mammalian.generator import slow_acv_mammalian
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

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
    # The slowest sampled path took 10,062 steps; peak was 591 cells.
    assert steps <= 10_062
    assert peak <= 591
    assert len(source) <= 346_181


def test_mammalian_uses_seed_sized_cells() -> None:
    """Every command starts on the SEED-sized lattice."""
    wrapped = _mammalian(
        "SEED SEED DIGEST ACCEPT LEAPFROG PRONOUNCE CONFLAGRATE SEED", 39
    )
    assert wrapped.split("\n") == [
        "SEED SEED DIGEST    ACCEPT    LEAPFROG",
        "PRONOUNCE CONFLAGRATE    SEED",
    ]
    for row in wrapped.split("\n"):
        assert all(match.start() % 5 == 0 for match in re.finditer(r"\S+", row))


def test_mammalian_hands_back_a_program_with_no_words() -> None:
    """The grid wrapper needs at least one token to size a row, so a
    whitespace-only program is returned as it came."""
    assert _mammalian("", 40) == ""
    assert _mammalian("   \n ", 40) == "   \n "


@pytest.mark.medium
@pytest.mark.parametrize("cell", [255, 256])
@pytest.mark.parametrize("io", [255, 256])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_print_array_is_independent_of_every_input(cell, io, bit) -> None:
    import esolangs
    from esolangs.runtime._evaluate import _evaluate

    table = bit * 256
    settings = esolangs.DialectSettings(cell_modulus=cell, io_modulus=io)
    program = esolangs.generate("SLOW ACV MAMMALIAN", table, settings=settings)
    assert program.split().count("ACCEPT") == 8
    assert "LEAPFROG" not in program
    assert (
        _evaluate("SLOW ACV MAMMALIAN", program, inputs=8, settings=settings) == table
    )


@pytest.mark.parametrize("cell", [255, 256])
@pytest.mark.parametrize("io", [255, 256])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_print_array_still_consumes_the_whole_stream(cell, io, bit) -> None:
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    program = boolean.slow_acv_mammalian(bit * 8, cell_modulus=cell, io_modulus=io)
    stream = ScriptedIO("0101")
    machine = _Machine(program, stream, cell_modulus=cell, io_modulus=io)
    while not machine.halted:
        machine.step()
    assert stream.position() == 3
    assert stream.getvalue() == bit


def test_equal_cells_reach_the_global_minimum() -> None:
    for count in range(1, 33):
        program = " ".join(["1111"] * count)
        balanced = _balance_mammalian(program)
        optimum = min(
            (_mammalian(program, width) for width in range(1, len(program) + 1)),
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)


def test_balancing_an_empty_program_returns_it() -> None:
    assert _balance_mammalian("") == ""
