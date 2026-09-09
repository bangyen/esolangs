"""Unit tests for the Factor interpreter."""

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

    def test_wiki_cat(self) -> None:
        """The wiki's cat number decodes to ,[.,]."""
        assert decode(CAT) == ",[.,]"

    def test_wiki_truth_machine(self) -> None:
        """The wiki's polyglot truth machine decodes to the dbfi program."""
        assert decode(TRUTH) == "<" * 18 + ",[>+>+<<-]++++++[>--------<-]>[>.<]>."

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
        assert io.getvalue() == "hi"

    def test_wiki_truth_machine_zero(self) -> None:
        """Input 0 prints 0 and halts."""
        assert run_program(TRUTH, "0") == "0"

    def test_unbalanced_brackets_rejected(self) -> None:
        """7 decodes to '[' alone, which is malformed."""
        with pytest.raises(ValueError, match="unmatched"):
            run_program(7)


class TestStepMachine:
    def test_a_program_with_no_digits_is_the_number_one(self) -> None:
        """No digits means 1, which factors to nothing and runs no commands.

        ``test_empty_program`` and ``test_comment_characters_ignored``
        both cover the digit-free case, but only through the output: 1 and
        2 decode to ``''`` and ``'<'``, and a lone ``<`` prints nothing
        either, so the empty string does not say which number was used.
        The decoded program does.
        """
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
    """A Factor program is one integer, so CPython's digit guard caps the
    language rather than the interpreter."""

    def test_a_program_past_cpythons_digit_limit_still_parses(self) -> None:
        """4300 digits is a DoS guard on int/str, not a Factor rule.

        The program is 2**k: one prime, so decoding is trivial and the test
        pays only for the parse this is about.  ``k`` is chosen to put the
        decimal form well past the default limit.
        """
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
    """``_factorint`` must answer exactly what ``sympy.factorint`` would.

    It divides small primes out itself and only hands the residue to
    sympy (see the function's docstring), so the two can disagree only
    where that split is wrong -- which is precisely what these check.
    """

    @pytest.mark.parametrize(
        "number",
        [
            2,
            3,
            4,
            1,
            2**10,
            6619**3 * 2,
            # A residue that survives the sieve: both factors are past
            # _SMALL_PRIME_LIMIT, so the composite goes to sympy whole.
            999983 * 999979,
            # One large prime, the other end of the same split.
            (10**9 + 7) * 4,
            # A Mersenne prime, which the sieve cannot touch at all.
            2**61 - 1,
            # The shape Factor actually emits: many small primes.
            2**49 * 3**20 * 5**7 * 6619,
        ],
    )
    def test_matches_sympy(self, number: int) -> None:
        import sympy

        from esolangs.interpreters.tape_based.factor import _factorint

        assert _factorint(number) == sympy.factorint(number)

    def test_does_not_strand_a_large_composite_on_sympy(self) -> None:
        """The residue handed to sympy must never be a large composite.

        Stopping the sieve at a fixed prime looks harmless -- whatever is
        left goes to ``factorint`` -- but it hands over exactly the input
        that function is worst at, and it takes minutes where the same
        call on the original number takes milliseconds.  This is the
        program that caught it: the parity table's 3243-digit number
        factors into 237 primes reaching 16189, and a 10000 ceiling left
        80 of them inside a 1275-digit composite.
        """
        import re
        import time

        from esolangs.interpreters.tape_based.factor import _factorint
        from esolangs.tools import boolean as boolean_tools

        program = str(boolean_tools.factor("01101001"))
        number = int(re.sub(r"[^0-9]", "", program))
        start = time.perf_counter()
        factors = _factorint(number)
        elapsed = time.perf_counter() - start

        assert max(factors) > 10000, "the case only bites above a 10000 sieve"
        # Generous next to the ~0.004s it takes, and far under the minutes
        # a stranded composite costs, so this fails on the bug and not on
        # a slow machine.
        assert elapsed < 5.0, f"factorizing took {elapsed:.1f}s"

    def test_never_hands_a_composite_to_sympy(self) -> None:
        """The same guarantee as above, asserted on the handoff itself.

        The timing test next to this one passes whenever the machine is
        fast enough, so it cannot see a handoff that happens to be cheap.
        This one makes ``factorint`` fail if it is called at all, and
        picks the input that provokes the handoff: every factor sits just
        above ``_SIEVE_CHUNK``, so the first chunk divides nothing out and
        a loop that treated a barren chunk as a ceiling would give up
        here with the composite intact.
        """
        import sympy

        from esolangs.interpreters.tape_based import factor as factor_module
        from esolangs.interpreters.tape_based.factor import (
            _SIEVE_CHUNK,
            _factorint,
        )

        primes = [20011, 20021, 20023]
        assert min(primes) > _SIEVE_CHUNK, "the case needs a barren first chunk"
        number = primes[0] * primes[1] * primes[2]

        def refuse(*_args: object, **_kwargs: object) -> dict[int, int]:
            raise AssertionError("a composite was stranded on sympy.factorint")

        with patch.object(factor_module.sympy, "factorint", refuse):
            assert _factorint(number) == dict.fromkeys(primes, 1)
        # The sieve, not sympy, is what found them.
        assert sympy.factorint(number) == dict.fromkeys(primes, 1)

    def test_does_not_pay_isprime_per_chunk(self) -> None:
        """``isprime`` must be gated, not asked once per sieve chunk.

        It runs BPSW -- two modular exponentiations priced by the full
        width of the argument -- so asking about a 41740-bit residue costs
        tens of seconds.  Asking once per chunk made the n=5 parity table
        take 60s to factorize when the sieve that finds every factor
        measures 0.000s.  The residue here needs three chunks, and every
        factor is small, so a correctly gated loop never asks at all.
        """
        from esolangs.interpreters.tape_based import factor as factor_module
        from esolangs.interpreters.tape_based.factor import (
            _SIEVE_CHUNK,
            _factorint,
        )

        asked: list[int] = []
        real_isprime = factor_module.sympy.isprime

        def counting_isprime(value: int) -> bool:
            asked.append(value)
            return bool(real_isprime(value))

        # A prime in the third chunk, so the sieve must widen twice, with
        # a fat small-prime tail to make the residue a real bignum.
        far = int(factor_module.sympy.nextprime(_SIEVE_CHUNK * 2))
        assert far > _SIEVE_CHUNK * 2, far
        number = 3**40 * 5**20 * far
        with patch.object(factor_module.sympy, "isprime", counting_isprime):
            factors = _factorint(number)

        assert factors == {3: 40, 5: 20, far: 1}, factors
        assert not asked, f"isprime asked about {len(asked)} residues, expected none"

    def test_matches_sympy_on_random_integers(self) -> None:
        """A sweep, since the cases above are all deliberately chosen."""
        import random

        import sympy

        from esolangs.interpreters.tape_based.factor import _factorint

        rng = random.Random(7)
        for _ in range(200):
            number = rng.randint(2, 10**12)
            assert _factorint(number) == sympy.factorint(number), number


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
