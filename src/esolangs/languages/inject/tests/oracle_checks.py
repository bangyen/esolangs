"""Independent Inject line-store, fixed-label and input accounting model.

Named send/readto/skip/regex rules; 64 boundaries and three post-halt holds.
"""

import re

from esolangs.languages.inject.interpreter import _Machine, prepare_machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import reject_faults
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "inject-v1", "instruction stopped lines input_cursor input_reads spans"
)


class _ModelError(Exception):
    pass


def _labels(lines):
    opened, spans = {}, {}
    for index, line in enumerate(lines):
        word = line.strip()
        name = word[:-1]
        if not word.endswith(";") or not name or not name.replace("_", "a").isalnum():
            continue
        if name in spans:
            raise _ModelError("syntax")
        if name in opened:
            spans[name] = (opened.pop(name), index)
        else:
            opened[name] = index
    if opened:
        raise _ModelError("syntax")
    return spans


class _Store:
    """A transaction on ordinary lists and delimiter coordinates."""

    def __init__(self, lines, spans, pc, stopped):
        self.lines, self.spans = lines.copy(), dict(spans)
        self.pc, self.stopped = pc, stopped

    def contents(self, name):
        if name not in self.spans:
            raise _ModelError("syntax")
        begin, end = self.spans[name]
        return self.lines[begin + 1 : end]

    def replace(self, name, body):
        self.contents(name)
        begin, end = self.spans[name]
        delta = len(body) - (end - begin - 1)
        if delta and any(
            begin < boundary < end
            for label, ends in self.spans.items()
            if label != name
            for boundary in ends
        ):
            raise _ModelError("halt")
        if begin < self.pc:
            if self.pc + delta + 1 < 0:
                raise _ModelError("halt")
            self.pc += delta
        self.lines[begin + 1 : end] = body
        self.spans = {
            label: tuple(
                position + delta if position > begin else position for position in ends
            )
            for label, ends in self.spans.items()
        }

    def skip(self):
        ahead = [
            name
            for name, ends in self.spans.items()
            if ends[0] == self.pc + 1 and self.lines[ends[0]].strip() == name + ";"
        ]
        if ahead:
            self.pc = self.spans[ahead[0]][1] + 1
            return
        inside = [
            (end - begin, begin)
            for begin, end in self.spans.values()
            if begin < self.pc < end
        ]
        if inside:
            self.pc = min(inside, key=lambda item: item[0])[1]
        else:
            self.stopped = True

    def inject(self, rest):
        if "=" not in rest:
            raise _ModelError("syntax")
        name, expression = rest.split("=", 1)
        if "/" not in expression:
            raise _ModelError("syntax")
        pattern, replacement = expression.split("/", 1)
        try:
            regex = re.compile(pattern)
        except re.error as error:
            raise _ModelError("halt") from error
        body = self.contents(name)
        try:
            rewritten = [regex.sub(replacement, line) for line in body]
        except (re.error, IndexError) as error:
            raise _ModelError("halt") from error
        self.replace(name, rewritten)

    def execute(self, command, rest, line_in):
        if command == "send":
            output = "".join(line + "\n" for line in self.contents(rest))
        else:
            output = ""
        if command == "readto":
            self.replace(rest, [] if line_in is None else [line_in])
        elif command == "inject":
            self.inject(rest)
        elif command == "skip":
            if rest:
                raise _ModelError("syntax")
            self.skip()
            return output
        elif command == "skipif" and self.contents(rest):
            self.skip()
            return output
        elif command == "skipq":
            left, separator, right = rest.partition(" ")
            if not separator or not right.strip():
                raise _ModelError("syntax")
            if self.contents(left) == self.contents(right.strip()):
                self.skip()
                return output
        self.pc += 1
        return output


def _model(source, stdin, cap=64):
    lines = source.split("\n") if isinstance(source, str) else list(source)
    try:
        spans = _labels(lines)
    except _ModelError:
        return "syntax", [(None, False, "", 0, 0)]
    pc = cursor = attempts = reads = past_end = 0
    stopped, output, trace = False, "", []

    def row():
        parts = (pc, stopped, tuple(lines), cursor, attempts, frozenset(spans.items()))
        return (
            (*parts, reads, past_end),
            stopped or pc >= len(lines),
            output,
            cursor,
            cursor,
        )

    for tick in range(cap + 1):
        trace.append(row())
        if stopped or pc >= len(lines):
            return None, trace + [row()] * 3
        if tick == cap:
            break
        command, _, rest = lines[pc].strip().partition(" ")
        line_in = None
        if command == "readto":
            attempts += 1
            if cursor == len(stdin):
                past_end += 1
            else:
                end = stdin.find("\n", cursor)
                stop = len(stdin) if end < 0 else end + 1
                line_in = stdin[cursor:stop].removesuffix("\n").removesuffix("\r")
                cursor = stop
                reads += 1
        changed = _Store(lines, spans, pc, stopped)
        try:
            emitted = changed.execute(command, rest.strip(), line_in)
        except _ModelError as error:
            return str(error), [*trace, row()]
        lines, spans, pc, stopped = (
            changed.lines,
            changed.spans,
            changed.pc,
            changed.stopped,
        )
        output += emitted
    return None, trace


def _view(machine):
    return (
        machine.ind,
        machine.done,
        tuple(machine.lines),
        machine.io.progress(),
        machine._input_reads,
        frozenset(machine.spans.items()),
        machine.io.reads,
        machine.io.past_end,
    )


def _check(factory, source, stdin="unused", *, cap=64):
    return workspace.agrees(
        _model(source, stdin, cap),
        (factory, source, stdin),
        (_WORKSPACE, lambda row: row[0][:6]),
        _view,
        cap=cap,
        context=(source, stdin),
    )


def check_raw_inject():
    populated = "d;\nold\nolder\nd;\nreadto d\nsend d\nskip"
    expected = _check(_Machine, populated, "λ\n")
    for index in range(6):
        assert any(row[0][index] != expected[1][0][0][index] for row in expected[1])
    for source, stdin in (
        ("", ""),
        ("a;", ""),
        ("a;\na;\na;", ""),
        ("send nowhere", ""),
        ("readto nowhere", "A\n"),
        ("readto d\nsend d\nskip\nd;\nold\nd;", ""),
        ("readto d\nsend d\nskip\nd;\nold\nd;", "\r\n"),
        ("inject d=x/xxx\nsend d\nskip\nd;\nx\nd;", ""),
        ("inject d=(/x\nd;\nx\nd;", ""),
        ("inject d=x/\\2\nd;\nx\nd;", ""),
        ("inject d\nd;\nd;", ""),
        ("inject d=x\nd;\nd;", ""),
        ("skip now", ""),
        ("d;\nd;\nskipq d", ""),
        ("readto d\nskip\nd;\nin;\nx\nin;\nd;", "q\n"),
        ("d;\nreadto d\nx\ny\nd;", ""),
        ("loop;\nsend d\nskip\nloop;\nd;\nx\nd;", ""),
    ):
        _check(_Machine, source, stdin)
    workspace.check_erasures(_WORKSPACE, _check, _Machine, populated, "λ\n")

    class WrongOutput(_Machine):
        def step(self):
            super().step()
            self.io.print_str("!")

    reject_faults(_check, _Machine, WrongOutput, populated, "λ\n")
    factory = prepare_machine(populated.split("\n"), {})
    left, right = factory(ScriptedIO("λ\n")), factory(ScriptedIO("λ\n"))
    held = right.workspace_snapshot()
    for machine, sibling in ((left, right), (right, left)):
        checked = workspace.workspace_view(
            expected[1], _WORKSPACE, lambda row: row[0][:6], _view
        )
        previous = sibling.workspace_snapshot()
        for index, reference in enumerate(expected[1]):
            if index:
                machine.step()
            assert (
                checked(machine),
                machine.halted,
                machine.io.getvalue(),
                machine.io.position(),
                machine.io.progress(),
            ) == reference
            assert sibling.workspace_snapshot() == previous
        if machine is left:
            assert right.workspace_snapshot() == held
    assert left.lines is not right.lines
    assert left.spans is not right.spans
