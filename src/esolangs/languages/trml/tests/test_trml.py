"""Published and discriminating Trml examples."""

import pytest

from esolangs.languages.trml.interpreter import run
from esolangs.languages.trml.tests.oracle_checks import check_raw_trml
from esolangs.runtime.io import ScriptedIO


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("s;k;`(a)(b);``k(a)(b):(a);```s(a)(b)(c):``(a)(c)`(b)(c);$```skkk", "k"),
        ("a;b;p(x)(y);p(x)(x):a;$pbb", "a"),
        ("a;b;p(x)(y);p(x)(x):a;$pba", "pba"),
        ("a;b;(x)b;z(x):a;$zab", "ab"),
        ("a;b;c;a:b;a:c;$a", "b"),
    ],
)
def test_rewrite(source: str, expected: str) -> None:
    io = ScriptedIO()
    run(source, io)
    assert io.getvalue() == expected


def test_rewrite_model() -> None:
    check_raw_trml()
