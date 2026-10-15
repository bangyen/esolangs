"""Interpreter for Quassaunt.

Every value is a string or a set of strings and sets, on one stack in
reverse Polish notation.  A word is ``@@text`` (push the string) or a
``%%`` command; whitespace separates words, but code run by
``%%Evaluate`` and the two ``%%If`` commands is split on ``?`` instead.
Variables hold sets: a name in square brackets is global, any other is
local to the evaluation that stores it.  ``%%Ifpropersubset`` and
``%%Ifdisjoint`` are the only branches; recursion through stored code is
the only loop.  The wiki's Hello world examples and Truth-machine run as
stated.

Input/output:
    ``%%Inputchar`` reads one character and raises at EOF.

Errors:
    ProgramError: A word that is neither ``@@`` nor a command, including
        ``%%Multithread`` (an extension the wiki lists apart, not
        implemented) and any ``%%^^`` command.
    InputExhaustedError: ``%%Inputchar`` at EOF.
    HaltError: Missing operands; a value of the wrong type; ``%%Head`` or
        ``%%Tail`` of an empty string; obtaining or deleting an unset
        variable; storing or deleting ``@@[Whitespace]``; a set inside
        ``%%Concatenateall``; ``@@##Argv`` or another reserved ``##``/``^^``
        name; a bad word in code ``%%Evaluate`` or an ``%%If`` runs.

Decisions:
    * ``%%Concatenateall`` joins its strings in code-point order (the wiki
      makes the order the implementation's) and refuses a set, the wiki
      saying sets "should not be included".
    * Each ``%%Evaluate`` and each branch an ``%%If`` takes is a new call
      stack entry with no locals; ``%%Evaluatereplace`` drops the top
      entry's locals and remaining code.  An entry with no code left is
      replaced, not kept, by the call that ends it: its locals are
      unreachable.
    * ``@@##Argv`` is not supported; ``@@##Argvsupport`` obtains ``{N}`` as
      specified.  The ``%%Store``/``%%Delete`` messages are the wiki's code
      run literally, so they keep its leading ``@@``.
    * Empty words (``a??b``, a trailing ``?``) are skipped.
    * The halting cases above get no result from the wiki.
"""

from __future__ import annotations

import re
from typing import TypeGuard

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

_COMMANDS = frozenset(
    [
        "Empty",
        "Store",
        "Obtain",
        "Concatenate",
        "Makecontain",
        "Makenotcontain",
        "Concatenateall",
        "Evaluate",
        "Evaluatepermanently",
        "Evaluatereplace",
        "Ifpropersubset",
        "Ifdisjoint",
        "Printtoconsole",
        "Inputchar",
        "Delete",
        "Head",
        "Tail",
        "Swap",
    ]
)
_WHITESPACE = " \t\n\r"
_ERROR = "##Errormessage"
_DUPLICATE = frozenset({"No_duplicates_are_allowed_in_a_set."})
_ABSENT = frozenset({"The_set_does_not_contain_the_value_entered."})

type _Value = str | frozenset[object]
#: The value stack as a linked list, top first.
type _Stack = tuple[_Value, _Stack] | None
#: ``(words, pc, depth)``: one call stack entry; its locals live at ``depth``.
type _Frame = tuple[tuple[str, ...], int, int]
type _Frames = tuple[_Frame, _Frames] | None
type _State = tuple[_Stack, _Frames]
#: ``("set", scope, name, value)``, ``("del", scope, name)`` or
#: ``("clear", depth)``; ``scope`` is ``"g"`` or a depth.
type _Effect = tuple[object, ...]


def _words(code: str, separator: str, error: type[Exception]) -> tuple[str, ...]:
    words = tuple(w for w in re.split(separator, code) if w)
    for word in words:
        if not word.startswith("@@") and (
            not word.startswith("%%") or word[2:] not in _COMMANDS
        ):
            hint = " (an extension, not implemented)" if word == "%%Multithread" else ""
            raise error(f"Quassaunt has no word {word!r}{hint}")
    return words


def _scope(name: str, depth: int) -> str | int:
    """Return where ``name`` lives: ``"g"`` for globals, else the frame's depth."""
    if name.startswith(("##", "^^")) or (
        len(name) >= 2 and name[0] == "[" and name[-1] == "]"
    ):
        return "g"
    return depth


def _is_set(value: object) -> TypeGuard[frozenset[object]]:
    return isinstance(value, frozenset)


class _Run:
    """One word's work: pops and pushes on the stack, effects, output."""

    def __init__(self, stack: _Stack, depth: int) -> None:
        self.stack = stack
        self.depth = depth
        self.effects: list[_Effect] = []
        self.output: str | None = None

    def pop(self, kind: str, command: str) -> _Value:
        if self.stack is None:
            raise HaltError(f"Quassaunt %%{command} needs more values on the stack")
        value, self.stack = self.stack
        if kind == "str" and not isinstance(value, str):
            raise HaltError(f"Quassaunt %%{command} needs a string, got a set")
        if kind == "set" and not _is_set(value):
            raise HaltError(f"Quassaunt %%{command} needs a set, got {value!r}")
        return value

    def push(self, value: _Value) -> None:
        self.stack = (value, self.stack)

    def error(self, message: frozenset[object]) -> None:
        self.effects.append(("set", "g", _ERROR, message))


def _variable(run: _Run, command: str, name: str, got: _Value | None) -> None:
    """Store, obtain or delete ``name``; ``got`` is its value, or the one stored."""
    if name == "[Whitespace]":
        if command != "Obtain":
            raise HaltError(f"Quassaunt cannot {command.lower()} @@[Whitespace]")
        run.push(_WHITESPACE)
        return
    if name == "##Argvsupport":
        if command == "Obtain":
            run.push(frozenset({"N"}))
        else:
            run.error(frozenset({f"@@##Argvsupport_does_not_support_%%{command}."}))
        return
    if name.startswith(("##", "^^")) and name != _ERROR:
        raise HaltError(f"Quassaunt does not support the reserved variable {name!r}")
    scope = _scope(name, run.depth)
    if command == "Store":
        run.effects.append(("set", scope, name, got))
    elif name == _ERROR and command == "Delete":
        run.effects.append(("set", "g", name, frozenset()))
    elif got is None:
        raise HaltError(f"Quassaunt %%{command} found no variable {name!r}")
    elif command == "Obtain":
        run.push(got)
    else:
        run.effects.append(("del", scope, name))


def _set_op(run: _Run, command: str) -> None:
    if command == "Makecontain":
        target = run.pop("set", command)
        value = run.pop("any", command)
        assert _is_set(target)
        if value in target:
            run.error(_DUPLICATE)
            run.push(frozenset())
        else:
            run.push(target | {value})
    else:
        value = run.pop("any", command)
        target = run.pop("set", command)
        assert _is_set(target)
        if value not in target:
            run.error(_ABSENT)
            run.push(frozenset())
        else:
            run.push(target - {value})


def _string_op(run: _Run, command: str, got: _Value | None) -> None:
    if command == "Concatenate":
        top = run.pop("str", command)
        run.push(f"{run.pop('str', command)}{top}")
    elif command == "Concatenateall":
        run.pop("any", command)
        members = run.pop("set", command)
        run.pop("any", command)
        separator = run.pop("str", command)
        assert _is_set(members)
        assert isinstance(separator, str)
        if not all(isinstance(m, str) for m in members):
            raise HaltError("Quassaunt %%Concatenateall met a set inside its set")
        run.push(separator.join(sorted(members)))  # type: ignore[arg-type]
    elif command == "Printtoconsole":
        run.output = str(run.pop("str", command))
    elif command == "Inputchar":
        assert isinstance(got, str)
        run.push(got)
    else:  # Head, Tail
        text = str(run.pop("str", command))
        if not text:
            raise HaltError(f"Quassaunt %%{command} of an empty string")
        run.push(text[0] if command == "Head" else text[1:])


def _branch(run: _Run, command: str) -> str:
    """Pop an ``%%If``'s four operands; return the string it evaluates."""
    top_set = run.pop("set", command)
    top = run.pop("str", command)
    bottom_set = run.pop("set", command)
    bottom = run.pop("str", command)
    assert _is_set(top_set)
    assert _is_set(bottom_set)
    if command == "Ifpropersubset":
        taken = top_set < bottom_set
    else:
        taken = top_set.isdisjoint(bottom_set)
    return str(bottom if taken else top)


def _advance(
    state: _State, got: _Value | None = None
) -> tuple[_State, tuple[_Effect, ...], str | None]:
    """Run one word: the new state, the variable effects, any output.

    Pure: ``%%Inputchar``'s character, or the variable ``%%Obtain`` and
    ``%%Delete`` name, arrives as ``got``.
    """
    stack, frames = state
    assert frames is not None
    (words, pc, depth), rest = frames
    word = words[pc]
    run = _Run(stack, depth)
    frames = ((words, pc + 1, depth), rest)
    command = word[2:]
    called: str | None = None
    if word.startswith("@@"):
        run.push(word[2:])
    elif command == "Empty":
        run.push(frozenset())
    elif command in ("Store", "Obtain", "Delete"):
        if command == "Store":
            got = run.pop("set", command)
        _variable(run, command, str(run.pop("str", command)), got)
    elif command in ("Makecontain", "Makenotcontain"):
        _set_op(run, command)
    elif command == "Swap":
        top, below = run.pop("any", command), run.pop("any", command)
        run.push(top)
        run.push(below)
    elif command in ("Ifpropersubset", "Ifdisjoint"):
        called = _branch(run, command)
    elif command.startswith("Evaluate"):
        called = str(run.pop("str", command))
    else:
        _string_op(run, command, got)
    effects = run.effects
    if called is not None:
        body = _words(called, r"\?", HaltError)
        if command == "Evaluatepermanently":
            effects.append(("clear", 0))
            frames, depth = None, 0
        elif command == "Evaluatereplace" or pc + 1 == len(words):
            # Replacing a finished caller is unobservable: its locals are dead.
            effects.append(("clear", depth))
            frames, depth = rest, depth - 1
        frames = ((body, 0, depth + 1), frames)
    while frames is not None and frames[0][1] >= len(frames[0][0]):
        effects.append(("clear", frames[0][2]))
        frames = frames[1]
    return (run.stack, frames), tuple(effects), run.output


class _Machine:
    """The shell around :func:`_advance`: variables, input and output."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        words = _words(code, r"[ \t\n\r]+", ValueError)
        self.state: _State = (None, ((words, 0, 1), None) if words else None)
        self.globals: dict[str, frozenset[object]] = {_ERROR: frozenset()}
        #: ``locals[d]`` belongs to the call stack entry at depth ``d``.
        self.locals: dict[int, dict[str, frozenset[object]]] = {}

    @property
    def halted(self) -> bool:
        return self.state[1] is None

    @property
    def ip(self) -> tuple[int, ...]:
        """Each call stack entry's word index, outermost first."""
        pcs: list[int] = []
        frames = self.state[1]
        while frames is not None:
            pcs.append(frames[0][1])
            frames = frames[1]
        return tuple(pcs[::-1])

    @property
    def stack(self) -> list[object]:
        """The value stack, bottom first."""
        values: list[object] = []
        node = self.state[0]
        while node is not None:
            values.append(node[0])
            node = node[1]
        return values[::-1]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        scopes = tuple(
            (depth, frozenset(names.items()))
            for depth, names in sorted(self.locals.items())
            if names
        )
        return (
            *self.state,
            frozenset(self.globals.items()),
            scopes,
            self.io.progress(),
        )

    def _lookup(self, name: str, depth: int) -> frozenset[object] | None:
        scope = _scope(name, depth)
        if scope == "g":
            return self.globals.get(name)
        return self.locals.get(depth, {}).get(name)

    def step(self) -> None:
        """Run one word, fetching what it reads first."""
        stack, frames = self.state
        if frames is None:
            return
        words, pc, depth = frames[0]
        word = words[pc]
        got: _Value | None = None
        if word == "%%Inputchar":
            got = chr(self.io.input_char())
        elif (
            word in ("%%Obtain", "%%Delete")
            and stack is not None
            and isinstance(stack[0], str)
        ):
            got = self._lookup(stack[0], depth)
        self.state, effects, out = _advance(self.state, got)
        for effect in effects:
            if effect[0] == "clear":
                depth_cleared = effect[1]
                assert isinstance(depth_cleared, int)
                for d in [d for d in self.locals if d >= max(depth_cleared, 1)]:
                    del self.locals[d]
            else:
                scope, name = effect[1], effect[2]
                assert isinstance(name, str)
                names = (
                    self.globals if scope == "g" else self.locals.setdefault(scope, {})  # type: ignore[arg-type]
                )
                if effect[0] == "set":
                    names[name] = effect[3]  # type: ignore[assignment]
                else:
                    del names[name]
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a Quassaunt program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
