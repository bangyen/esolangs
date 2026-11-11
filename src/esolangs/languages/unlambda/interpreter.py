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
step of the language.  Every value is applicable, so nothing at run time is
invalid and no HaltError arises.

Input/output:
    ``@`` consumes the next Unicode character, including newlines.  At EOF
    it hands its argument ``v`` and clears the current character.

Errors:
    ProgramError: an empty source; a second expression after the first; a
        backtick with nothing after it; a ``.`` or ``?`` at the end; any
        character that is not a command.

Decisions:
    * The spec does not define character encoding.
    * Both input branches are live: at EOF ``@`` hands its argument ``v``,
      which the shell reaches by catching the port's ``EOFError`` (as other
      interpreters here do); letting it escape would make ``@``'s failure
      branch unreachable and every read-until-EOF program a crash.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable, Mapping
from dataclasses import dataclass, fields
from typing import Any, cast

from esolangs.languages.unlambda.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._snapshot import SnapshotCodec
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


class _ValueBase:
    """Hash persistent values once and compare their full contents iteratively."""

    __slots__ = ("_hash",)

    _hash: int

    def _store_hash(self) -> None:
        object.__setattr__(
            self,
            "_hash",
            hash(
                (
                    "_Kont" if isinstance(self, _Kont) else type(self).__name__,
                    _value_parts(self),
                )
            ),
        )

    def __hash__(self) -> int:
        try:
            return self._hash
        except AttributeError:
            self._cache_value_hash()
            return self._hash

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _ValueBase):
            return NotImplemented
        if type(self) is not type(other) and not (
            isinstance(self, _Kont) and isinstance(other, _Kont)
        ):
            return False
        if hash(self) != hash(other):
            return False
        return _same_value(self, other)

    def _cache_value_hash(self) -> None:
        """Rebuild missing derived hashes bottom-up after pickle or deepcopy."""
        pending: list[tuple[object, bool]] = [(self, False)]
        while pending:
            node, ready = pending.pop()
            if isinstance(node, tuple):
                pending.extend((part, False) for part in node)
                continue
            if not isinstance(node, _ValueBase) or hasattr(node, "_hash"):
                continue
            if ready:
                _ValueBase._store_hash(node)
            else:
                pending.append((node, True))
                pending.extend((part, False) for part in _value_parts(node))


def _value_parts(value: _ValueBase) -> tuple[object, ...]:
    if isinstance(value, _Kont):
        return value.frame, value.rest
    return tuple(getattr(value, field.name) for field in fields(cast("Any", value)))


def _same_value(left: object, right: object) -> bool:
    pending = [(left, right)]
    seen = set()
    while pending:
        left, right = pending.pop()
        if left is right:
            continue
        if type(left) is not type(right) and not (
            isinstance(left, _Kont) and isinstance(right, _Kont)
        ):
            return False
        pair = id(left), id(right)
        if pair in seen:
            continue
        seen.add(pair)
        if isinstance(left, _ValueBase):
            node = cast("_ValueBase", right)
            if isinstance(left, _Kont) and left.depth != cast("_Kont", node).depth:
                return False
            pending.extend(zip(_value_parts(left), _value_parts(node), strict=True))
        elif isinstance(left, tuple):
            items = cast("tuple[object, ...]", right)
            if len(left) != len(items):
                return False
            pending.extend(zip(left, items, strict=True))
        elif left != right:
            return False
    return True


@dataclass(frozen=True, slots=True)
class _Cmd:
    """A one-character command, as a term and as the value it evaluates to."""

    name: str


@dataclass(frozen=True, slots=True)
class _Print:
    """``.x``, and what ``|`` hands over: printing is applying it."""

    char: str


@dataclass(frozen=True, slots=True)
class _Query:
    """``?x``, which applies its argument to ``i`` or to ``v``."""

    char: str


@dataclass(frozen=True, slots=True, eq=False)
class _Partial(_ValueBase):
    """A combinator that has some of its arguments: ``k1``, ``s1``, ``s2``."""

    name: str
    args: tuple[_Value, ...]


@dataclass(frozen=True, slots=True, eq=False)
class _Promise(_ValueBase):
    """What ``d`` made: a term held unevaluated until something applies it."""

    term: _Term


class _Kont(_ValueBase):
    """A non-empty continuation: its innermost frame, and the rest.

    Linked rather than a tuple, so a push, a pop and ``c``'s capture are each
    O(1): rebuilding a tuple every step made ``` ``*N i*(N+1)`` quadratic
    (1.8 s at N=16k).  Equal when the frames are, as a tuple would be.
    """

    __slots__ = ("depth", "frame", "rest")

    def __init__(self, frame: _Frame, rest: _Kont | None) -> None:
        self.frame = frame
        self.rest = rest
        self.depth: int = 1 + (rest.depth if rest is not None else 0)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _Kont):
            return NotImplemented
        return super().__eq__(other)

    __hash__ = _ValueBase.__hash__

    def __getstate__(self) -> tuple[_Frame, _Kont | None]:
        """Omit the derived depth and process-specific hash."""
        return self.frame, self.rest

    def __setstate__(self, state: tuple[_Frame, _Kont | None]) -> None:
        """Restore a continuation without retaining a cached hash."""
        frame, rest = state
        if rest is not None and not isinstance(rest, _Kont):
            raise TypeError("invalid continuation state")
        self.frame, self.rest = frame, rest
        self.depth = 1 + (rest.depth if rest is not None else 0)
        if hasattr(self, "_hash"):
            object.__delattr__(self, "_hash")

    def frames(self) -> tuple[_Frame, ...]:
        """Return the frames, outermost first."""
        out: list[_Frame] = []
        node: _Kont | None = self
        while node is not None:
            out.append(node.frame)
            node = node.rest
        return tuple(reversed(out))


@dataclass(frozen=True, slots=True, eq=False)
class _Cont(_ValueBase):
    """A continuation ``c`` captured; applying it abandons the current one."""

    kont: _Kont | None


@dataclass(frozen=True, slots=True, eq=False)
class _App(_ValueBase):
    """An application, the language's one syntactic form."""

    f: _Term
    a: _Term


@dataclass(frozen=True, slots=True, eq=False)
class _Val(_ValueBase):
    """A value standing in for a term, so ``s`` can re-apply what it holds."""

    value: _Value


@dataclass(frozen=True, slots=True, eq=False)
class _Arg(_ValueBase):
    """Waiting for the function's value, holding the argument's term."""

    term: _Term


@dataclass(frozen=True, slots=True, eq=False)
class _Fun(_ValueBase):
    """Holding the function's value while the argument is evaluated."""

    value: _Value


@dataclass(frozen=True, slots=True, eq=False)
class _Eval(_ValueBase):
    """Evaluate a term."""

    term: _Term


@dataclass(frozen=True, slots=True, eq=False)
class _Apply(_ValueBase):
    """Apply one value to another."""

    f: _Value
    a: _Value


@dataclass(frozen=True, slots=True, eq=False)
class _Ret(_ValueBase):
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
#: ``(task, continuation, current character, finished)``, ``None`` the empty
#: continuation.  The flag is what makes ``halted`` true: an empty
#: continuation, or ``e``.
type _State = tuple[_Task, _Kont | None, str | None, bool]

#: What ``@`` and ``?x`` hand their argument.  The spec's words: "applies its
#: argument to ``i`` if successful or to ``v`` if not".  ``i`` and *not* ``k``
#: -- with ``k`` the success value would swallow the argument after it, so
#: ``` ``?c f v `` would keep ``f`` instead of running it, and a program
#: written against the language would take the wrong branch.
_SUCCESS = _Cmd("i")
_READ = _Cmd("@")
_DELAY = _Cmd("d")
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
                raise syntax_error(
                    f"Unlambda {char!r} has no character after it",
                    "follow . or ? with its literal character, for example .A",
                )
            out.append(_Print(code[index]) if char == "." else _Query(code[index]))
            index += 1
            continue
        if char in _COMMANDS:
            out.append(_COMMANDS[char])
            continue
        raise syntax_error(
            f"{char!r} is not an Unlambda command",
            ("use Unlambda combinators or ` for application; # starts a comment"),
        )
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
                    raise syntax_error(
                        "an Unlambda program is one expression, and this "
                        "source spells a second one after the first",
                        (
                            "combine the expressions using prefix ` application, or "
                            "keep a single expression"
                        ),
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
        raise syntax_error(
            "an Unlambda backtick is missing one of its two terms",
            "give each ` exactly two expressions, for example `ii",
        )
    if whole is None:
        raise syntax_error(
            "an Unlambda program cannot be empty",
            "provide one expression; i is the identity combinator",
        )
    return whole


def _combinator(
    value: _Cmd | _Partial,
    argument: _Value,
    kont: _Kont | None,
    char: str | None,
    *,
    read_ok: bool = True,
) -> _State:
    """Return the state after applying a combinator or a partial one.

    ``read_ok`` is whether ``@``'s read found a line; it is the spec's
    success flag and decides which of ``i`` and ``v`` ``@`` hands over.
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
        # live: ``i`` when a character arrived, ``v`` at end of input.
        return (_Apply(argument, _SUCCESS if read_ok else _FAILURE), kont, char, False)
    if name == "|":
        held_char = _Print(char) if char is not None else _FAILURE
        return (_Apply(argument, held_char), kont, char, False)
    # ``e``: the run ends, and the argument is its result.
    return (_Ret(argument), None, char, True)


def _apply(
    value: _Value,
    argument: _Value,
    kont: _Kont | None,
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
    state: _State, read_char: str | None = None, *, at_eof: bool = False
) -> tuple[_State, str | None]:
    """Return the state after one machine step, and the text to print.

    Pure: ``@``'s character arrives as ``read_char``, ``at_eof`` says the read found
    nothing, and a print leaves as the return value.
    """
    task, kont, char, done = state
    if done:
        return state, None
    if isinstance(task, _Eval):
        term = task.term
        if isinstance(term, _App):
            return (_Eval(term.f), _Kont(_Arg(term.a), kont), char, False), None
        if isinstance(term, _Val):
            return (_Ret(term.value), kont, char, False), None
        return (_Ret(term), kont, char, False), None
    if isinstance(task, _Apply):
        if task.f == _READ:
            # The specification makes both ?x and | see no character at EOF.
            char = None if at_eof else read_char
        return _apply(task.f, task.a, kont, char, read_ok=not at_eof)
    if kont is None:
        return (task, kont, char, True), None
    frame, rest = kont.frame, kont.rest
    if isinstance(frame, _Arg):
        if task.value == _DELAY:
            # The delay: the argument is not evaluated at all.
            return (_Ret(_Promise(frame.term)), rest, char, False), None
        return (_Eval(frame.term), _Kont(_Fun(task.value), rest), char, False), None
    return (_Apply(frame.value, task.value), rest, char, False), None


_WORKSPACE_MODEL = WorkspaceModel(
    "unlambda-v1", ("task", "continuation", "character", "stopped", "input_cursor")
)


def _workspace_fields(value: object) -> tuple[str, tuple[object, ...]]:
    """Describe logical constructors without continuation depth caches."""
    match value:
        case _Cmd(name):
            return "Cmd", (name,)
        case _Print(char):
            return "Print", (char,)
        case _Query(char):
            return "Query", (char,)
        case _Partial(name, args):
            return "Partial", (name, args)
        case _Promise(term):
            return "Promise", (term,)
        case _Cont(kont):
            return "Cont", (kont,)
        case _App(function, argument):
            return "App", (function, argument)
        case _Val(item):
            return "Val", (item,)
        case _Arg(term):
            return "Arg", (term,)
        case _Fun(item):
            return "Fun", (item,)
        case _Eval(term):
            return "Evaluate", (term,)
        case _Apply(function, argument):
            return "Apply", (function, argument)
        case _Ret(item):
            return "Ret", (item,)
        case _Kont():
            return "Kont", value.frames()
        case tuple():
            return "tuple", value
        case _:
            raise TypeError("unsupported Unlambda workspace value")


def _workspace_value(
    value: object, cache: OrderedDict[int, tuple[object, Hashable]] | None = None
) -> Hashable:
    """Freeze a term DAG iteratively; captured continuations keep logical frames."""
    frozen: dict[int, Hashable] = {}
    pending = [(value, False)]
    while pending:
        node, ready = pending.pop()
        if id(node) in frozen:
            continue
        if node is None or isinstance(node, (str, bool)):
            frozen[id(node)] = node
            continue
        hit = cache.get(id(node)) if cache is not None else None
        if hit is not None and hit[0] is node:
            frozen[id(node)] = hit[1]
            assert cache is not None
            cache.move_to_end(id(node))
            continue
        kind, parts = _workspace_fields(node)
        if ready:
            frozen[id(node)] = WorkspaceVariant(
                kind, tuple(frozen[id(part)] for part in parts)
            )
            if cache is not None:
                cache[id(node)] = (node, frozen[id(node)])
                if len(cache) > 2048:
                    cache.popitem(last=False)
        else:
            pending.append((node, True))
            pending.extend((part, False) for part in parts)
    return frozen[id(value)]


class _Machine:
    """The run state: one task, the continuation, and the character read."""

    #: ``@`` hands its argument ``v`` at end of input, so an underfed program
    #: takes its failure branch rather than failing.  Declared because the
    #: public API reports it.
    eof_is_a_value = True

    def __init__(self, code: str | _Term, io: IO) -> None:
        self.io = io
        term = _parse(code) if isinstance(code, str) else code
        self.state: _State = (_Eval(term), None, None, False)
        # A 200-command counter rebuilt 17,743 views; cap reuse at 2,048 nodes.
        self._workspace_cache: OrderedDict[int, tuple[object, Hashable]] = OrderedDict()

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
        return (kont.depth if kont is not None else 0, kinds.index(type(task)))

    @property
    def stack(self) -> list[object]:
        """The continuation, outermost frame first: what waits on a value."""
        kont = self.state[1]
        return list(kont.frames()) if kont is not None else []

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical terms and continuations, excluding cached depths."""
        task, continuation, character, stopped = self.state
        return _WORKSPACE_MODEL.capture(
            task=_workspace_value(task, self._workspace_cache),
            continuation=_workspace_value(continuation, self._workspace_cache),
            character=character,
            stopped=stopped,
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Take one machine step, reading or printing where it asks."""
        if self.halted:
            return
        task = self.state[0]
        reading = isinstance(task, _Apply) and task.f == _READ
        read_char: str | None = None
        at_eof = False
        if reading:
            try:
                read_char = chr(self.io.input_char())
            except EOFError:
                # The spec's end-of-input branch: ``@`` hands its argument
                # ``v`` rather than ``i`` (see the module docstring).
                at_eof = True
        self.state, out = _advance(self.state, read_char, at_eof=at_eof)
        if out is not None:
            self.io.print_str(out)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse source once and build fresh state for each run."""
    if not isinstance(source, str):
        raise TypeError("Unlambda machines require text source")
    if options:
        raise TypeError("Unlambda machines accept no runtime options")
    image = _parse(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Term, io: IO) -> CompletionReport:
    """Run an Unlambda program."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run an Unlambda program."""
    _execute(code, io)


SNAPSHOT_RECORDS = (
    _Cmd,
    _Print,
    _Query,
    _Partial,
    _Promise,
    _Cont,
    _App,
    _Val,
    _Arg,
    _Fun,
    _Eval,
    _Apply,
    _Ret,
)


def _kont_payload(kont: _Kont) -> Hashable:
    return kont.frames()


def _kont_restore(payload: Hashable) -> _Kont:
    if (
        not isinstance(payload, tuple)
        or not payload
        or any(not isinstance(frame, (_Arg, _Fun)) for frame in payload)
    ):
        raise TypeError("invalid continuation snapshot")
    kont: _Kont | None = None
    for frame in payload:
        kont = _Kont(frame, kont)
    assert kont is not None
    return kont


SNAPSHOT_CODECS = (SnapshotCodec(_Kont, _kont_payload, _kont_restore),)


if __name__ == "__main__":
    script_main(run)
