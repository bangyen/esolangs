"""Fish instruction semantics."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.fish.interpreter import _advance, _Machine, run
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import FirstDraw
from tests.support.raises import assert_halts_with_hint


def _run(source: str, stdin: str = "", rng: object = None) -> str:
    io = ScriptedIO(stdin)
    run(source.splitlines(), io, rng=rng)
    return io.getvalue()


def _state(
    cells: dict[tuple[int, int], int],
    stack: tuple[object, ...] = (),
    *,
    dx: int = 1,
    dy: int = 0,
    width: int = 1,
    height: int = 1,
    quote: str | None = None,
) -> tuple[object, ...]:
    """Build an explicit Fish core for the pure transition."""
    return (
        0,
        0,
        dx,
        dy,
        cells,
        (stack,),
        (None,),
        quote,
        False,
        width,
        height,
    )


def test_advance_is_pure_and_repeatable() -> None:
    """The transition leaves its argument alone and is a function of it."""
    cells = {(0, 0): ord("p")}
    state = _state(cells, (ord("A"), 0, 0))
    moved, effect = _advance(state)
    again, again_effect = _advance(state)
    assert moved == again
    assert effect == again_effect
    # The input mapping is not written through: ``p`` copies on write.
    assert cells == {(0, 0): ord("p")}
    assert moved[4][(0, 0)] == ord("A")


def test_advance_returns_output_instead_of_writing() -> None:
    """``n``/``o`` report an effect; the transition owns no port."""
    moved, effect = _advance(_state({(0, 0): ord("n")}, (65,)))
    assert effect == ("num", "65")
    assert moved[5] == ((),)
    moved, effect = _advance(_state({(0, 0): ord("o")}, (65,)))
    assert effect == ("char", "A")


def test_advance_takes_its_random_draw_as_an_argument() -> None:
    """``x`` uses the supplied direction; the same call repeats."""
    state = _state({(0, 0): ord("x")})
    first, _ = _advance(state, random_dir=2)
    second, _ = _advance(state, random_dir=2)
    assert first == second
    assert first[2:4] == (-1, 0)


def test_advance_takes_its_input_value_as_an_argument() -> None:
    """``i`` pushes the supplied codepoint, and -1 when the shell saw EOF."""
    state = _state({(0, 0): ord("i")})
    read, _ = _advance(state, char_input=65)
    assert read[5] == ((65,),)
    eof, _ = _advance(state, char_input=None)
    assert eof[5] == ((-1,),)


def test_literals_arithmetic_comparison_and_output() -> None:
    assert _run("23+n;") == "5"
    assert _run("53-n;") == "2"
    assert _run("23*n;") == "6"
    assert _run("53%n;") == "2"
    assert _run("94,n;") == "2.25"
    assert _run("23(n;") == "1"
    assert _run("23)n;") == "0"
    assert _run("22=n;") == "1"
    assert _run("'iH'oo;") == "Hi"
    assert _run('"iH"oo;') == "Hi"


def test_input_returns_minus_one_at_eof() -> None:
    assert _run("iin;", "A") == "-1"


def test_stack_stack_register_and_rotations() -> None:
    assert _run("1233[r]rnnn;") == "321"
    assert _run("12&~&n;") == "2"
    assert _run("123}nnn;") == "213"
    assert _run("123{nnn;") == "132"
    assert _run("1:nn;") == "11"
    assert _run("12$nn;") == "12"
    assert _run("123@nnn;") == "213"
    assert _run("12lnnn;") == "221"
    assert _run("0[]ln;") == "0"
    assert _run("12]ln;") == "0"
    assert _run("1232[]nnn;") == "321"


def test_get_put_and_negative_storage() -> None:
    assert _run("'A'01p01go;") == "A"
    machine = _Machine(["'A'01-01-p;"], ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.cells[(-1, -1)] == ord("A")
    machine = _Machine(["'A'99p;"], ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert (machine.width, machine.height) == (10, 10)


def test_branching_protocol_covers_random_input_plain_and_halted_states() -> None:
    random = _Machine(["x"], ScriptedIO(""))
    start = random.branching_snapshot()
    assert len(random.branching_successors(start, 10) or ()) == 4
    reading = _Machine(["i"], ScriptedIO(""))
    assert reading.branching_successors(reading.branching_snapshot(), 10) is None
    plain = _Machine(["1"], ScriptedIO(""))
    assert len(plain.branching_successors(plain.branching_snapshot(), 10) or ()) == 1
    halted = _Machine([";"], ScriptedIO(""))
    halted.step()
    final = halted.branching_snapshot()
    assert halted.branching_halted(final)
    assert halted.branching_successors(final, 10) == (final,)
    halted.step()


def test_errors_are_fishy() -> None:
    # a negative jump target and a non-codepoint 'o' are errors (author's fish.py),
    # and so are a tab and a newline that 'p' writes: only a space is a NOP
    errors = ("~;", "10,;", "10%;", "};", "{;", "2[;", "z;", "01-0.;", "01-o;")
    for source in (*errors, "\t;", "1a60p 2n;"):
        with pytest.raises(HaltError, match="fishy"):
            _run(source)
    fractional = (
        0,
        0,
        1,
        0,
        {(0, 0): ord("p")},
        ((2.5, 0, 0),),
        (None,),
        None,
        False,
        1,
        1,
    )
    with pytest.raises(HaltError, match="fishy"):
        _advance(fractional)


def test_integral_floats_print_without_a_decimal_point() -> None:
    """Author's fish.py prints ``int(n)`` when ``n`` is whole: 8/4 is ``2``."""
    assert _run("84,n;") == "2"


def test_float_overflow_is_fishy() -> None:
    """0.5 times 15**512 overflows a float: a Fish error, not a host crash."""
    with pytest.raises(HaltError, match="fishy"):
        _run("12,f" + ":*" * 9 + "*n;")


def test_large_integers_print_past_the_host_digit_limit() -> None:
    """15**4096 has 4818 digits, beyond Python's default str() limit."""
    out = _run("f" + ":*" * 12 + "n;")
    assert len(out) == 4818
    assert out.startswith("1")
    assert out.endswith("5")


def test_quoted_x_and_i_are_literals_in_the_branch_search() -> None:
    """Inside a string, ``x`` pushes 120 (one successor) and ``i`` pushes 105."""
    for code in ("'x", "'i"):
        machine = _Machine([code], ScriptedIO(""))
        machine.step()  # enter string mode; the IP now sits on the letter
        (successor,) = (
            machine.branching_successors(machine.branching_snapshot(), 10) or ()
        )
        assert successor[5] == ((ord(code[1]),),)


def test_branch_successors_keep_a_grown_codebox() -> None:
    """A state whose ``p`` grew the box to width 10 keeps it when searched."""
    grown = _Machine(["' '90p"], ScriptedIO(""))
    for _ in range(6):
        grown.step()
    fresh = _Machine(["' '90p"], ScriptedIO(""))
    (successor,) = fresh.branching_successors(grown.branching_snapshot(), 10) or ()
    assert successor[:2] == (7, 0)


def test_a_missing_codebox_cell_is_a_nop() -> None:
    machine = _Machine(["v", ""], ScriptedIO(""))
    machine.step()
    machine.step()
    assert machine.ip == (0, 0, 0, 1)
    # a string pushes a missing cell as 0, its 'g' value (fish.py: a space)
    machine = _Machine(['"', "ab"], ScriptedIO(""))
    machine.step()
    machine.step()
    assert machine.stack == [0]


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([], ScriptedIO(""))


def test_movement_mirrors_jump_and_trampolines() -> None:
    assert _run("1!9n;") == "1"
    # '?' skips when the popped value is 0 (wiki; author's fish.py agrees)
    assert _run("10?9n;") == "1"
    assert _run("01?9n;") == "9"
    assert _run("20.9n;") == "9"
    # a jump past the box re-enters it modulo its width (fish.py: wraps to 0)
    assert _run("1n f0. 2n;") == "12"
    assert _run("x;", rng=FirstDraw(0)) == ""
    machine = _Machine(["/ ", " ;"], ScriptedIO(""))
    machine.step()
    assert machine.ip == (1, 0, 0, -1)

    headings = {
        ">": (1, 0),
        "<": (-1, 0),
        "^": (0, -1),
        "v": (0, 1),
    }
    for command, heading in headings.items():
        machine = _Machine([command], ScriptedIO(""))
        machine.step()
        assert (machine.dx, machine.dy) == heading

    for command, start, expected in (
        ("/", (1, 0), (0, -1)),
        ("\\", (1, 0), (0, 1)),
        ("|", (1, 0), (-1, 0)),
        ("_", (0, 1), (0, -1)),
        ("#", (1, 0), (-1, 0)),
    ):
        state = (
            0,
            0,
            start[0],
            start[1],
            {(0, 0): ord(command)},
            ((),),
            (None,),
            None,
            False,
            1,
            1,
        )
        moved, _ = _advance(state)
        assert moved[2:4] == expected


#: The wiki's four Hello, world! programs, its one-space indent removed.
_WIKI_HELLO = (
    '>"Hello, world!"0r>o:?v;\n                  ^   <',
    '"!dlrow ,olleH"l?!;oe0.',
    "98*oaa*1+o9c*o9c*oba*\\\n1+ob4*o84*of2+7*oba*1\\\n+of4+6*oc9*oaa*ob3*o;\\",
    "98*ob3*aa*:1+o9c*:\\\no;!*4b*48+8o::-3:+\\!6o:|ooo",
)


@pytest.mark.parametrize("source", _WIKI_HELLO)
def test_the_wiki_hello_worlds(source: str) -> None:
    assert _run(source) == "Hello, world!"


def test_the_wiki_fizzbuzz_counts_to_one_hundred() -> None:
    source = (
        "0voa                            ~/?=0:\\\n"
        " voa            oooo'Buzz'~<     /\n"
        " >1+:aa*1+=?;::5%:{3%:@*?\\?/'zziF'oooo/\n"
        " ^oa                 n:~~/"
    )
    lines = _run(source).splitlines()
    assert len(lines) == 100
    assert lines[:5] == ["1", "2", "Fizz", "4", "Buzz"]
    assert lines[14] == "FizzBuzz"
    assert lines[-2:] == ["Fizz", "Buzz"]


def test_the_wiki_quines_print_their_source() -> None:
    """The multi-line quine reads 24 columns a row.

    The wiki copy lost its last row's trailing space, so the quine then reads
    an empty cell (0) there; restoring that one space is the only repair.
    """
    assert _run('"r00gol?!;40.') == '"r00gol?!;40.'
    quine = (
        "0>:a$f8+$p1+:5-?vv     \n"
        " ^              <>~0v  \n"
        "v             <     <  \n"
        ">0v          ;^?-6:+1~<\n"
        "v <                  < \n"
        ">$:{:}$go$   1+:f9+-?^^ "
    )
    assert _run(quine) == quine
    assert _run(quine.rstrip(" ")).endswith("^^\x00")


@pytest.mark.medium
def test_hints_for_bad_programs_and_input() -> None:
    assert_halts_with_hint("Fish", "+", "something smells fishy", "push a value")


def test_only_x_draws_from_the_source() -> None:
    """The first draw is ``x``'s, however many commands run before it."""
    assert _run("1nx;", rng=FirstDraw(0, rest=2)) == "1"


def test_jumping_to_column_zero_is_allowed() -> None:
    assert _run("01.\n 9n;") == "9"


def test_the_quote_view_names_the_open_quote() -> None:
    machine = _Machine(['"a"'], ScriptedIO(""))
    assert machine.quote is None
    machine.step()
    assert machine.quote == '"'
    machine.step()
    machine.step()
    assert machine.quote is None


def test_the_last_codepoint_is_printable_and_the_next_is_not() -> None:
    horner = "1" + "".join(f"f1+*{digit}+" for digit in "0ffff")  # 0x10FFFF
    assert _run(horner + "o;") == "\U0010ffff"
    with pytest.raises(HaltError, match="smells fishy"):
        _run(horner + "1+o;")
