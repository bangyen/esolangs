"""Tests for the Bruijndejx interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.bruijndejx.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.execution import assert_digit_cap_independent


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_the_pages_examples_and_binding_rules() -> None:
    # The page's two examples: ``*`` halts (a bare final item), the copier
    # copies, ending on EOF through ``?``'s third argument.
    assert _out("*") == ""
    for bits in ("", "0", "1", "0110"):
        assert _out(r"main = *main\.main/.?;", bits) == bits
    # A name keeps its free index free; ``$`` lets the use site bind it.
    assert _out("Z=*/.; F=[1]; main=* Z [$F] :;") == "0"
    with pytest.raises(HaltError, match="unbound"):
        _out("Z=*/.; F=[1]; main=* Z [F] :;")
    # A huge index stops at the environment's end, not after 10^40 links.
    with pytest.raises(HaltError, match="unbound"):
        _out("main=* [" + "9" * 40 + "].;")
    # Call-by-name: an unused looping argument is never evaluated.
    assert _out("loop=loop; main=loop [*].;") == ""
    assert_digit_cap_independent("Bruijndejx", "9" * 4500 + r" [*\.] .", "", "1")
    # Missing operands are index 0 on the left; missing '.' are appended.
    assert _out("main=* [ ].;") == _out("main=* *[[1]]:;") == ""
    for code, message in (
        ("a=*; a=*", "duplicate"),
        ("main=b", "undeclared"),
        ("x; main=*", "bare expression"),
        ("main=[*", "unclosed"),
    ):
        with pytest.raises(ValueError, match=message):
            _out(code)
    with pytest.raises(HaltError, match="argument"):
        _out("* *.")
