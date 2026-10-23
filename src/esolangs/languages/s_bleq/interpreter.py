r"""Interpreter for S*bleq.

A subtract-and-branch machine: each instruction ``a b c`` does ``mem[a] -= mem[b]``
and, if the result is ``<= 0``, jumps to ``mem[c]`` (indirect); otherwise
the pointer advances by three.  Address ``-1`` is the instruction
pointer, ``-2`` the next input character (zero at EOF), ``-3``
outputs the other operand; none appears in ``c``.  ``store`` selects the
base (``a``), ``S*bl*q`` (``a`` and ``b``) or ``Subl*q`` (``b``)
variant, and ``indirect`` the ``S**bleq``/``Subl**q``/``S**bl**q`` family,
which replaces ``a`` and ``b`` by ``*a`` and ``*b``.

Programs are whitespace-separated integers loaded at address zero; reads
past the end are zero.  Execution halts off the end of the program (fewer
than three cells left at the pointer) or on a negative jump target; the
wiki names no halt.

Input/output:
    ``-2`` reads one input character, zero at EOF; ``-2`` in both operands
    is one read, not two.  ``-3`` prints the other operand.

Errors:
    ProgramError: A non-integer program token; a negative ``c``, raised when
    its instruction runs, jump taken or not (after a ``-3`` print); an
    address below ``-3``; an unknown ``store``; under ``indirect``, a
    negative ``a`` or ``b``.
    InterpreterLimitError: A store to an address past the cell limit.

Decisions:
    * The wiki does not say whether the special addresses apply before or
      after the indirection; here ``*a`` is the address held at cell ``a``,
      so it may itself be ``-1``, ``-2`` or ``-3``, and an ``a`` that is
      already negative raises.
    * Bare "-1 IP", "-2 returns next byte of user input" and "none of which
      could be in ``c``": writing ``-1`` moves the pointer and a result
      above zero then advances three from there.
"""

from collections.abc import Sequence

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._validate import check_address
from esolangs.runtime.io import IO
from esolangs.runtime.memory import format_integer
from esolangs.runtime.memory import parse_int_memory as _parse
from esolangs.runtime.source_hints import syntax_error

# The three store targets the wiki defines: base S*bleq, S*bl*q, Subl*q.
_STORES = ("a", "ab", "b")


#: One instant of a run's control: ``(ip, halted)`` -- the instruction pointer
#: and whether a negative jump stopped the run.  The self-modifying memory is
#: not in it: a transition reads it through ``mem`` and returns its cell
#: writes, because threading a tuple copy per write made a row's cost
#: quadratic in program size.
#:
#: ``halted`` is carried because a jump to a negative address stops the run
#: with the pointer left where it was, so the position alone does not say.
type _State = tuple[int, bool]

#: ``(address, value)`` cell stores, in order, for the shell to apply.
type _Writes = tuple[tuple[int, int], ...]


def _read(mem: Sequence[int], ip: int, addr: int, byte: int | None = None) -> int:
    """Read a value: a special address or a memory cell.

    ``byte`` is what the shell took from the input port for ``-2``.
    """
    if addr == -1:
        return ip
    if addr == -2:
        return byte if byte is not None else 0
    if addr >= 0:
        return mem[addr] if addr < len(mem) else 0
    raise syntax_error(
        f"invalid address {format_integer(addr)}",
        (
            "use a nonnegative memory address, -1 for the instruction "
            "pointer or -2 for input"
        ),
    )


def _operands(mem: Sequence[int], ip: int, *, indirect: bool) -> tuple[int, int]:
    """Return ``a`` and ``b``, read through the cells they name if indirect."""
    a, b = mem[ip], mem[ip + 1]
    if not indirect:
        return a, b
    for operand in (a, b):
        if operand < 0:
            raise syntax_error(
                f"indirect S*bleq operand {format_integer(operand)} names no cell",
                "use a nonnegative cell holding the address in S**bleq variants",
            )
    return (
        mem[a] if a < len(mem) else 0,
        mem[b] if b < len(mem) else 0,
    )


def _advance(
    state: _State,
    mem: Sequence[int],
    store: str,
    byte: int | None = None,
    *,
    indirect: bool = False,
) -> tuple[_State, _Writes]:
    """Return the control state and cell writes of one ``a b c`` instruction.

    Pure; output is the caller's, input arrives as ``byte``.
    The variant selects the destinations, including pointer writes.
    """
    ip, _halted = state
    a, b = _operands(mem, ip, indirect=indirect)
    c = mem[ip + 2]
    if c < 0:
        raise syntax_error(
            f"invalid S*bleq branch address {format_integer(c)}",
            "use a nonnegative branch address",
        )
    if a == -3 or b == -3:
        # The print already happened in the shell.
        return (ip + 3, False), ()

    diff = _read(mem, ip, a, byte) - _read(mem, ip, b, byte)
    writes: list[tuple[int, int]] = []
    for addr in {"a": (a,), "ab": (a, b), "b": (b,)}[store]:
        if addr >= len(mem):
            check_address(addr, "S*bleq")
        if addr >= 0:
            writes.append((addr, diff))
        elif addr == -1:
            ip = diff

    if diff > 0:
        return (ip + 3, False), tuple(writes)
    # ``c`` may be a cell this very instruction wrote.
    target = next(
        (value for addr, value in reversed(writes) if addr == c),
        mem[c] if c < len(mem) else 0,
    )
    if target < 0:
        return (ip, True), tuple(writes)
    return (target, False), tuple(writes)


class _Machine:
    #: Whether a read past the end of the input yields a *value* here
    #: rather than raising.  A few languages do; the rest raise
    #: :class:`~esolangs.exceptions.InputExhaustedError`, which is the
    #: package norm and what :func:`esolangs.run` documents; this one does
    #: not, so an underfed program answers a different row of its table
    #: instead of refusing, and a caller has no way to tell from the output
    #: that it happened.
    #:
    #: Declared rather than changed.  The zero-beyond-input convention was
    #: audited against every wiki page and settled deliberately
    #: (``docs/limitations.md``, Interpreter conventions); rewriting it
    #: would be a decision about what these languages *mean*, not a fix.
    #: What was wrong was that nothing said so, so the promise ``run`` made
    #: was false for seven languages and a generic caller could not find
    #: out which.
    eof_is_a_value = True

    def __init__(
        self, code: str, io: IO, store: str = "a", *, indirect: bool = False
    ) -> None:
        """Build a machine over the cells ``code`` parses to."""
        self.io = io
        self.mem = _parse(code)
        self.ip = 0
        self.store = store
        self.indirect = indirect
        self._halted = False
        if store not in _STORES:
            raise syntax_error(
                f"unknown store target: {store!r}", "choose store a, ab or b"
            )

    @property
    def halted(self) -> bool:
        """Whether the instruction pointer has run off the program."""
        return self._halted or not (0 <= self.ip < len(self.mem) - 2)

    # The VM's language-shaped view: OISC cells + instruction pointer; memory is the
    # program memory.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.mem)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.mem), self.ip, self.io.progress(), self._halted)

    def input_byte(self) -> int:
        # -2 returns the next byte of input; EOF reads as zero
        try:
            return self.io.input_char()
        except (EOFError, IndexError):
            return 0

    def output(self, value: int) -> None:
        self.io.print_char(chr(value & 0xFF))

    def step(self) -> None:
        """Execute one instruction (``a b c``), advancing or branching.

        ``-3`` in either slot prints the other; ``-2`` in either is one
        read, shared by both operands.
        """
        if self.halted:
            return
        a, b = _operands(self.mem, self.ip, indirect=self.indirect)
        byte = self.input_byte() if -2 in (a, b) else None
        if a == -3 or b == -3:
            other = b if a == -3 else a
            self.output(_read(self.mem, self.ip, other, byte))
            byte = None
        (self.ip, self._halted), writes = _advance(
            (self.ip, self._halted),
            self.mem,
            self.store,
            byte,
            indirect=self.indirect,
        )
        for addr, value in writes:
            if addr >= len(self.mem):
                self.mem.extend([0] * (addr + 1 - len(self.mem)))
            self.mem[addr] = value


def run(code: str, io: IO, store: str = "a", *, indirect: bool = False) -> None:
    """Execute an S*bleq program.

    ``store`` is ``"a"`` (base), ``"ab"`` (S*bl*q) or ``"b"`` (Subl*q);
    ``indirect`` gives S**bleq, S**bl**q and Subl**q respectively.
    """
    drive(_Machine(code, io, store=store, indirect=indirect))


if __name__ == "__main__":
    script_main(run)
