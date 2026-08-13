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
import shutil
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


class TestDivergenceDetection:
    """The fuzzer must fail when the two sides disagree."""

    @pytest.mark.skipif(shutil.which("nasm") is None, reason="nasm not installed")
    def test_nocomment_catches_divergence(self, rng) -> None:
        """A wrong output on the assembly side is reported as a failure."""
        x86_elf_runner = importlib.import_module("x86_elf_runner")
        real_elf = x86_elf_runner.run_elf

        def tampered(binary, stdin):
            out, code = real_elf(binary, stdin)
            return out + b"!", code

        with patch.object(x86_elf_runner, "run_elf", side_effect=tampered):
            assert not verify_differential._fuzz_nocomment(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
    def test_forth_catches_divergence(self, rng) -> None:
        """A wrong output on the C++ side is reported as a failure."""
        real_run = verify_differential._run_forth_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_forth_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_forth(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
    def test_basicfuck_catches_divergence(self, rng) -> None:
        """A wrong output on the C++ side is reported as a failure."""
        real_run = verify_differential._run_basicfuck_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_basicfuck_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_basicfuck(rng, 20)  # noqa: SLF001

    _UNSQUARE_REF = Path(__file__).parents[1] / "extra/rust/target/debug/unsquare"

    @pytest.mark.skipif(not _UNSQUARE_REF.exists(), reason="Rust reference not built")
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

    @pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby not installed")
    def test_three_x_catches_divergence(self, rng) -> None:
        """A wrong output on the Ruby side is reported as a failure."""
        real_run = verify_differential._run_three_x_native  # noqa: SLF001

        def tampered(program, stdin):
            out, code = real_run(program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_three_x_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_three_x(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
    def test_pct_catches_divergence(self, rng) -> None:
        """A wrong output on the C++ side is reported as a failure."""
        real_run = verify_differential._run_pct_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(verify_differential, "_run_pct_native", side_effect=tampered):
            assert not verify_differential._fuzz_pct(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
    def test_two_d_fish_catches_divergence(self, rng) -> None:
        """A wrong output on the C++ side is reported as a failure."""
        real_run = verify_differential._run_two_d_fish_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_two_d_fish_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_two_d_fish(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
    def test_painfuck_catches_divergence(self, rng) -> None:
        """A wrong output on the C++ side is reported as a failure."""
        real_run = verify_differential._run_painfuck_native  # noqa: SLF001

        def tampered(binary, program, stdin):
            out, code = real_run(binary, program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_painfuck_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_painfuck(rng, 20)  # noqa: SLF001

    @pytest.mark.skipif(shutil.which("ruby") is None, reason="ruby not installed")
    def test_bit_tilde_catches_divergence(self, rng) -> None:
        """A wrong output on the Ruby side is reported as a failure."""
        real_run = verify_differential._run_bit_tilde_native  # noqa: SLF001

        def tampered(program, stdin):
            out, code = real_run(program, stdin)
            return out + b"!", code

        with patch.object(
            verify_differential, "_run_bit_tilde_native", side_effect=tampered
        ):
            assert not verify_differential._fuzz_bit_tilde(rng, 20)  # noqa: SLF001
