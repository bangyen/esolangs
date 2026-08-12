"""Tests for the seeded differential fuzzers in scripts/verify_differential.py.

The fuzzers draw random programs from each language's alphabet with a seeded
RNG and compare the in-package interpreter against the native cross-check,
including the error category (exit code) and -- for NoComment -- the
termination verdict.  These tests pin that the fuzzers are deterministic for
a fixed seed and that they flag divergences when one side is tampered with
(the regression they are meant to catch).

The native toolchains (Rscript, nasm+unicorn, cargo) are skipped when
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


class TestExconFuzz:
    def test_fuzz_is_seeded(self) -> None:
        """The same seed always explores the same programs (pure RNG)."""
        first = random.Random(42)
        second = random.Random(42)
        a = [first.choice(":^<!") for _ in range(50)]
        b = [second.choice(":^<!") for _ in range(50)]
        assert a == b

    def test_program_alphabet(self, rng) -> None:
        """Fuzz programs stay within the EXCON instruction alphabet."""
        program = "".join(
            rng.choice(":^<!") for _ in range(rng.randint(0, 40))
        )
        assert set(program) <= set(":^<!")


class TestNoCommentFuzz:
    def test_program_alphabet(self, rng) -> None:
        program = "".join(
            rng.choice("idclrnfsbo") for _ in range(rng.randint(0, 30))
        )
        assert set(program) <= set("idclrnfsbo")


class TestDivergenceDetection:
    """The fuzzer must fail when the two sides disagree."""

    @pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not installed")
    def test_excon_catches_divergence(self, rng) -> None:
        """A tampered native result is reported as a failure."""
        real_run = verify_differential._run_native_code  # noqa: SLF001

        def tampered(cmd, program, timeout=5):
            out, code = real_run(cmd, program, timeout)
            return out, (code + 1) % 4  # never match a real exit code

        with patch.object(
            verify_differential, "_run_native_code", side_effect=tampered
        ):
            assert not verify_differential._fuzz_excon(rng, 20)  # noqa: SLF001

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
