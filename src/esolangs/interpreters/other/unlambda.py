r"""Interpreter for Unlambda.

David Madore's 1999 pure applicative language: no variables, no lambda, only
application.  A backtick applies the term after it to the one after that.
``k``, ``s``, ``i`` and ``v`` are the usual combinators (``v`` swallows every
argument), ``c`` is call/cc, ``d`` delays its operand instead of evaluating
it, ``.x`` prints ``x`` and returns its argument, ``r`` prints a newline,
``@`` reads, ``?x`` asks whether the character just read is ``x``, ``|``
hands the reader the character it has, ``e`` ends the run, and ``#`` starts
a comment.

The delay is dynamic, as the spec has it: evaluating an application whose
*function part evaluates to* ``d`` leaves the argument as a promise, and
forcing the promise evaluates it then applies the result.  So the evaluator
here is an explicit continuation machine rather than a recursive walk --
``c`` needs the continuation as a value, and one step of the machine is one
step of the language.

An empty source, a source with a second expression after the first, a
backtick with nothing after it, a ``.`` or ``?`` at the end, and any
character that is not a command raise :class:`ValueError`.  Every value is
applicable, so nothing at run time is invalid and no
:class:`~esolangs.exceptions.HaltError` arises.

``@`` consumes the next Unicode character, including newlines. The spec
does not define character encoding. Both input branches are live.  At end of
input ``@`` hands its argument ``v``, which the
shell reaches by catching the ``EOFError`` the port raises, as nine other
interpreters here catch it and carry on with their language's value; letting
it escape would make ``@``'s failure branch unreachable and every
read-until-EOF program a crash.  The current character is then left as it
was, since a read that found nothing replaced nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO


@dataclass(frozen=True)
class _Cmd:
    """A one-character command, as a term and as the value it evaluates to."""

    name: str


@dataclass(frozen=True)
class _Print:
    """``.x``, and what ``|`` hands over: printing is applying it."""

    char: str


@dataclass(frozen=True)
class _Query:
    """``?x``, which applies its argument to ``k`` or to ``v``."""

    char: str


@dataclass(frozen=True)
class _Partial:
    """A combinator that has some of its arguments: ``k1``, ``s1``, ``s2``."""

    name: str
    args: tuple[_Value, ...]


@dataclass(frozen=True)
class _Promise:
    """What ``d`` made: a term held unevaluated until something applies it."""

    term: _Term


@dataclass(frozen=True)
class _Cont:
    """A continuation ``c`` captured; applying it abandons the current one."""

    kont: tuple[_Frame, ...]


@dataclass(frozen=True)
class _App:
    """An application, the language's one syntactic form."""

    f: _Term
    a: _Term


@dataclass(frozen=True)
class _Val:
    """A value standing in for a term, so ``s`` can re-apply what it holds."""

    value: _Value


@dataclass(frozen=True)
class _Arg:
    """Waiting for the function's value, holding the argument's term."""

    term: _Term


@dataclass(frozen=True)
class _Fun:
    """Holding the function's value while the argument is evaluated."""

    value: _Value


@dataclass(frozen=True)
class _Eval:
    """Evaluate a term."""

    term: _Term


@dataclass(frozen=True)
class _Apply:
    """Apply one value to another."""

    f: _Value
    a: _Value


@dataclass(frozen=True)
class _Ret:
    """Hand a finished value back to the continuation."""

    value: _Value


#: A parsed term.
type _Term = _App | _Val | _Cmd | _Print | _Query
#: A value: a command, a partial application, a promise, a continuation.
type _Value = _Cmd | _Print | _Query | _Partial | _Promise | _Cont
#: One continuation frame.
type _Frame = _Arg | _Fun
#: What the machine is doing next.
type _Task = _Eval | _Apply | _Ret
#: ``(task, continuation, current character, finished)``.  The flag is what
#: makes ``halted`` true: an empty continuation, or ``e``.
type _State = tuple[_Task, tuple[_Frame, ...], str | None, bool]

#: What ``@`` and ``?x`` hand their argument.  The spec's words: "applies its
#: argument to ``i`` if successful or to ``v`` if not".  ``i`` and *not* ``k``
#: -- with ``k`` the success value would swallow the argument after it, so
#: ``` ``?c f v `` would keep ``f`` instead of running it, and a program
#: written against the language would take the wrong branch.
_SUCCESS = _Cmd("i")
_FAILURE = _Cmd("v")
_COMMANDS: dict[str, _Term] = {
    name: _Cmd(name) for name in ("k", "s", "i", "v", "c", "d", "e", "@", "|")
}
_COMMANDS["r"] = _Print("\n")


def _tokens(code: str) -> list[_Term | None]:
    """Return the source as terms, with ``None`` standing for a backtick."""
    out: list[_Term | None] = []
    index = 0
    while index < len(code):
        char = code[index]
        index += 1
        if char.isspace():
            continue
        if char == "#":
            found = code.find("\n", index)
            index = len(code) if found < 0 else found + 1
            continue
        if char == "`":
            out.append(None)
            continue
        if char in ".?":
            if index >= len(code):
                raise ValueError(f"Unlambda {char!r} has no character after it")
            out.append(_Print(code[index]) if char == "." else _Query(code[index]))
            index += 1
            continue
        if char in _COMMANDS:
            out.append(_COMMANDS[char])
            continue
        raise ValueError(f"{char!r} is not an Unlambda command")
    return out


def _parse(code: str) -> _Term:
    """Return the one term ``code`` spells.

    Iterative, so a long application chain cannot exhaust the recursion
    limit: each backtick opens a slot that the next two terms fill.
    """
    pending: list[list[_Term]] = []
    whole: _Term | None = None
    for token in _tokens(code):
        if token is None:
            pending.append([])
            continue
        term = token
        while True:
            if not pending:
                if whole is not None:
                    raise ValueError(
                        "an Unlambda program is one expression, and this "
                        "source spells a second one after the first"
                    )
                whole = term
                break
            slot = pending[-1]
            slot.append(term)
            if len(slot) < 2:
                break
            pending.pop()
            term = _App(slot[0], slot[1])
    if pending:
        raise ValueError("an Unlambda backtick is missing one of its two terms")
    if whole is None:
        raise ValueError("an Unlambda program cannot be empty")
    return whole


def _combinator(
    value: _Cmd | _Partial,
    argument: _Value,
    kont: tuple[_Frame, ...],
    char: str | None,
    *,
    read_ok: bool = True,
) -> _State:
    """Return the state after applying a combinator or a partial one.

    ``read_ok`` is whether ``@``'s read found a line; it is the spec's
    success flag and decides which of ``k`` and ``v`` ``@`` hands over.
    """
    name = value.name
    held = value.args if isinstance(value, _Partial) else ()
    if name == "i":
        return (_Ret(argument), kont, char, False)
    if name == "v":
        return (_Ret(_FAILURE), kont, char, False)
    if name == "c":
        return (_Apply(argument, _Cont(kont)), kont, char, False)
    if name in ("k", "s"):
        return (_Ret(_Partial(f"{name}1", (argument,))), kont, char, False)
    if name == "k1":
        return (_Ret(held[0]), kont, char, False)
    if name == "s1":
        return (_Ret(_Partial("s2", (*held, argument))), kont, char, False)
    if name == "s2":
        left = _App(_Val(held[0]), _Val(argument))
        right = _App(_Val(held[1]), _Val(argument))
        return (_Eval(_App(left, right)), kont, char, False)
    if name == "d":
        # ``d`` reached here already applied to an evaluated argument, which
        # only the combinators can arrange; the promise is of that value.
        return (_Ret(_Promise(_Val(argument))), kont, char, False)
    if name == "@":
        # The read happened in the shell.  Both of the spec's branches are
        # live: ``k`` when a line arrived, ``v`` at end of input.
        return (_Apply(argument, _SUCCESS if read_ok else _FAILURE), kont, char, False)
    if name == "|":
        held_char = _Print(char) if char is not None else _FAILURE
        return (_Apply(argument, held_char), kont, char, False)
    # ``e``: the run ends, and the argument is its result.
    return (_Ret(argument), (), char, True)


def _apply(
    value: _Value,
    argument: _Value,
    kont: tuple[_Frame, ...],
    char: str | None,
    *,
    read_ok: bool = True,
) -> tuple[_State, str | None]:
    """Return the state after applying ``value`` to ``argument``, and any print.

    Pure.  ``char`` is the character ``@`` has already read, and ``read_ok``
    whether it found one.
    """
    if isinstance(value, _Print):
        return (_Ret(argument), kont, char, False), value.char
    if isinstance(value, _Query):
        answer = _SUCCESS if char == value.char else _FAILURE
        return (_Apply(argument, answer), kont, char, False), None
    if isinstance(value, _Promise):
        return (_Eval(_App(value.term, _Val(argument))), kont, char, False), None
    if isinstance(value, _Cont):
        # Abandon the continuation this application sits in for the captured
        # one: that is the whole of what an Unlambda continuation does.
        return (_Ret(argument), value.kont, char, False), None
    return _combinator(value, argument, kont, char, read_ok=read_ok), None


def _advance(
    state: _State, line: str | None = None, *, at_eof: bool = False
) -> tuple[_State, str | None]:
    """Return the state after one machine step, and the text to print.

    Pure: ``@``'s line arrives as ``line``, ``at_eof`` says the read found
    nothing, and a print leaves as the return value.
    """
    task, kont, char, done = state
    if done:
        return state, None
    if isinstance(task, _Eval):
        term = task.term
        if isinstance(term, _App):
            return (_Eval(term.f), (*kont, _Arg(term.a)), char, False), None
        if isinstance(term, _Val):
            return (_Ret(term.value), kont, char, False), None
        return (_Ret(term), kont, char, False), None
    if isinstance(task, _Apply):
        if task.f == _Cmd("@") and not at_eof:
            char = line[0] if line else "\n"
        # At end of input the current character is left as it was: the read
        # found nothing, so it replaced nothing, and ``|`` still reports the
        # last character taken.
        return _apply(task.f, task.a, kont, char, read_ok=not at_eof)
    if not kont:
        return (task, kont, char, True), None
    frame, rest = kont[-1], kont[:-1]
    if isinstance(frame, _Arg):
        if task.value == _Cmd("d"):
            # The delay: the argument is not evaluated at all.
            return (_Ret(_Promise(frame.term)), rest, char, False), None
        return (_Eval(frame.term), (*rest, _Fun(task.value)), char, False), None
    return (_Apply(frame.value, task.value), rest, char, False), None


class _Machine:
    """The run state: one task, the continuation, and the character read."""

    #: ``@`` hands its argument ``v`` at end of input, so an underfed program
    #: takes its failure branch rather than failing.  Declared because the
    #: public API reports it.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.state: _State = (_Eval(_parse(code)), (), None, False)

    @property
    def halted(self) -> bool:
        return self.state[3]

    #: A position in the source would have to be a position in a term tree
    #: that ``s`` rebuilds as it runs, so there is none to report: the pair
    #: is the continuation's depth and which task it is running.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        task, kont, _char, _done = self.state
        kinds = (_Eval, _Apply, _Ret)
        return (len(kont), kinds.index(type(task)))

    @property
    def memory(self) -> list[int]:
        """No addressable cells; Unlambda has no store at all."""
        return []

    @property
    def stack(self) -> list[object]:
        """The continuation, outermost frame first: what waits on a value."""
        return list(self.state[1])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.position())

    def step(self) -> None:
        """Take one machine step, reading or printing where it asks."""
        if self.halted:
            return
        task = self.state[0]
        reading = isinstance(task, _Apply) and task.f == _Cmd("@")
        line: str | None = None
        at_eof = False
        if reading:
            try:
                line = chr(self.io.input_char())
            except EOFError:
                # The spec's end-of-input branch: ``@`` hands its argument
                # ``v`` rather than ``k``.  Nine interpreters here already
                # catch this raise and carry on with the value their language
                # defines; letting it escape instead would make the branch
                # unreachable and break every read-until-EOF program.
                at_eof = True
        self.state, out = _advance(self.state, line, at_eof=at_eof)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run an Unlambda program."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
