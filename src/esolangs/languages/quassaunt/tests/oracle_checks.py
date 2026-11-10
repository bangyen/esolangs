"""Independent bounded Quassaunt values, frames, scopes and input model.

The wiki's named stack/set/evaluation rules; 64 word boundaries, including
failed steps and three stable post-halt captures. No production transitions.
"""

from copy import deepcopy

from esolangs.languages.quassaunt.interpreter import _Machine, prepare_machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import reject_faults
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "quassaunt-v1", "stack frames globals locals input_cursor"
)
_COMMANDS = frozenset(
    (
        "Empty",
        "Store",
        "Obtain",
        "Delete",
        "Makecontain",
        "Makenotcontain",
        "Swap",
        "Concatenate",
        "Concatenateall",
        "Printtoconsole",
        "Inputchar",
        "Head",
        "Tail",
        "Evaluate",
        "Evaluatereplace",
        "Evaluatepermanently",
        "Ifpropersubset",
        "Ifdisjoint",
    )
)


class _RefusalError(Exception):
    pass


def _words(source, *, nested=False):
    if not nested:
        source = source.translate(str.maketrans("\t\n\r", "   "))
    words = tuple(word for word in source.split("?" if nested else " ") if word)
    if any(
        not word.startswith("@@")
        and (not word.startswith("%%") or word[2:] not in _COMMANDS)
        for word in words
    ):
        raise _RefusalError("halt" if nested else "syntax")
    return words


def _global(name):
    return name.startswith(("##", "^^")) or (
        name.startswith("[") and name.endswith("]")
    )


class _Step:
    """One independent transactional word; failed words commit no core changes."""

    def __init__(self, stack, frames, globals_, locals_):
        self.stack, self.frames = stack.copy(), frames.copy()
        self.globals, self.locals = dict(globals_), deepcopy(locals_)
        self.words, self.pc, self.depth = frames[-1]
        self.frames[-1] = (self.words, self.pc + 1, self.depth)

    def pop(self, kind=None):
        if not self.stack:
            raise _RefusalError("halt")
        value = self.stack.pop()
        if kind is not None and not isinstance(value, kind):
            raise _RefusalError("halt")
        return value

    def clear(self, first):
        for level in list(self.locals):
            if level >= first:
                del self.locals[level]

    def variable(self, command):
        value = self.pop(frozenset) if command == "Store" else None
        name = self.pop(str)
        if name == "[Whitespace]":
            if command != "Obtain":
                raise _RefusalError("halt")
            self.stack.append(" \t\n\r")
        elif name == "##Argvsupport":
            if command == "Obtain":
                self.stack.append(frozenset({"N"}))
            else:
                self.globals["##Errormessage"] = frozenset(
                    {f"@@##Argvsupport_does_not_support_%%{command}."}
                )
        else:
            if name.startswith(("##", "^^")) and name != "##Errormessage":
                raise _RefusalError("halt")
            names = (
                self.globals
                if _global(name)
                else self.locals.setdefault(self.depth, {})
            )
            if command == "Store":
                names[name] = value
            elif name == "##Errormessage" and command == "Delete":
                names[name] = frozenset()
            elif name not in names:
                raise _RefusalError("halt")
            elif command == "Obtain":
                self.stack.append(names[name])
            else:
                del names[name]

    def set_operation(self, command):
        if command == "Makecontain":
            target, value = self.pop(frozenset), self.pop()
            duplicate = value in target
            result = target | {value}
            error = "No_duplicates_are_allowed_in_a_set."
        else:
            value, target = self.pop(), self.pop(frozenset)
            duplicate = value not in target
            result = target - {value}
            error = "The_set_does_not_contain_the_value_entered."
        if duplicate:
            self.globals["##Errormessage"] = frozenset({error})
        self.stack.append(frozenset() if duplicate else result)

    def string_operation(self, command):
        if command == "Concatenate":
            top = self.pop(str)
            self.stack.append(self.pop(str) + top)
        elif command == "Concatenateall":
            self.pop()
            members = self.pop(frozenset)
            self.pop()
            separator = self.pop(str)
            if any(not isinstance(value, str) for value in members):
                raise _RefusalError("halt")
            self.stack.append(separator.join(sorted(members)))
        elif command == "Printtoconsole":
            return self.pop(str)
        else:
            text = self.pop(str)
            if not text:
                raise _RefusalError("halt")
            self.stack.append(text[0] if command == "Head" else text[1:])
        return ""

    def branch(self, command):
        top_set, top = self.pop(frozenset), self.pop(str)
        bottom_set, bottom = self.pop(frozenset), self.pop(str)
        condition = (
            top_set < bottom_set
            if command == "Ifpropersubset"
            else top_set.isdisjoint(bottom_set)
        )
        return bottom if condition else top

    def execute(self, word):
        command = word[2:]
        if word.startswith("@@"):
            self.stack.append(command)
        elif command == "Empty":
            self.stack.append(frozenset())
        elif command in ("Store", "Obtain", "Delete"):
            self.variable(command)
        elif command in ("Makecontain", "Makenotcontain"):
            self.set_operation(command)
        elif command == "Swap":
            top, below = self.pop(), self.pop()
            self.stack.extend((top, below))
        elif command in (
            "Concatenate",
            "Concatenateall",
            "Printtoconsole",
            "Head",
            "Tail",
        ):
            return self.string_operation(command), None
        elif command in ("Ifpropersubset", "Ifdisjoint"):
            return "", self.branch(command)
        else:
            assert command in ("Evaluate", "Evaluatereplace", "Evaluatepermanently")
            return "", self.pop(str)
        return "", None

    def finish(self, called, command):
        if called is not None:
            body = _words(called, nested=True)
            if command == "Evaluatepermanently":
                self.frames.clear()
                self.clear(1)
            elif command == "Evaluatereplace" or self.pc + 1 == len(self.words):
                self.frames.pop()
                self.clear(self.depth)
            self.frames.append((body, 0, len(self.frames) + 1))
        while self.frames and self.frames[-1][1] == len(self.frames[-1][0]):
            self.clear(self.frames[-1][2])
            self.frames.pop()


def _model(source, stdin, cap=64):
    try:
        words = _words(source)
    except _RefusalError:
        return "syntax", [(None, False, "", 0, 0)]
    stack, frames = [], [(words, 0, 1)] if words else []
    globals_, locals_ = {"##Errormessage": frozenset()}, {}
    cursor = reads = past_end = 0
    output, trace = "", []

    def row():
        state = (
            tuple(reversed(stack)),
            tuple(reversed(frames)),
            frozenset(globals_.items()),
            frozenset(
                (depth, frozenset(values.items()))
                for depth, values in locals_.items()
                if values
            ),
            reads,
            past_end,
        )
        return state, not frames, output, cursor, cursor

    for tick in range(cap + 1):
        trace.append(row())
        if not frames:
            return None, trace + [row()] * 3
        if tick == cap:
            break
        step = _Step(stack, frames, globals_, locals_)
        word = step.words[step.pc]
        emitted, called = "", None
        try:
            if word == "%%Inputchar":
                if cursor == len(stdin):
                    past_end += 1
                    raise _RefusalError("input")
                step.stack.append(stdin[cursor])
                cursor += 1
                reads += 1
            else:
                emitted, called = step.execute(word)
            step.finish(called, word[2:])
        except _RefusalError as error:
            return str(error), [*trace, row()]
        stack, frames, globals_, locals_ = (
            step.stack,
            step.frames,
            step.globals,
            step.locals,
        )
        output += emitted
    return None, trace


def _view(machine):
    frames, pending = [], machine.state[1]
    while pending is not None:
        frame, pending = pending
        frames.append(frame)
    return (
        tuple(reversed(machine.stack)),
        tuple(frames),
        frozenset(machine.globals.items()),
        frozenset(
            (depth, frozenset(values.items()))
            for depth, values in machine.locals.items()
            if values
        ),
        machine.io.reads,
        machine.io.past_end,
    )


def _check(factory, source, stdin="unused", *, cap=64):
    return workspace.agrees(
        _model(source, stdin, cap),
        (factory, source, stdin),
        (_WORKSPACE, lambda row: (*row[0][:4], row[-1])),
        _view,
        cap=cap,
        context=(source, stdin),
    )


def check_raw_quassaunt():
    populated = (
        "@@[g] @@a %%Empty %%Makecontain %%Store @@v %%Inputchar"
        " %%Empty %%Makecontain %%Store @@v %%Obtain"
    )
    expected = _check(_Machine, populated, "λ")
    start = (*expected[1][0][0][:4], expected[1][0][-1])
    for index in range(5):
        assert any((*row[0][:4], row[-1])[index] != start[index] for row in expected[1])
    for source, stdin in (
        ("", ""),
        ("bogus", ""),
        ("%%Inputchar", ""),
        ("%%Inputchar %%Printtoconsole %%Inputchar", "A"),
        ("@@x %%Printtoconsole %%Swap", ""),
        ("@@@@v?%%Empty?%%Store %%Evaluate @@v %%Obtain", ""),
        ("@@@@[g]?%%Empty?%%Store %%Evaluate @@[g] %%Obtain", ""),
        ("@@@@x?%%Printtoconsole %%Evaluate @@y %%Printtoconsole", ""),
        ("@@@@x?%%Printtoconsole %%Evaluatereplace @@y %%Printtoconsole", ""),
        ("@@v %%Empty %%Store @@@@v?%%Obtain %%Evaluatepermanently", ""),
        ("@@[g] %%Empty %%Store @@[g] %%Delete", ""),
        ("@@v %%Empty %%Store @@v %%Delete", ""),
        ("@@%%Nope %%Evaluate", ""),
    ):
        _check(_Machine, source, stdin)
    workspace.check_erasures(_WORKSPACE, _check, _Machine, populated, "λ")

    class WrongOutput(_Machine):
        def step(self):
            super().step()
            self.io.print_str("!")

    reject_faults(_check, _Machine, WrongOutput, populated, "λ")
    factory = prepare_machine(populated, {})
    left, right = factory(ScriptedIO("λ")), factory(ScriptedIO("λ"))
    held = right.workspace_snapshot()
    trace = expected[1]

    def checker():
        return workspace.workspace_view(
            trace, _WORKSPACE, lambda row: (*row[0][:4], row[-1]), _view
        )

    def sample(machine, checked, index):
        assert (
            checked(machine),
            machine.halted,
            machine.io.getvalue(),
            machine.io.position(),
            machine.io.progress(),
        ) == trace[index]

    left_check, right_check = checker(), checker()
    sample(left, left_check, 0)
    for index in range(1, 13):
        left.step()
        sample(left, left_check, index)
        assert right.workspace_snapshot() == held
    assert left.globals is not right.globals
    assert left.locals is not right.locals
    for index in range(13, len(trace)):
        left.step()
        sample(left, left_check, index)
        assert right.workspace_snapshot() == held
    finished_left = left.workspace_snapshot()
    sample(right, right_check, 0)
    for index in range(1, len(trace)):
        right.step()
        sample(right, right_check, index)
        assert left.workspace_snapshot() == finished_left
