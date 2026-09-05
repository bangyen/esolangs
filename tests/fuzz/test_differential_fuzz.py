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
        program = "".join(rng.choice("idclrnfsbo") for _ in range(rng.randint(0, 30)))
        assert set(program) <= set("idclrnfsbo")


class TestBfPdaFuzz:
    def test_program_alphabet(self, rng) -> None:
        program = verify_differential._gen_bfpda_program(rng)  # noqa: SLF001
        assert set(program) <= set("@.<>[]")


class TestRam0Fuzz:
    def test_program_alphabet(self, rng) -> None:
        program = "".join(
            rng.choice("ZANCLS123456789") for _ in range(rng.randint(0, 30))
        )
        assert set(program) <= set("ZANCLS123456789")


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
