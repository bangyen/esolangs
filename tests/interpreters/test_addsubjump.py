"""Assembly rejection cases and published AddSubJump programs."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.addsubjump import _assembly, run


class TestAssemblyErrors:
    @pytest.mark.parametrize(
        ("code", "message"),
        [
            ("def", "malformed .*macro"),
            ("def bad A { extra", "malformed .*macro"),
            ("def bad {\n{\n}\n", "nested"),
            ("def bad {", "missing"),
            ("def bad {\n}\ndef bad {\n}", "duplicate macro"),
            ("def loop {\nloop\n}\nloop", "recursive macro"),
            ("def one A {\n.data A\n}\none", "takes 1 arguments"),
            ("def bad {\n:label 1 2\n}\nbad", "empty AddSubJump label"),
            (":bad 1 2", "empty AddSubJump label"),
            ("IO: 1 2", "duplicate label"),
            (".data :1", "empty AddSubJump label"),
            (".data A:1 A:2", "duplicate label"),
            ("1", "needs 2 to 4 operands"),
            ("1 2 3 4 5", "needs 2 to 4 operands"),
            (".data $", "invalid AddSubJump operand"),
        ],
    )
    def test_malformed_assembly_is_rejected(self, code: str, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            _assembly(code)


def test_malformed_token() -> None:
    with pytest.raises(ValueError, match="undefined label 'x'"):
        run("12 -6 x -7", ScriptedIO())


# The wiki's assembler ships an ``IFZ`` macro; this repo's dialect has the
# ``def`` blocks but no macro library, so the two wiki programs below carry
# their own.  ``IFZ X Z P`` is "goto Z if *X == 0, else goto P": it copies
# ``*X`` under flag-update mode so ZF answers the test, then adds or
# subtracts 4 from a goto's own ``c`` cell to pick one of two trampolines
# four cells either side of its resting value.  Each trampoline undoes the
# move before jumping, so the macro is re-entrant -- the hello-world loop
# runs it thirteen times.
_IFZ = """
def IFZ X Z P {
  T2 T2 ? @1
  T2 X ?
  g+2 D4 ? ZF
  g: @0 @0 g+8
  g+2 D4 ?
  @0 @0 Z
  g+2 D4 ? @1
  @0 @0 P
  D4:.data 4
  T2:.data 0
}
"""

_CMP = """
def CMP A B {
  temp temp ? @1
  temp A ?
  temp B ? @1
}
"""

# The wiki's truth machine, verbatim but for two things: the ``FUM`` line
# that arms IFZ's zero test, and cell B, which holds -48 so that the
# comparison sees the digit and not its ASCII byte (this repo's port reads
# bytes; the wiki program assumes a numeric read).  The jump structure --
# ``loop:`` naming itself as ``c``, ``end:`` halting on the literal -1 -- is
# the wiki's and is exactly what the literal semantics buys.
_TRUTH_MACHINE = (
    _IFZ
    + """
FUM @1
A IO
B A
IFZ B end loop
loop: IO A loop
end: IO A -1
A:.data 0
B:.data -48
"""
)

# The wiki's hello world.  ``start+1`` replaces the wiki's literal ``1``
# (the ``FUM`` line shifts every address by one instruction) and ``temp``
# is declared in the program because macro-local labels are private per
# expansion, so CMP's result has to be a shared name.
_HELLO_WORLD = (
    _IFZ
    + _CMP
    + """
FUM @1
start: IO H
start+1 @1
CMP start+1 E
IFZ temp IO start
.data H: 72 101 108 108 111 44 32 119 111 114 108 100 33 E:E
temp:.data 0
"""
)


def _capped(code: str, stdin: str, cap: int) -> tuple[str, bool, int]:
    """Run at most ``cap`` instructions; return output, halted, steps taken."""
    from esolangs.interpreters.register_based.addsubjump import _Machine

    machine = _Machine(code, ScriptedIO(stdin))
    steps = 0
    while not machine.halted and steps < cap:
        machine.step()
        steps += 1
    return machine.io.getvalue(), machine.halted, steps


class TestWikiPrograms:
    """The wiki's own two programs, which only run under ``goto c``.

    Both are load-bearing for the jump semantics: the truth machine's loop
    is ``loop: IO A loop``, a literal self-reference, and both halt with
    ``c = -1``.  Dereferencing ``c`` would send -1 to memory[0] instead.
    """

    def test_truth_machine_prints_zero_and_halts(self) -> None:
        assert _capped(_TRUTH_MACHINE, "0", 100) == ("0", True, 10)

    def test_truth_machine_loops_on_one(self) -> None:
        # Capped rather than waited out: the loop is one instruction, so a
        # thousand steps is a thousand ones and no halt.
        output, halted, steps = _capped(_TRUTH_MACHINE, "1", 1000)
        assert (output, halted, steps) == ("1" * 991, False, 1000)

    def test_hello_world(self) -> None:
        assert _capped(_HELLO_WORLD, "", 10_000) == ("Hello, world!", True, 144)
