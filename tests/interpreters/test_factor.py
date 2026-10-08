"""Unit tests for the Factor interpreter."""

import math
import sys
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.factor import decode, run
from tests.interpreters.contract import CycleContract, SnapshotContract

# The wiki's published programs, decoded from their prime factorizations.
CAT = 310861643  # 17 * 29 * 71 * 83 * 107 -> ,[.,]
TRUTH = int(
    "233915737501853959241591127266540514014498928384925170744745"
    "371936977107366667491950094954248611898080571424768"
)
HELLO = (
    "165568126334970152108465968061155171986407140362585967599315"
    "536018497965087531792407507166301417079639821420008960583725"
    "657575924647885581598194350616996937817991828503583279278232"
    "187442387967338114367653866183679008386601675267486870730114"
    "2092304365222517116382208838942082995905598124019955549"
)


def run_program(number: int, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(str(number), io)
    return io.getvalue()


def run_program_text(program: str, stdin: str = "") -> str:
    """Run an already-rendered program, for one too long to pass as an int."""
    io = ScriptedIO(stdin)
    run(program, io)
    return io.getvalue()


class TestDecode:
    def test_repeated_instruction(self) -> None:
        """9 = 3^2 decodes to two increments."""
        assert decode(9) == "++"

    def test_instructions_sort_ascending(self) -> None:
        """Factors sort ascending, so the residues map to that order."""
        assert decode(3 * 23) == "+>"  # 3 -> '+', 23 -> '>'
        assert decode(23 * 3) == "+>"  # same multiset, same order

    def test_zero_and_one(self) -> None:
        """1 has no prime factors; 0's factor 0 has residue 0, both ignored."""
        assert decode(1) == ""
        assert decode(0) == ""


class TestRun:
    def test_empty_program(self) -> None:
        assert run_program(1) == ""

    def test_comment_characters_ignored(self) -> None:
        """Non-digits are comments: 'Hi 15!' is just 15."""
        io = ScriptedIO()
        run("Hi 15!", io)
        assert io.getvalue() == "\x01"

    def test_single_instruction(self) -> None:
        """15 = 3*5 decodes to '+.' which prints chr(1)."""
        assert run_program(15) == "\x01"

    def test_print_letter(self) -> None:
        """3^65 * 5 decodes to 65 increments then a print (ASCII 'A')."""
        assert run_program(3**65 * 5) == "A"

    def test_wiki_cat_echoes(self) -> None:
        """The cat program echoes input, then EOF raises like brainfuck."""
        io = ScriptedIO("h\ni")
        with pytest.raises(EOFError):
            run(str(CAT), io)
        assert io.getvalue() == "h\ni"

    def test_wiki_truth_machine_zero(self) -> None:
        """Input 0 prints 0 and halts."""
        assert run_program(TRUTH, "0") == "0"

    def test_wiki_truth_machine_one_repeats(self) -> None:
        """Input 1 prints 1 forever; a bounded run sees only 1s."""
        from esolangs.interpreters.tape_based.factor import _Machine

        io = ScriptedIO("1")
        machine = _Machine(str(TRUTH), io)
        for _ in range(2000):
            machine.step()
        assert not machine.halted
        assert set(io.getvalue()) == {"1"}
        assert len(io.getvalue()) > 100

    def test_wiki_hello_world(self) -> None:
        """Its decode ends ``>>.`` on an empty cell, so a NUL follows the text."""
        assert run_program_text(HELLO) == "Hello World!\x00"

    def test_unbalanced_brackets_rejected(self) -> None:
        """7 decodes to '[' alone, which is malformed."""
        with pytest.raises(ValueError, match="unmatched"):
            run_program(7)


class TestStepMachine:
    def test_a_program_with_no_digits_is_the_number_one(self) -> None:
        """No digits means 1, which factors to nothing and runs no commands."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.factor import _Machine

        assert _Machine("", ScriptedIO()).bf.code == ""
        assert _Machine("no digits here", ScriptedIO()).bf.code == ""

    def test_step_tracks_the_decoded_tape(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.factor import _Machine

        machine = _Machine("15", ScriptedIO())
        assert (machine.bf.ind, list(machine.bf.tape)) == (0, [0])
        machine.step()  # + increments the cell
        assert list(machine.bf.tape) == [1]
        machine.step()  # . prints it
        assert machine.io.getvalue() == "\x01"
        assert machine.halted


class TestLongPrograms:
    """Factor programs remain valid past CPython's process-wide digit guard."""

    def test_a_program_past_cpythons_digit_limit_still_parses(self) -> None:
        """4300 digits is a DoS guard on int/str, not a Factor rule."""
        number = 2**20000
        limit = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(30000)
        try:
            program = str(number)
        finally:
            sys.set_int_max_str_digits(limit)
        assert len(program) > limit, "the point of the test is to exceed it"
        # 2 has residue 2 mod 11, so this decodes to 20000 '<' -- every one
        # of them clamped at the left edge, printing nothing and halting.
        assert run_program_text(program) == ""

    def test_the_parse_leaves_the_global_limit_alone(self) -> None:
        """The limit is process-global, so it is borrowed and handed back."""
        before = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(30000)
        try:
            program = str(2**20000)
        finally:
            sys.set_int_max_str_digits(before)
        run_program_text(program)
        assert sys.get_int_max_str_digits() == before


class TestFactorint:
    """``_factorint`` must answer exactly what ``sympy.factorint`` would."""

    def test_primality_boundaries(self) -> None:
        from esolangs.interpreters.tape_based.factor import _isprime64

        assert not _isprime64(0)
        assert _isprime64(2)

    def test_primes_dividing_a_witness_base_are_prime(self) -> None:
        """A base the number divides is skipped, not read as a witness."""
        import sympy

        from esolangs.interpreters.tape_based.factor import _isprime64

        for number in (73, 193, 3089, 29059, 299210837):
            assert sympy.isprime(number)
            assert _isprime64(number), number

    def test_the_witnesses_are_sinclairs_proven_set(self) -> None:
        """The last base is ``1795265022``, not the truncated ``179526502``."""
        import inspect

        from esolangs.interpreters.tape_based import factor as factor_module

        source = inspect.getsource(factor_module._isprime64)  # noqa: SLF001
        assert "(2, 325, 9375, 28178, 450775, 9780504, 1795265022)" in source

    @pytest.mark.parametrize(
        "number",
        [
            # Above _BATCH_BITS, so the chunk is tested by one gcd rather
            # than a remainder per prime.  Only 2 divides, so every other
            # prime in the chunk has to fall through the gcd's answer.
            pytest.param(2**9000, id="one-small-prime"),
            # Two primes far apart, the larger past the first chunk: the
            # batch has to survive a residue that keeps shrinking under it,
            # and a later chunk's gcd has to still find 20011.
            pytest.param(2**9000 * 3**40 * 20011, id="across-chunks"),
        ],
    )
    def test_the_batched_chunk_answers_what_the_divisions_would(
        self, number: int
    ) -> None:
        """The gcd shortcut must find exactly the primes the loop found."""
        import sympy

        from esolangs.interpreters.tape_based.factor import _BATCH_BITS, _factorint

        assert number.bit_length() >= _BATCH_BITS, "would not reach the batch"
        assert _factorint(number) == sympy.factorint(number)

    def test_a_large_prime_residue_is_certified_after_one_barren_chunk(self) -> None:
        """2**61 - 1 outlives the first chunk, then the exact screen accepts it."""
        from esolangs.interpreters.tape_based.factor import _factorint

        assert _factorint(2**61 - 1) == {2**61 - 1: 1}

    def test_never_strands_a_composite_above_the_first_chunk(self) -> None:
        """A barren chunk is not a factorization ceiling."""
        import sympy

        from esolangs.interpreters.tape_based.factor import (
            _SIEVE_CHUNK,
            _factorint,
        )

        primes = [20011, 20021, 20023]
        assert min(primes) > _SIEVE_CHUNK, "the case needs a barren first chunk"
        number = primes[0] * primes[1] * primes[2]

        assert _factorint(number) == dict.fromkeys(primes, 1)
        assert sympy.factorint(number) == dict.fromkeys(primes, 1)

    def test_does_not_pay_isprime_per_chunk(self) -> None:
        """``isprime`` must be gated, not asked once per sieve chunk."""
        from esolangs.interpreters.tape_based import factor as factor_module
        from esolangs.interpreters.tape_based.factor import (
            _SIEVE_CHUNK,
            _factorint,
        )

        asked: list[int] = []
        real_isprime = factor_module._isprime64  # noqa: SLF001

        def counting_isprime(value: int) -> bool:
            asked.append(value)
            return bool(real_isprime(value))

        # A prime in the third chunk, so the sieve must widen twice, with
        # a fat small-prime tail to make the residue a real bignum.
        import sympy

        far = int(sympy.nextprime(_SIEVE_CHUNK * 2))
        assert far > _SIEVE_CHUNK * 2, far
        number = 3**40 * 5**20 * far
        with patch.object(factor_module, "_isprime64", counting_isprime):
            factors = _factorint(number)

        assert factors == {3: 40, 5: 20, far: 1}, factors
        assert not asked, f"isprime asked about {len(asked)} residues, expected none"

    def test_probable_prime_screen_is_never_used_above_64_bits(self) -> None:
        """An uncapped decode cannot accept BPSW as a primality proof."""
        from esolangs.interpreters.tape_based import factor as factor_module
        from esolangs.interpreters.tape_based.factor import _factorint

        primes = [20011, 20021, 20023, 20029, 20047]
        number = math.prod(primes)
        assert number >= 2**64
        real_isprime = factor_module._isprime64  # noqa: SLF001

        def exact_range_only(value: int) -> bool:
            assert value < 2**64
            return bool(real_isprime(value))

        with patch.object(factor_module, "_isprime64", exact_range_only):
            assert _factorint(number) == dict.fromkeys(primes, 1)


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.factor import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "15"
    halting_program = "15"
    looping_program = "3567"
