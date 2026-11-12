"""Complete bounded memory/control traces from the unchanged independent oracle.

The old decimal-source cohort remains the scope: no comment/numeric-grammar or
host-allocation universality follows from these small admitted programs.
"""

from dataclasses import dataclass, replace

from tests.interpreters.semantic_oracles import subleq

CAP = 200


@dataclass(frozen=True)
class Row:
    """One immutable independent boundary, including physical IO metadata."""

    memory: tuple[int, ...] | None
    pc: int | None
    halted: bool
    output: str
    cursor: int
    reads: int
    past_end: int
    character_reads: bool
    newline: bool
    steps: int

    @property
    def parts(self):
        """Return all three declared semantic components in model order."""
        return self.memory, self.pc, self.cursor

    @property
    def legacy(self):
        """Return the old full-observer row, without losing new metadata."""
        state = None if self.memory is None else (self.memory, self.pc)
        return state, self.halted, self.output, self.cursor, self.cursor


def predict(source, stdin, cap=CAP):
    """Replay every prefix of the SAME old oracle; no second transition engine."""
    rows = []
    reads = past = 0
    character = newline = False
    for steps in range(cap + 1):
        try:
            result = subleq(source, stdin, steps)
        except (ValueError, RuntimeError, EOFError) as error:
            kind = (
                "input"
                if isinstance(error, EOFError)
                else "halt"
                if isinstance(error, RuntimeError)
                else "syntax"
            )
            if not rows:
                return kind, (
                    Row(
                        memory=None,
                        pc=None,
                        halted=False,
                        output="",
                        cursor=0,
                        reads=0,
                        past_end=0,
                        character_reads=False,
                        newline=False,
                        steps=0,
                    ),
                )
            before = rows[-1]
            if kind == "input":
                character = True
                past += 1
            failed = replace(before, past_end=past, character_reads=character)
            return kind, (*rows, failed)
        if rows:
            before = rows[-1]
            a, b, _target = before.memory[before.pc : before.pc + 3]
            if a == -1:
                reads += 1
                character = True
                newline = False
                assert result.consumed == before.cursor + 1
            elif b == -1:
                value = before.memory[a] if a < len(before.memory) else 0
                emitted = chr(value % 256)
                assert result.output == before.output + emitted
                newline = emitted != "\n"
        row = Row(
            result.memory,
            result.ip,
            result.halted,
            result.output,
            result.consumed,
            reads,
            past,
            character,
            newline,
            steps,
        )
        rows.append(row)
        if result.halted:
            return None, (*rows, row, row, row)
    return None, tuple(rows)


def legacy_prediction(source, stdin):
    """Preserve the complete observer protocol and its200-command cap."""
    error, rows = predict(source, stdin)
    return error, [row.legacy for row in rows]
