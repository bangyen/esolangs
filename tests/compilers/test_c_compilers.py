"""End-to-end tests for the C compilers.

Each C compiler translates an esolang program to C. The test compiles the
compiler with gcc, runs it on a source program, compiles the generated C,
runs it, and checks the output.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

COMPILERS_DIR = Path(__file__).parents[2] / "src/esolangs/compilers/c"

pytestmark = pytest.mark.skipif(
    shutil.which("gcc") is None, reason="gcc is not installed"
)


def compile_and_run(compiler_name: str, source: str, tmp_path: Path) -> bytes:
    """Compile a C compiler, run it on ``source``, and run the generated C."""
    compiler_bin = tmp_path / "compiler"
    result = subprocess.run(
        ["gcc", str(COMPILERS_DIR / compiler_name), "-o", str(compiler_bin)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    source_file = tmp_path / "program.txt"
    source_file.write_text(source)
    result = subprocess.run(
        [str(compiler_bin), str(source_file)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    generated = tmp_path / "output.c"
    assert generated.exists(), "compiler did not produce output.c"

    program_bin = tmp_path / "program"
    result = subprocess.run(
        ["gcc", str(generated), "-o", str(program_bin)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    return subprocess.run([str(program_bin)], capture_output=True).stdout


class TestExcon:
    def test_character(self, tmp_path: Path) -> None:
        assert compile_and_run("excon.c", "^<<<<<<^!", tmp_path) == b"A"

    def test_most_significant_bit(self, tmp_path: Path) -> None:
        assert compile_and_run("excon.c", "<<<<<<<^!", tmp_path) == b"\x80"


class TestBFStack:
    def test_output_value(self, tmp_path: Path) -> None:
        assert compile_and_run("bfstack.c", ">++.", tmp_path) == b"\x02"


class TestBFPDA:
    def test_toggle_and_output(self, tmp_path: Path) -> None:
        assert compile_and_run("bf-pda.c", "@.", tmp_path) == b"1"

    def test_zeros_output(self, tmp_path: Path) -> None:
        assert compile_and_run("bf-pda.c", ".", tmp_path) == b"0"


class TestRAM0:
    def test_increment(self, tmp_path: Path) -> None:
        assert compile_and_run("RAM0.c", "A A A", tmp_path) == b"Z: 3\nN: 0\n"


class TestCFuzzing:
    """C compilers must not crash or emit invalid C on arbitrary input."""

    ALPHABET = "><+-.,[]{}_|#@$%^&*;:?!\\/'\"" + "0123456789" + "ANZLSCxyz \n"

    @pytest.mark.parametrize("compiler", ["bfstack.c", "excon.c", "bf-pda.c", "RAM0.c"])
    def test_random_input_produces_valid_c(self, compiler: str, tmp_path: Path) -> None:
        import random

        compiler_bin = tmp_path / "compiler"
        result = subprocess.run(
            ["gcc", str(COMPILERS_DIR / compiler), "-o", str(compiler_bin)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

        random.seed(11)
        for _ in range(20):
            source = "".join(
                random.choice(self.ALPHABET) for _ in range(random.randint(1, 50))
            )
            src_file = tmp_path / "in.txt"
            src_file.write_text(source)
            result = subprocess.run(
                [str(compiler_bin), str(src_file)],
                cwd=tmp_path,
                capture_output=True,
                text=True,
            )
            assert result.returncode < 128, f"compiler crashed on {source!r}"

            generated = tmp_path / "output.c"
            assert generated.exists(), "compiler produced no output.c"
            check = subprocess.run(
                ["gcc", "-c", "-o", "/dev/null", str(generated)],
                capture_output=True,
                text=True,
            )
            assert (
                check.returncode == 0
            ), f"output.c invalid for {source!r}:\n{check.stderr}"
