"""Smu: the wiki cat, command edges, the preprocessor, and generated programs."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.smu import preprocess, run
from esolangs.tools.smu import smu
from tests.witness_tables import witnesses

CAT = "x(+|)xg()+gy(g)ybx=(=)y=xy+x=ba(bxggxg)aa(|=)=a(+=)=baxg"
_A = "((+|)=(=)(()+)=(+|)(()+)+(+|)=(+|)()+()+(+|)()+)"
#: The wiki's "expanded form" drops the ``=`` after ``(+=)``.
PRINTED = f"{_A}(|=)={_A}(+=)(+|)=(=)(()+)=(+|)(()+)+(+|)={_A}(+|)()+"
REPAIRED = PRINTED.replace("(+=)(+|)", "(+=)=(+|)")


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_wiki_cat_copies_every_byte() -> None:
    text = "".join(map(chr, range(256)))
    assert _run(CAT, text) == text
    assert _run(CAT) == ""


def test_wiki_expanded_form_is_the_cat_less_one_equals() -> None:
    """The compact source fixes the repair; the printed form forces a 1 first."""
    assert preprocess(CAT) == REPAIRED
    assert _run(PRINTED, "\x00") == "\x01"
    assert _run(PRINTED, "\x02") == "\x03"


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        # ``=`` assigns the second string to the top's name; ``+`` reads an
        # unset ``""`` as empty.
        ("(+)(|)=(|)()+", "", "\x01"),
        # ``|`` leaves the head on top: ``|`` is assigned ``+``, not ``||``.
        ("(+||)|(|)=(|)()+", "", "\x01"),
        ("()|(+)", "", "\x01"),  # an empty string is popped, nothing pushed
        ("=+", "", ""),  # underflow is a no-op; EOF's ``=`` prints nothing
        ("()=|", "", ""),
        ("", "A", "\x01"),  # the run's bit is the byte's low bit
        ("", "\x02", "\x00"),
        ("1a(+)1a & a comment\n 1a", "", "\x01"),
        ("7(+)", "", "\x01"),  # digits naming no macro are dropped
    ],
)
def test_commands(code: str, stdin: str, expected: str) -> None:
    assert _run(code, stdin) == expected


@pytest.mark.parametrize("code", ["(+", ")", "a(b)a", "a(+)"])
def test_malformed_source(code: str) -> None:
    with pytest.raises(ValueError):
        _run(code)


@pytest.mark.parametrize(
    "code",
    [
        "((()+))|",  # outputs ``(``
        "((()+))|(())=(+)",  # runs ``()+)``
    ],
)
def test_runtime_halts(code: str) -> None:
    with pytest.raises(HaltError):
        _run(code)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_generated_programs(n: int) -> None:
    for table in witnesses(n):
        code = smu(table)
        for row in range(1 << n):
            assert _run(code, f"{row:0{n}b}") == table[row], (table, row)
