"""Tests for the Pilas interpreter."""

import pytest

from esolangs.languages.pilas.interpreter import run
from tests.interpreters.runner import native_runner

_out = native_runner(run)


def test_arithmetic_pops_a_then_b() -> None:
    from esolangs.languages.pilas.tests.oracle_checks import check_raw_pilas

    check_raw_pilas()
    # 9 6 - is b - a = 3, printed as '3' after adding 48.
    assert _out("96-6:+:+:++.\n0{0}") == "3"


def test_lines_alternate_and_tilde_crosses() -> None:
    # Line one moves 7 over; line two then prints 7 + 41 = '0'.
    assert _out("7~" + " " * 14 + "\n  6:+:+:+7-+.") == "0"


def test_brace_loops_while_zero_on_its_own_line() -> None:
    # Counts 0 up to 1 once: the body runs, then the 1 exits.
    assert _out("0{1}6:+:+:+.\n0{0}") == "0"


def test_halts_when_either_pointer_runs_off() -> None:
    assert _out("6:+:+:+.\n1") == ""


def test_wiki_while_zero_translation() -> None:
    # The page's loop, entered on a zero cell and left once it is set.
    code = "0:~:{1+:~:}6:+:+:+1+.\n    {    }0{0}          "
    assert _out(code) == "1"


def test_reads_bytes(tmp_path, monkeypatch) -> None:
    import esolangs

    source = ",.\n  "
    assert _out(source, "A") == "A"
    api = esolangs.Language("Pilas")
    path = tmp_path / "source.txt"
    path.write_bytes((source + "\r\n").encode())
    assert api.from_file(path).source == source + "\r\n"
    for program in (source + "\r\n", path):
        for options in ({}, {"max_steps": 100}):
            with pytest.raises(esolangs.ProgramError, match="lines"):
                api.run(program, stdin="A", **options)
    native = api.from_file(path, normalize=True)
    assert native.source == source
    assert api.run(native, stdin="A").output == "A"
    api.save_program(api.from_source(source), path)
    assert path.read_bytes() == source.encode()
    assert api.run(path, stdin="A").output == "A"
    api.save_program(api.from_source(source), path, normalize=True)
    assert path.read_bytes() == (source + "\n").encode()

    from esolangs.languages.pilas import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Pilas",
        ",.1{x}xx\nxxxxxxxxx",
        interpreter,
        "_parse",
        monkeypatch,
    )


@pytest.mark.parametrize(
    ("code", "match"),
    [("{\n", "unmatched"), ("}\n", "unmatched"), ("a\nb\nc", "lines")],
)
def test_malformed_programs(code: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _out(code)
