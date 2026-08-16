"""A step-and-inspect interface for the interpreter suite.

:func:`make_vm` wraps one of the step-capable interpreters in a :class:`VM`
that exposes the run state between commands: ``step()`` executes one command,
and the ``halted``/``output``/``ip``/``memory``/``stack`` properties describe
the machine after it.  The fields are language-shaped rather than uniform:
a tape language exposes its cells and code cursor, an OISC its cells and
instruction pointer, and a stack language its stack (empty ``stack`` where a
language has none).

The interpreters whose state objects expose ``step()``/``halted`` are the
ones the VM can wrap; the rest of the registry runs whole programs only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from esolangs.exceptions import UnknownLanguageError
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import RUNNERS


@runtime_checkable
class VM(Protocol):
    """A step-capable interpreter wrapper.

    ``ip``/``memory``/``stack`` are language-shaped: each adapter exposes
    what the language's state actually is, so a tape language's ``memory``
    is its cells, a stack language's ``stack`` its values, and so on.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def output(self) -> str:
        """Everything the machine has written so far."""

    @property
    def ip(self) -> int:
        """The current code or instruction position."""

    @property
    def memory(self) -> list[int]:
        """The addressable cells, or ``[]`` where there is no such store."""

    @property
    def stack(self) -> list[object]:
        """The stack, or ``[]`` where the language has none."""


class _BaseVM:
    """Shared ``output`` capture and the run-state accessor plumbing.

    Subclasses supply ``step``, ``halted``, and the language-shaped
    ``ip``/``memory``/``stack``; ``output`` is captured here.
    """

    def __init__(self, program: str | list[str], stdin: str = "") -> None:
        """Create a VM for ``program`` reading input from ``stdin``."""
        self._io = ScriptedIO(stdin)
        self._program = program

    @property
    def output(self) -> str:
        return self._io.getvalue()

    def step(self) -> None:
        raise NotImplementedError

    @property
    def halted(self) -> bool:
        raise NotImplementedError

    @property
    def ip(self) -> int:
        raise NotImplementedError

    @property
    def memory(self) -> list[int]:
        raise NotImplementedError

    @property
    def stack(self) -> list[object]:
        raise NotImplementedError


class _BrainfuckVM(_BaseVM):
    """Tape + pointer; ``ip`` is the code cursor, ``memory`` the tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.brainfuck import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ind

    @property
    def memory(self) -> list[int]:
        return list(self._machine.tape)

    @property
    def stack(self) -> list[object]:
        return []


class _SbleqVM(_BaseVM):
    """OISC cells + instruction pointer; ``memory`` is the program memory."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.sbleq import _Machine

        self._machine = _Machine(io=self._io, mem=[int(tok) for tok in program.split()])

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ip

    @property
    def memory(self) -> list[int]:
        return list(self._machine.mem)

    @property
    def stack(self) -> list[object]:
        return []


class _DimensionalVM(_BaseVM):
    """Pointer hierarchy; ``ip`` is the code cursor, ``memory`` the axes."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.dimensional import _Runner

        self._runner = _Runner(program, self._io)

    @property
    def halted(self) -> bool:
        return self._runner.halted

    def step(self) -> None:
        self._runner.step()

    @property
    def ip(self) -> int:
        return self._runner.ind

    @property
    def memory(self) -> list[int]:
        # the single byte the pointer hierarchy currently addresses
        return [self._runner.machine.value()]

    @property
    def stack(self) -> list[object]:
        return []


class _GraphemeVM(_BaseVM):
    """Stack + variables; ``ip`` is the active call frame's cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.grapheme import _Frame, _Machine

        if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in program):
            raise ValueError(
                "Grapheme programs may only contain uppercase Latin letters"
            )
        self._machine = _Machine(self._io, 1_000_000)
        self._machine.frames.append(_Frame(program, 0))

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return (
            self._machine.frames[-1].pc if self._machine.frames else len(self._program)
        )

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)


class _QoiblVM(_BaseVM):
    """256-entry variable list; ``ip`` is the expression cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.qoibl import State

        self._state = State(io=self._io)
        self._state.code = program.splitlines()

    @property
    def halted(self) -> bool:
        return self._state.halted

    def step(self) -> None:
        self._state.step()

    @property
    def ip(self) -> int:
        return self._state.ind

    @property
    def memory(self) -> list[int]:
        return [self._state.var.get(k, 0) for k in range(256)]

    @property
    def stack(self) -> list[object]:
        return []


class _EvalVM(_BaseVM):
    """Two stacks + active index; ``ip`` is the code cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.eval import State

        self._state = State(io=self._io, sym=program)

    @property
    def halted(self) -> bool:
        return self._state.halted

    def step(self) -> None:
        self._state.step()

    @property
    def ip(self) -> int:
        return self._state.ind

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._state.stk[self._state.ptr])


class _ModulousVM(_BaseVM):
    """Stack + variables; ``ip`` is the token cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        import re

        from esolangs.interpreters.stack_based.modulous import State

        self._state = State(var={f"VAR{k}": 0 for k in range(1, 5)}, io=self._io)
        self._state.tokens = [
            k[0] for k in re.compile(r'\[([^\[\]\"]*("[^"]*")?)]').findall(program)
        ]

    @property
    def halted(self) -> bool:
        return self._state.halted

    def step(self) -> None:
        self._state.step()

    @property
    def ip(self) -> int:
        return self._state.ind

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._state.stk)


class _TemporaryStackVM(_BaseVM):
    """Single stack + output mode; ``ip`` is the word pointer."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.the_temporary_stack import State

        self._state = State(io=self._io)
        self._state.code = program.split()

    @property
    def halted(self) -> bool:
        return self._state.halted

    def step(self) -> None:
        self._state.step()

    @property
    def ip(self) -> int:
        return self._state.ptr

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._state.stk)


# Language name -> VM adapter.  Only interpreters with a step()/halted state
# object are wrappable; the rest raise UnknownLanguageError.
_VM_ADAPTERS: dict[str, type[_BaseVM]] = {
    "brainfuck": _BrainfuckVM,
    "S*bleq": _SbleqVM,
    "Dimensional": _DimensionalVM,
    "Grapheme": _GraphemeVM,
    "Qoibl": _QoiblVM,
    "Eval": _EvalVM,
    "Modulous": _ModulousVM,
    "The Temporary Stack": _TemporaryStackVM,
}


def make_vm(language: str, program: str, stdin: str = "") -> VM:
    """Return a step-and-inspect wrapper around ``language``'s interpreter.

    The wrapper exposes ``step()``, ``halted``, ``output``, ``ip``,
    ``memory``, and ``stack`` between commands.  ``stdin`` is fed to the
    program line by line, like :func:`esolangs.run`.  A language whose
    interpreter does not expose a step-capable state object raises
    :class:`UnknownLanguageError`.
    """
    if language not in RUNNERS:
        raise UnknownLanguageError(language)
    try:
        adapter = _VM_ADAPTERS[language]
    except KeyError:
        raise UnknownLanguageError(language) from None
    return adapter(program, stdin)
