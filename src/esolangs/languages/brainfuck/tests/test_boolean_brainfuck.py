"""brainfuck generator tests."""

import pytest

from tests.support.reference import REFERENCE


@pytest.mark.medium
def test_affine_stream_all_small_coefficients_within_ledger() -> None:
    from esolangs.debugger import make_vm
    from esolangs.languages.brainfuck.generator import _affine_stream
    from scripts.benchmark import WrittenState

    _check_constants()
    admitted = 0
    for n in range(1, 6):
        for mask in range(1 << n):
            for bias in (0, 1):
                table = "".join(
                    str((row & mask).bit_count() % 2 ^ bias) for row in range(1 << n)
                )
                source = _affine_stream(table)
                if source is None:
                    continue
                admitted += 1
                for row, expected in enumerate(table):
                    vm = make_vm(REFERENCE, source, stdin=f"{row:0{n}b}")
                    written = WrittenState(vm.snapshot())
                    commands = 0
                    while not vm.halted and commands <= 69 * n + 44:
                        vm.step()
                        written.sample(vm.snapshot())
                        commands += 1
                    assert vm.halted
                    assert vm.output == expected
                    assert commands <= 69 * n + 44
                    assert (
                        written.bits
                        <= 2 * n
                        + 6
                        + (2 * n).bit_length()
                        + n.bit_length()
                        + len(source).bit_length()
                    )
    assert admitted > 0
    assert _affine_stream("0001") is None


@pytest.mark.medium
def test_affine_stream_reduces_cap_parity_within_ledger() -> None:
    from esolangs.languages.brainfuck.generator import _bf_ordered
    from tests.support.generator_support import assert_shared_program

    n = 16
    table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    previous = _bf_ordered(table, tuple(range(n)))
    assert_shared_program(
        REFERENCE,
        table,
        previous,
        69 * n + 44,
        lambda p: (
            2 * n + 6 + (2 * n).bit_length() + n.bit_length() + len(p).bit_length()
        ),
        rows=[0, 1, 2, 3, 32767, 32768, 65534, 65535],
    )


@pytest.mark.parametrize("blocks", [((1, 0), (1, 4)), ((2, 0), (1, 0)), ((3, 0),)])
def test_deferred_flags_require_ordered_distinct_levels(blocks) -> None:
    from esolangs.generation.shared_flag import flag_tree_body

    with pytest.raises(ValueError, match="deferred levels"):
        flag_tree_body("01101001", (0, 1, 2), 4, 6, shared_blocks=blocks)


@pytest.mark.medium
def test_multiple_residuals_reduce_guarded_parity_within_ledger() -> None:
    import esolangs
    from esolangs.generation.shared_block import repeated_block
    from esolangs.generation.shared_flag import flag_tree_body
    from tests.support.generator_support import assert_shared_program

    n = 10
    residual = "".join(str(row.bit_count() & 1) for row in range(1 << (n - 4)))
    table = "0" * (15 * len(residual)) + residual
    body, _ = flag_tree_body(
        table, tuple(range(n)), 2 * (n - 1), 2 * n, shared=repeated_block(table)
    )
    previous = ">>".join("," + "-" * 48 for _ in range(n)) + body + "+" * 48 + "."
    assert len(esolangs.generate(REFERENCE, table)) < len(previous)
    assert_shared_program(
        REFERENCE,
        table,
        previous,
        69 * n + 44,
        lambda p: (
            2 * n + 6 + (2 * n).bit_length() + n.bit_length() + len(p).bit_length()
        ),
        rows=[
            *range(15 * len(residual), len(table)),
            *[prefix * len(residual) + len(residual) - 1 for prefix in range(15)],
        ],
    )


@pytest.mark.medium
@pytest.mark.parametrize("n", [2, 3, 6])
def test_literal_counter_consumes_inputs_within_revised_bounds(n: int) -> None:
    from esolangs.debugger import make_vm
    from esolangs.languages.brainfuck.generator import brainfuck
    from scripts.benchmark import WrittenState

    size = 1 << n
    for exceptional in (0, size // 3, size - 1):
        product = "0" * exceptional + "1" + "0" * (size - exceptional - 1)
        for table in (product, product.translate(str.maketrans("01", "10"))):
            source = brainfuck(table)
            for row, expected in enumerate(table):
                vm = make_vm(REFERENCE, source, stdin=f"{row:0{n}b}")
                written = WrittenState(vm.snapshot())
                commands = 0
                while not vm.halted and commands <= 81 * n + 47:
                    vm.step()
                    written.sample(vm.snapshot())
                    commands += 1
                assert vm.halted
                assert vm.output == expected
                assert vm.snapshot()[-1] == n
                assert commands <= 81 * n + 47
                assert written.bits <= (
                    max(7 * n, 2 * n + 7)
                    + (2 * n).bit_length()
                    + n.bit_length()
                    + len(source).bit_length()
                )


def _check_constants() -> None:
    import esolangs
    from esolangs.languages.brainfuck.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(2, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.reads == self.expected
                super()._write(value)

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("brainfuck", bit * (1 << n), **options)
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "brainfuck", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q")
                    machine = _Machine("".join(program.split()), io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= n + 82 + int(bit)
                    assert steps == n + 82 + int(bit)
                    assert io.getvalue() == bit
                    assert (
                        written.bits
                        == 16 + (n + 22 + int(bit)).bit_length() + n.bit_length()
                    )
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("brainfuck", f"{v:08b}")) for v in range(256))
        == 70418
    )
