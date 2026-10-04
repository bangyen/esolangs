"""Mutable call scheduler, independent of Grapheme's tuple transition."""

from dataclasses import dataclass

from tests.interpreters.grapheme_reference import Function, InvalidError, Reference


@dataclass
class Frame:
    source: str
    cursor: int = 0
    mode: str = ""
    buffer: str = ""
    pending: int = -1
    repeat: bool = False


class Stepped:
    def __init__(self, source, text=""):
        source = source.replace("\n", "")
        if any(not "A" <= c <= "Z" for c in source):
            raise ValueError
        self.evaluator = Reference(text)
        self.frames = [Frame(source)]

    def finish(self):
        frame = self.frames[-1]
        if frame.mode:
            self.evaluator.flush(frame.mode, frame.buffer)
        if frame.repeat and self.evaluator.stack:
            self.frames[-1] = Frame(frame.source, repeat=True)
        else:
            self.frames.pop()

    def step(self):
        if not self.frames:
            return
        frame = self.frames[-1]
        ref = self.evaluator
        if frame.cursor >= len(frame.source):
            self.finish()
            return
        op = frame.source[frame.cursor]
        if frame.mode:
            if op == frame.mode:
                ref.flush(frame.mode, frame.buffer)
                frame.mode = ""
                frame.buffer = ""
            else:
                frame.buffer += op
            frame.cursor += 1
            return
        cursor = frame.cursor
        pending = frame.pending
        body = None
        repeat = False
        oldstack = list(ref.stack)
        try:
            if op in "EFH":
                frame.mode = op
            elif op in "GIQZ":
                value = ref.pop()
                if op == "G":
                    body = value.source if isinstance(value, Function) else value
                    if not isinstance(body, str):
                        raise InvalidError("G")
                elif op == "I":
                    if isinstance(value, Function):
                        body = value.source
                    else:
                        ref.stack.append(value)
                elif op == "Q":
                    condition = ref.pop()
                    if isinstance(value, Function) and ref.truth(condition):
                        body = value.source
                elif isinstance(value, Function) and ref.stack:
                    body = value.source
                    repeat = True
            elif op in "UVX":
                condition = ref.pop()
                if op == "U" and not ref.truth(condition):
                    cursor += 1
                elif op == "V":
                    amount = ref.pop()
                    if not ref.truth(condition):
                        cursor += ref.integer(amount)
                elif op == "X":
                    if ref.truth(condition):
                        pending = cursor
                    else:
                        cursor += 1
            else:
                ref.execute(op)
        except (InvalidError, ValueError):
            ref.stack = oldstack
            raise
        cursor += 1
        if pending >= 0 and cursor == pending + 2:
            cursor += 1
            pending = -1
        frame.cursor = cursor
        frame.pending = pending
        if body is not None:
            self.frames.append(Frame(body, repeat=repeat))
        while self.frames and self.frames[-1].cursor >= len(self.frames[-1].source):
            was = self.frames[-1]
            self.finish()
            if (
                self.frames
                and self.frames[-1].repeat
                and self.frames[-1].cursor == 0
                and self.frames[-1].source == was.source
            ):
                break
