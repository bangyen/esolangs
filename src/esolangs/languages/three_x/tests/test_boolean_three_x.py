"""three_x generator tests."""

import itertools
from fractions import Fraction

import pytest

import esolangs
from esolangs.languages import generators as boolean
from esolangs.languages.three_x.generator import _constant, _gain
from esolangs.languages.three_x.tests.formulas import _key
from scripts.benchmark import state_bits


def _grammar_level(length: int, memo: dict[int, dict[Fraction, str]]) -> dict:
    """Oracle: constants whose shortest ``3 | C C C x`` program is ``length`` long."""
    if length in memo:
        return memo[length]
    if length == 1:
        memo[1] = {Fraction(3): "3"}
        return memo[1]
    lower = {size: _grammar_level(size, memo) for size in range(1, length)}
    seen = set().union(*lower.values())
    fresh: dict[Fraction, str] = {}
    for first, divisors in lower.items():
        for second, subtracted in lower.items():
            tops = lower.get(length - 1 - first - second)
            if tops is None:
                continue
            for a, code_a in divisors.items():
                if a == 0:
                    continue
                for b, code_b in subtracted.items():
                    for c, code_c in tops.items():
                        value = (c - b) / a
                        if value not in seen and value not in fresh:
                            fresh[value] = code_a + code_b + code_c + "x"
    memo[length] = fresh
    return fresh


def _evaluate(code: str) -> Fraction:
    """Evaluate a ``C ::= 3 | C C C x`` program with exact rationals."""
    stack: list[Fraction] = []
    for char in code:
        if char == "3":
            stack.append(Fraction(3))
        else:
            c, b, a = stack.pop(), stack.pop(), stack.pop()
            stack.append((c - b) / a)
    (value,) = stack
    return value


class TestThreeX:
    def test_identity_program_structure(self) -> None:
        """The 01 table reads a bit and stores it before printing."""
        program = boolean.three_x("01")
        assert program.startswith("?")
        assert program.endswith("!")

    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than the identity order's program."""
        from esolangs.languages.three_x.generator import _three_x_ordered

        for i in range(256):
            table = format(i, "08b")
            identity = _three_x_ordered(table, (0, 1, 2))
            assert len(boolean.three_x(table)) <= len(identity)

    def test_unimproved_tables_keep_their_emission(self) -> None:
        """A table no reorder helps emits exactly what it emitted before."""
        from esolangs.languages.three_x.generator import _three_x_ordered

        for table in ("0" * 8, "1" * 8):
            assert boolean.three_x(table) == _three_x_ordered(table, (0, 1, 2))

    def test_reads_stay_in_stream_order(self) -> None:
        """Only the store target moves, so the input stream is consumed the same."""
        from esolangs.languages.three_x.generator import _three_x_ordered

        table = "00010111"
        for perm in ((0, 1, 2), (2, 1, 0), (1, 2, 0)):
            program = _three_x_ordered(table, perm)
            head = program[: program.index("(")] if "(" in program else program
            assert head.count("?") == 3
            # the reads are the first thing the program does
            assert program.startswith("?")

    def test_every_input_order_computes_the_table(self) -> None:
        """The permuted build computes the original table on the original stream."""

        from esolangs.languages.three_x.generator import _three_x_ordered
        from esolangs.languages.three_x.interpreter import run
        from esolangs.runtime.io import ScriptedIO

        def permuted(table: str, perm: tuple[int, ...]) -> str:
            out = []
            for row in range(8):
                src = 0
                for k in range(3):
                    src |= ((row >> (2 - k)) & 1) << (2 - perm[k])
                out.append(table[src])
            return "".join(out)

        for table in ("00010111", "01101001", "11110000", "10101010"):
            for perm in itertools.permutations(range(3)):
                program = _three_x_ordered(permuted(table, perm), perm)
                for combo in range(8):
                    bits = [(combo >> (2 - k)) & 1 for k in range(3)]
                    io = ScriptedIO("\n".join(str(b) for b in bits) + "\n")
                    run(program, io)
                    assert io.getvalue().strip() == table[combo], f"{table} {perm}"

    def test_uses_input_variables(self) -> None:
        """Each input bit is read into a distinct variable."""
        program = boolean.three_x("0001")
        assert program.count("?") == 2
        assert "333x" in program  # the constant-0 encoding appears
        assert "3333x3x" in program  # the constant-1 encoding appears

    def test_constant_table_has_no_override_blocks(self) -> None:
        """When every row equals the default, no ( ... ) guards are emitted."""
        assert "(" not in boolean.three_x("0" * 4)
        assert "(" not in boolean.three_x("1" * 4)

    def test_majority_default_handles_zero_row(self) -> None:
        """A zero row differing from a majority-1 default still overrides it."""
        program = boolean.three_x("0110")  # XOR: two 1s, two 0s
        assert program.startswith("?")
        assert program.endswith("!")
        assert "(" in program  # the zero row needs an override block

    def test_scales_to_more_inputs(self) -> None:
        """The generator handles n beyond the built-in constants."""
        program = boolean.three_x("0" * (2**7))
        assert program.count("?") == 7

    def test_shared_tree_prefix_sharing(self) -> None:
        """Differing combos share prefix guards instead of repeating them."""
        # top-half n=5: 16 zero-rows all share MSB=0.  A full tree has
        # 31 guard nodes; independent chains would emit 16 * 5 = 80.
        program = boolean.three_x("0" * 16 + "1" * 16)
        assert program.count("(") < 40

    def test_deep_names_keep_full_tree_growth_linear(self) -> None:
        """The shortest variable names sit at the most repeated depths."""
        parity7 = "".join(str(i.bit_count() & 1) for i in range(2**7))
        parity8 = "".join(str(i.bit_count() & 1) for i in range(2**8))
        assert len(boolean.three_x(parity8)) < 2 * len(boolean.three_x(parity7))

    def test_constants_are_distinct_grammar_programs(self) -> None:
        """Every key is a ``3 | C C C x`` program; no two share a value."""
        values = [_evaluate(_constant(k)) for k in range(3000)]
        assert len(set(values)) == len(values)  # a key has to be distinct

    def test_constant_lengths_are_closed_form(self) -> None:
        """Key ``k`` costs ``4 + 3 * (bit_length(k) - 1)`` characters; key 0 is 3."""
        assert _constant(0) == "3"
        for k in range(1, 3000):
            assert len(_constant(k)) == 4 + 3 * (k.bit_length() - 1)

    def test_constants_match_the_grammar_enumeration_lengths(self) -> None:
        """Against the shortest-first enumeration: equal for 16 keys, 3 longer by 41."""
        memo: dict[int, dict[Fraction, str]] = {}
        oracle: list[str] = []
        length = 0
        while len(oracle) < 41:
            length += 1
            oracle.extend(_grammar_level(length, memo).values())
        mine = [len(_constant(k)) for k in range(41)]
        assert mine[:16] == [len(c) for c in oracle[:16]]
        assert all(m <= len(c) + 3 for m, c in zip(mine, oracle[:41], strict=True))

    def test_constants_run_to_their_value(self) -> None:
        """The interpreter agrees with the exact evaluation for the first 40 keys."""
        from esolangs.languages.three_x.interpreter import run
        from esolangs.runtime.io import ScriptedIO

        for k in range(40):
            io = ScriptedIO("")
            run(_constant(k) + "!", io)
            assert Fraction(io.getvalue().strip()) == _evaluate(_constant(k))

    def test_share_gain_prices_uses_and_rows(self) -> None:
        """One use never pays; more uses of a longer block pay more."""
        assert _gain(64, 1) < 0
        assert _gain(4, 2) < 0 < _gain(16, 8)
        assert _gain(16, 8) < _gain(32, 8)

    def test_bit_copies_replace_a_guarded_pair(self) -> None:
        """A subtree that *is* one of its bits collapses to one write."""
        # The identity on input 1 at n=2: no guard, one copy of the stored bit.
        program = boolean.three_x("0011")
        assert "(" not in program

    def test_repeated_blocks_are_written_once(self) -> None:
        """Three copies of one block cost one block, and the program still runs."""
        from esolangs.languages.three_x.generator import _three_x_emit
        from esolangs.languages.three_x.interpreter import run
        from esolangs.runtime.io import ScriptedIO

        a, b = "0010110111010001", "1101001000101110"
        table = a + a + b + a
        program = boolean.three_x(table)
        plain = _three_x_emit(table, tuple(range(6)), list(range(6)), 6, ())
        assert len(program) < 0.9 * len(plain)
        for combo in range(64):
            io = ScriptedIO("\n".join(str((combo >> (5 - k)) & 1) for k in range(6)))
            run(program, io)
            assert io.getvalue().strip() == table[combo]


def test_three_x_keys_fit_their_bound() -> None:
    """K(i) covers the 41 first keys, every key through n = 20."""
    for i in range(1, 42):
        assert state_bits(_evaluate(_constant(i - 1)), {}) <= _key(i), i


@pytest.mark.parametrize(
    ("table", "size"),
    [
        # A repeated constant block is not shared.
        ("0001100000011000000110000000000000000000000000000000000000000000", 366),
        # The sharing gain charges 7 characters a row.
        ("1101110011011101110011011101110111001101110111011100110011001101", 565),
        # Four-row blocks are candidates for sharing.
        ("1011000000001011111111111011101111111011101100000000101100001011", 497),
    ],
)
def test_block_sharing_sizes(table: str, size: int) -> None:
    assert len(esolangs.generate("three_x", table)) == size
