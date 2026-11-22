"""Run Trml's semicolon-delimited term declarations and rewrite rules.

The text after `$` is the object program. Steps replace the leftmost
matching span, using declaration order to break a rule tie. The final
text is written once when no rule matches. Trml reads no stdin.

Decisions:
    A metavariable matches a nonempty declared term. If a split is
    ambiguous, try shortest bindings first. Repeat names must bind the
    same text. Only description whitespace is explicitly ignored by the
    spec; object text uses the same whitespace-insensitive reading.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from typing import Any

from esolangs.languages.trml.grammar import (
    Pattern,
    Rule,
    Variable,
    matches,
    parse,
    term_chart,
)
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import Completion, CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO

_WORKSPACE_MODEL = WorkspaceModel("trml-v1", ("text", "halted"))


def _advance(
    text: str, terms: tuple[Pattern, ...], rules: tuple[Rule, ...]
) -> str | None:
    """Return the next object text or signal normal form."""
    chart = term_chart(terms, text)
    for start in range(len(text)):
        for before, after in rules:
            match = next(matches(before, text, start, chart), None)
            if match is not None:
                end, bindings = match
                replacement = "".join(
                    bindings[part] if isinstance(part, Variable) else part
                    for part in after
                )
                return text[:start] + replacement + text[end:]
    return None


class _Machine:
    """Keep immutable object text as the cycle-detection state."""

    def __init__(
        self, terms: tuple[Pattern, ...], rules: tuple[Rule, ...], text: str, io: IO
    ) -> None:
        self.terms = terms
        self.rules = rules
        self.text = text
        self.io = io
        self.halted = False

    def snapshot(self) -> tuple[object, ...]:
        """Expose the state used for cycle detection."""
        return (self.text, self.halted)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture the current object text and completion flag."""
        return _WORKSPACE_MODEL.capture(text=self.text, halted=self.halted)

    def step(self) -> None:
        """Rewrite once or print the normal form and halt."""
        if self.halted:
            return
        result = _advance(self.text, self.terms, self.rules)
        if result is None:
            self.io.print_str(self.text)
            self.halted = True
        else:
            self.text = result


def _execute(
    terms: tuple[Pattern, ...], rules: tuple[Rule, ...], text: str, io: IO
) -> CompletionReport:
    return drive(_Machine(terms, rules, text, io), policy=Completion.HALTED)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse text once and bind each invocation to fresh state."""
    if not isinstance(source, str):
        raise TypeError("Trml requires text source")
    if options:
        raise TypeError("Trml accepts no runtime options")
    program = parse(source)
    return RuntimePlan(partial(_Machine, *program), partial(_execute, *program))


def complete(code: str, io: IO) -> CompletionReport:
    """Run the parsed source and report its halt."""
    return _execute(*parse(code), io)


def run(code: str, io: IO) -> None:
    """Normalize the object text and print it."""
    complete(code, io)


if __name__ == "__main__":
    script_main(run)
