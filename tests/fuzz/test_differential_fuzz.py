"""Tests for the seeded differential fuzzers in scripts/verify_differential.py.

The fuzzers draw random programs from each language's alphabet with a seeded
RNG and compare the in-package interpreter against the native cross-check,
including the error category (exit code) and -- for NoComment -- the
termination verdict.  These tests pin that the fuzzers are deterministic for
a fixed seed and that they flag divergences when one side is tampered with
(the regression they are meant to catch).

The native toolchain (RISC-V gcc + unicorn) is skipped when missing,
mirroring the differential script itself.
"""

import importlib
import random
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# the differential script imports x86_elf_runner (in scripts/) by bare name
sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

verify_differential = importlib.import_module("scripts.verify_differential")


@pytest.fixture
def rng() -> random.Random:
    return random.Random(1234)


class TestNoCommentFuzz:
    def test_program_alphabet(self, rng) -> None:
        program = verify_differential._gen_nocomment_program(rng)  # noqa: SLF001
        assert set(program) <= set("idclrnfsbo")

    def test_some_draws_are_stack_disciplined(self, rng) -> None:
        """Half the draws pop only what they pushed.

        Popping an empty stack is an invalid operation and was where most
        uniform draws stopped.  A uniform draw goes negative often, so
        "some draw never does" is only true because the structured half
        exists -- which is the property worth pinning.
        """

        def underflows(program: str) -> bool:
            depth = 0
            for char in program:
                depth += (char == "n") - (char == "f")
                if depth < 0:
                    return True
            return False

        draws = [
            verify_differential._gen_nocomment_program(rng)  # noqa: SLF001
            for _ in range(200)
        ]
        # Non-trivial draws only: the empty program underflows nothing.
        safe = [p for p in draws if len(p) > 4 and not underflows(p)]
        assert len(safe) > len(draws) // 5


class TestBfPdaFuzz:
    def test_program_alphabet(self, rng) -> None:
        program = verify_differential._gen_bfpda_program(rng)  # noqa: SLF001
        assert set(program) <= set("@.<>[]")


class TestRam0Fuzz:
    def test_program_alphabet(self, rng) -> None:
        program = verify_differential._gen_ram0_program(rng)  # noqa: SLF001
        assert set(program) <= set("ZANCLS123456789 ")

    def test_some_draws_separate_their_tokens(self, rng) -> None:
        """Half the draws space their tokens apart.

        Without a space in the alphabet, adjacent digits glue into one
        multi-digit goto -- ``'4877'`` is a single jump past the end, so the
        program dumps and halts having executed one token.  That was 63% of
        uniform draws stopping within two steps.
        """
        draws = [
            verify_differential._gen_ram0_program(rng)  # noqa: SLF001
            for _ in range(200)
        ]
        spaced = [p for p in draws if " " in p]
        assert len(spaced) > len(draws) // 5

    def test_structured_gotos_are_not_absurdly_out_of_range(self, rng) -> None:
        """A structured goto lands near the program rather than far past it.

        The uniform half still draws runaway gotos, which is how the
        out-of-range path stays covered; this pins that the structured half
        does not, since that was the whole reason its draws ran two steps.
        """
        for _ in range(200):
            program = verify_differential._gen_ram0_program(rng)  # noqa: SLF001
            if " " not in program:
                continue  # a uniform draw; runaway gotos are expected there
            tokens = program.split()
            for token in tokens:
                if token.isdigit():
                    assert int(token) <= len(tokens) + 2


class TestBioFuzz:
    def test_program_alphabet(self, rng) -> None:
        program = verify_differential._gen_bio_program(rng)  # noqa: SLF001
        assert set(program) <= set("01OoIiXxYyZz{};/ \nabc")


class TestGeneratorsReachExecution:
    """The structured draws must actually run, not just parse-fail.

    A generator drawing uniformly from a language's alphabet agrees with the
    reference on every program and still tests no execution: BIO's random
    draws were rejected at the first token 97% of the time and produced no
    output at all, so the register machine was never reached.  These pin the
    property that was missing, not the exact rates.
    """

    @pytest.mark.parametrize(
        ("gen_name", "run_name", "floor"),
        [
            ("_gen_bfpda_program", "_run_bfpda_python_limited", 0.20),
            ("_gen_bio_program", "_run_bio_python_limited", 0.05),
            ("_gen_nocomment_program", "_run_nocomment_python_limited", 0.20),
            ("_gen_ram0_program", "_run_ram0_python_limited", 0.40),
        ],
    )
    def test_a_useful_share_of_draws_executes(
        self, rng, gen_name: str, run_name: str, floor: float
    ) -> None:
        gen = getattr(verify_differential, gen_name)
        run = getattr(verify_differential, run_name)
        draws = 60
        ran = 0
        for _ in range(draws):
            result = run(gen(rng), timeout=3)
            # exit 0 means the program loaded and executed to completion.
            if result is not None and result[1] == 0:
                ran += 1
        assert ran / draws >= floor, f"{gen_name}: only {ran}/{draws} executed"


class TestMinskySwapFuzz:
    def test_generated_program_shape(self, rng) -> None:
        """The command line is +/~/* only; the jump line is digits and spaces."""
        program = verify_differential._gen_minsky_swap_program(rng)  # noqa: SLF001
        cmd_line = program.split("\n", 1)[0]
        assert set(cmd_line) <= set("+~*")


@pytest.mark.slow
class TestDivergenceDetection:
    """The fuzzer must fail when the two sides disagree."""

    @pytest.mark.skipif(
        not verify_differential._asm_refs_ready("nocomment"),  # noqa: SLF001
        reason="RISC-V cross-check not buildable",
    )
    def test_nocomment_catches_divergence(self, rng) -> None:
        """A wrong output on the RISC-V side is reported as a failure."""
        real_ref = verify_differential._asm_refs  # noqa: SLF001

        def tampered(name, program):
            result = real_ref(name, program)
            if result is None:
                return None
            out, code = result
            return out + b"!", code

        with patch.object(verify_differential, "_asm_refs", side_effect=tampered):
            assert not verify_differential._fuzz_nocomment(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(
        not verify_differential._asm_refs_ready("bfpda"),  # noqa: SLF001
        reason="RISC-V cross-check not buildable",
    )
    def test_bfpda_catches_divergence(self, rng) -> None:
        """A wrong output on the RISC-V side is reported as a failure."""
        real_ref = verify_differential._asm_refs  # noqa: SLF001

        def tampered(name, program):
            result = real_ref(name, program)
            if result is None:
                return None
            out, code = result
            return out + b"!", code

        with patch.object(verify_differential, "_asm_refs", side_effect=tampered):
            assert not verify_differential._fuzz_bfpda(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(
        not verify_differential._asm_refs_ready("ram0"),  # noqa: SLF001
        reason="RISC-V cross-check not buildable",
    )
    def test_ram0_catches_divergence(self, rng) -> None:
        """A wrong output on the RISC-V side is reported as a failure."""
        real_ref = verify_differential._asm_refs  # noqa: SLF001

        def tampered(name, program):
            result = real_ref(name, program)
            if result is None:
                return None
            out, code = result
            return out + b"!", code

        with patch.object(verify_differential, "_asm_refs", side_effect=tampered):
            assert not verify_differential._fuzz_ram0(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(
        not verify_differential._asm_refs_ready("bio"),  # noqa: SLF001
        reason="RISC-V cross-check not buildable",
    )
    def test_bio_catches_divergence(self, rng) -> None:
        """A wrong output on the RISC-V side is reported as a failure."""
        real_ref = verify_differential._asm_refs  # noqa: SLF001

        def tampered(name, program):
            result = real_ref(name, program)
            if result is None:
                return None
            out, code = result
            return out + b"!", code

        with patch.object(verify_differential, "_asm_refs", side_effect=tampered):
            assert not verify_differential._fuzz_bio(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(
        not verify_differential._asm_refs_ready("minsky_swap"),  # noqa: SLF001
        reason="RISC-V cross-check not buildable",
    )
    def test_minsky_swap_catches_divergence(self, rng) -> None:
        """A wrong output on the RISC-V side is reported as a failure."""
        real_ref = verify_differential._asm_refs  # noqa: SLF001

        def tampered(name, program):
            result = real_ref(name, program)
            if result is None:
                return None
            out, code = result
            return out + b"!", code

        with patch.object(verify_differential, "_asm_refs", side_effect=tampered):
            assert not verify_differential._fuzz_minsky_swap(rng, 20)  # noqa: SLF001


@pytest.mark.slow
@pytest.mark.skipif(
    not verify_differential._asm_refs_ready("bio"),  # noqa: SLF001
    reason="RISC-V cross-check not buildable",
)
class TestShrink:
    """The shrinker must reduce a real divergence, not just any string."""

    def test_shrinks_the_terminator_bug(self) -> None:
        """The BIO terminator bug reduces to a fraction of the found draw.

        A positive control rather than a shape assertion: BIO's tokenizer is
        put back to the loose regex that shipped the bug, so the divergence
        under test is the real one, and the reduction has to still diverge.
        Without the monkeypatch there is nothing to shrink and the test
        would pass vacuously -- so it asserts the setup diverges first.
        """
        import re

        from esolangs.interpreters.register_based import bio

        # the draw the fuzz originally found the bug as
        found = "0Iy;1ox;1oZ;1OZ;0iY{1oY;// 1b\n0iZ{0OZ;// 1\n};};"
        loose = re.compile(r"[01][oOiI][xXyYzZ](?:\{|;)|\};")

        with patch.object(bio, "_COMMAND", loose):
            run_limited = verify_differential._run_bio_python_limited  # noqa: SLF001
            assert verify_differential._diverges("bio", run_limited, found)  # noqa: SLF001
            small = verify_differential._shrink("bio", run_limited, found)  # noqa: SLF001
            assert verify_differential._diverges("bio", run_limited, small)  # noqa: SLF001
            assert len(small) < len(found) // 2

    def test_leaves_an_agreeing_program_alone(self) -> None:
        """Nothing to shrink when the two sides agree: the input comes back.

        The shrinker is only ever called on a divergence, but a reduction
        that "succeeded" on an agreeing program would mean the oracle was
        accepting anything.
        """
        run_limited = verify_differential._run_bio_python_limited  # noqa: SLF001
        good = "0ox;0ix{0oy;1ox;};1iy;"
        assert not verify_differential._diverges("bio", run_limited, good)  # noqa: SLF001
        assert verify_differential._shrink("bio", run_limited, good) == good  # noqa: SLF001
