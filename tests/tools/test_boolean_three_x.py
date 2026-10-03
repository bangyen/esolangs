"""three_x generator tests."""

import itertools

import pytest

from esolangs import tools as boolean


class TestThreeX:
    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than the identity order's program."""
        from esolangs.tools.three_x import _three_x_ordered

        for i in range(256):
            table = format(i, "08b")
            identity = _three_x_ordered(table, (0, 1, 2))
            assert len(boolean.three_x(table)) <= len(identity)

    def test_unimproved_tables_keep_their_emission(self) -> None:
        """A table no reorder helps emits exactly what it emitted before.

        ``best_input_order`` tries the identity first and keeps it on a tie,
        so reordering can only shrink a program, never churn one.  A constant
        table has no override blocks at all, so no order can beat it.
        """
        from esolangs.tools.three_x import _three_x_ordered

        for table in ("0" * 8, "1" * 8):
            assert boolean.three_x(table) == _three_x_ordered(table, (0, 1, 2))

    def test_reads_stay_in_stream_order(self) -> None:
        """Only the store target moves, so the input stream is consumed the same.

        The reorder is spelled in which variable each ``?`` stores into, not
        in when the reads happen: every build reads its ``n`` inputs up front,
        one ``?`` each, whatever order the tree tests them in.
        """
        from esolangs.tools.three_x import _three_x_ordered

        table = "00010111"
        for perm in ((0, 1, 2), (2, 1, 0), (1, 2, 0)):
            program = _three_x_ordered(table, perm)
            head = program[: program.index("(")] if "(" in program else program
            assert head.count("?") == 3
            # the reads are the first thing the program does
            assert program.startswith("?")

    def test_every_input_order_computes_the_table(self) -> None:
        """The permuted build computes the original table on the original stream."""

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.three_x import run
        from esolangs.tools.three_x import _three_x_ordered

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

    def test_wrong_length_truth_table_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.three_x("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.three_x("02")

    def test_constant_table_has_no_override_blocks(self) -> None:
        """When every row equals the default, no ( ... ) guards are emitted."""
        assert "(" not in boolean.three_x("0" * 4)
        assert "(" not in boolean.three_x("1" * 4)

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

    def test_constant_ladder_is_the_grammar_shortest_first(self) -> None:
        """Keys are the shortest ``C ::= 3 | C C C x`` programs, by length."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.three_x import run
        from esolangs.tools.three_x import _constants

        codes = _constants(13)
        assert [len(c) for c in codes] == [1, 4, 7, 7] + [10] * 4 + [13] * 5
        values = []
        for code in codes:
            io = ScriptedIO("")
            run(code + "!", io)  # each leaves exactly one value on the stack
            values.append(io.getvalue().strip())
        assert values[0] == "3"
        assert len(set(values)) == len(values)  # a key has to be distinct

    def test_constant_ladder_only_ever_extends(self) -> None:
        """More names append to the cache; 30 of them still fit 16 characters."""
        from esolangs.tools.three_x import _constants

        first = _constants(4)
        longer = _constants(30)
        assert longer[:4] == first
        assert len(longer[-1]) <= 16

    def test_bit_copies_replace_a_guarded_pair(self) -> None:
        """A subtree that *is* one of its bits collapses to one write."""
        # The identity on input 1 at n=2: no guard, one copy of the stored bit.
        program = boolean.three_x("0011")
        assert "(" not in program
