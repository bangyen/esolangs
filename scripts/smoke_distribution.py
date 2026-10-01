"""Exercise an installed distribution, CLI, raster paths, and math extra."""

from __future__ import annotations

import argparse
import importlib.util
import signal
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import esolangs


def _cli(args: list[str], stdin: str = "") -> str:
    result = subprocess.run(
        [sys.executable, "-I", "-m", "esolangs", *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout


def _refuses_timeout() -> None:
    try:
        esolangs.run("brainfuck", "+.", timeout=0.1)
    except esolangs.ArgumentError as exc:
        message = str(exc)
    else:
        raise AssertionError("unsupported signal timeout was accepted")
    assert "Unix main thread" in message


def smoke(*, math_extra: bool) -> None:
    """Check installed resources and behaviour outside the source checkout."""
    package = Path(esolangs.__file__).resolve().parent
    assert package.parent.name in {"site-packages", "dist-packages"}, package
    assert (package / "py.typed").is_file()
    assert "brainfuck" in _cli(["list"])
    bound = esolangs.Language("BRAINFUCK")
    program = bound.generate("0110", balance=True)
    assert bound.evaluate(program, inputs=2) == "0110"
    assert bound.read_answer(bound.run(program, bound.encode_inputs([0, 1]))) == "1"
    assert esolangs.run("brainfuck", "+.", max_steps=2, timeout=1) == "\x01"
    try:
        esolangs.run("brainfuck", "+[]", max_steps=10)
    except esolangs.ExecutionTimeoutError:
        pass
    else:
        raise AssertionError("the bounded runner accepted a diverging program")

    executable = Path(sys.executable).with_name(
        "esolangs.exe" if sys.platform == "win32" else "esolangs"
    )
    entrypoint = subprocess.run(
        [str(executable), "list"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "brainfuck" in entrypoint.stdout
    for name in esolangs.list_languages():
        facts = esolangs.describe(name)
        if facts["boolean_generator"] and facts["source_kind"] == "text":
            assert facts["examples"], name
            for filename in facts["examples"]:
                path = Path(filename)
                assert path.is_relative_to(package), filename
                assert path.is_file(), filename
    examples = esolangs.describe("brainfuck")["examples"]
    assert examples
    example = Path(examples[0])
    assert (
        esolangs.read_answer("brainfuck", esolangs.run("brainfuck", example, "0\n1\n"))
        == "0"
    )
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "xor.txt"
        source.write_text(_cli(["generate", "brainfuck", "0110"]), encoding="utf-8")
        for row in range(4):
            stdin = esolangs.encode_inputs("brainfuck", [row >> 1, row & 1])
            assert (
                esolangs.read_answer(
                    "brainfuck", _cli(["run", "brainfuck", str(source)], stdin)
                )
                == "0110"[row]
            )
        assert (
            _cli(["evaluate", "--table", "0110", "brainfuck", str(source)]).strip()
            == "0110"
        )
        source.write_text(",>,<.", encoding="utf-8")
        assert (
            _cli(["evaluate", "--inputs", "2", "brainfuck", str(source)]).strip()
            == "0011"
        )
    for language in ("Line", "Piet"):
        raster = esolangs.generate(language, "0110")
        assert isinstance(raster, esolangs.Raster)
        decoded = esolangs.Raster.from_png(raster.to_png())
        for row in range(4):
            bits = [row >> 1, row & 1]
            output = esolangs.run(
                language, decoded, esolangs.encode_inputs(language, bits)
            )
            assert esolangs.read_answer(language, output) == "0110"[row]
    if hasattr(signal, "SIGALRM"):
        assert (
            esolangs.evaluate(
                "brainfuck", esolangs.generate("brainfuck", "0110"), timeout=1, inputs=2
            )
            == "0110"
        )
        try:
            esolangs.run("brainfuck", "+[]", timeout=0.02)
        except esolangs.ExecutionTimeoutError:
            pass
        else:
            raise AssertionError("signal timeout did not stop a loop")
    else:
        _refuses_timeout()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_refuses_timeout).result(timeout=5)
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert (
            pool.submit(
                esolangs.evaluate,
                "Suffolk",
                esolangs.generate("Suffolk", "0110"),
                inputs=2,
                isolated=True,
            ).result(timeout=30)
            == "0110"
        )
    assert (
        esolangs.evaluate(
            "123", esolangs.generate("123", "01"), inputs=1, isolated=True
        )
        == "01"
    )
    try:
        esolangs.run("brainfuck", "+[]", timeout=0.5, isolated=True)
    except esolangs.ExecutionTimeoutError:
        pass
    else:
        raise AssertionError("isolated timeout did not stop a loop")
    assert (
        esolangs.evaluate("123", esolangs.generate("123", "01"), timeout=None, inputs=1)
        == "01"
    )
    if math_extra:
        assert importlib.util.find_spec("sympy") is not None
        assert (
            esolangs.evaluate(
                "Polynomial",
                esolangs.generate("Polynomial", "01"),
                timeout=None,
                inputs=1,
            )
            == "01"
        )
    else:
        assert importlib.util.find_spec("sympy") is None
        try:
            esolangs.run("Polynomial", "f(x) = x - 2")
        except esolangs.MissingDependencyError:
            pass
        else:
            raise AssertionError("Polynomial ran without its math extra")


def main() -> None:
    """Run the artifact smoke check with or without its optional extra."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math", action="store_true")
    args = parser.parse_args()
    smoke(math_extra=args.math)
    print("installed distribution smoke check passed")


if __name__ == "__main__":
    main()
