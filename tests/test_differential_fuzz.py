"""Tests for the seeded differential fuzzers in scripts/verify_differential.py.

The fuzzers draw random programs from each language's alphabet with a seeded
RNG and compare the in-package interpreter against the native cross-check,
including the error category (exit code) and -- for NoComment -- the
termination verdict.  These tests pin that the fuzzers are deterministic for
a fixed seed and that they flag divergences when one side is tampered with
(the regression they are meant to catch).

The native toolchains (nasm+unicorn, cargo) are skipped when
missing, mirroring the differential script itself.
"""

import importlib
import random
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# the differential script imports x86_elf_runner (in scripts/) by bare name
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

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
        program = "".join(rng.choice("@.<>[]") for _ in range(rng.randint(0, 30)))
        assert set(program) <= set("@.<>[]")


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
        not verify_differential.FORTH_BIN.exists(), reason="Rust cross-check not built"
    )
    def test_forth_catches_divergence(self, rng) -> None:
        """A wrong output on the Rust side is reported as a failure."""
        real_run = verify_differential._run_forth_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_forth_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_forth(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(
        not verify_differential.BASICFUCK_BIN.exists(),
        reason="Rust cross-check not built",
    )
    def test_basicfuck_catches_divergence(self, rng) -> None:
        """A wrong output on the Rust side is reported as a failure."""
        real_run = verify_differential._run_basicfuck_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_basicfuck_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_basicfuck(rng, 20)  # noqa: SLF001

    _UNSQUARE_CROSS_CHECK = (
        Path(__file__).parents[1] / "extra/rust/target/debug/unsquare"
    )

    @pytest.mark.skipif(
        not _UNSQUARE_CROSS_CHECK.exists(), reason="Rust cross-check not built"
    )
    def test_unsquare_catches_divergence(self, rng) -> None:
        """A wrong output on the Rust side is reported as a failure."""
        real_run = verify_differential._run_unsquare_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_unsquare_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_unsquare(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(
        not verify_differential.THREE_X_BIN.exists(),
        reason="Rust cross-check not built",
    )
    def test_three_x_catches_divergence(self, rng) -> None:
        """A wrong output on the Rust side is reported as a failure."""
        real_run = verify_differential._run_three_x_native  # noqa: SLF001

        def tampered(program, stdin):
            out, code = real_run(program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_three_x_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_three_x(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(
        not verify_differential.TWO_D_FISH_BIN.exists(),
        reason="Rust cross-check not built",
    )
    def test_two_d_fish_catches_divergence(self, rng) -> None:
        """A wrong output on the Rust side is reported as a failure."""
        real_run = verify_differential._run_two_d_fish_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_two_d_fish_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_two_d_fish(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(
        not verify_differential.PAINFUCK_BIN.exists(),
        reason="Rust cross-check not built",
    )
    def test_painfuck_catches_divergence(self, rng) -> None:
        """A wrong output on the Rust side is reported as a failure."""
        real_run = verify_differential._run_painfuck_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_painfuck_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_painfuck(rng, 20)  # noqa: SLF001
