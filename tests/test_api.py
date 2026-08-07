"""Tests for the public package API."""

import pytest

import esolangs
from esolangs.tools import boolean


@pytest.mark.parametrize("language", ["Sophie", "CircleFuck", "BFStack", "huf"])
def test_generate_round_trips(language):
    program = esolangs.generate(language, "Hi")
    assert esolangs.run(language, program) == "Hi"


def test_run_feeds_stdin():
    program = boolean.circlefuck("1101", 2)
    assert esolangs.run("CircleFuck", program, stdin="1\n0\n") == "0"
    assert esolangs.run("CircleFuck", program, stdin="0\n1\n") == "1"


def test_list_languages():
    names = esolangs.list_languages()
    assert "Sophie" in names
    assert "CircleFuck" in names
    assert names == sorted(names)


def test_unknown_language_raises():
    with pytest.raises(ValueError, match="unknown language"):
        esolangs.generate("NoSuchLanguage", "x")
    with pytest.raises(ValueError, match="unknown language"):
        esolangs.run("NoSuchLanguage", "x")
