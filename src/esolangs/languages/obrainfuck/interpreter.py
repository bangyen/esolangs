"""Interpreter for oBrainfuck.

Brainfuck whose k-th ``[`` pairs with the k-th ``]`` by occurrence, not
nesting.  The wiki's C lowering, ``[`` as ``goto Rk;Lk:`` and ``]`` as
``Rk:if(*cur)goto Lk;``, makes ``[`` jump straight to its partner's test,
which is Brainfuck's "skip on zero" test at the opener; so only the
bracket map differs from :mod:`esolangs.languages.brainfuck.interpreter`,
whose machine runs here unchanged.

Input/output:
    As Brainfuck: ``,`` reads one character into the cell modulo 256,
    ``.`` writes one.  ``,`` at EOF raises (the page inherits Brainfuck's
    unspecified EOF; this repo's Brainfuck raises).

Errors:
    ProgramError: different ``[`` and ``]`` counts.
    InputExhaustedError: ``,`` at EOF.

Decisions:
    * The name keeps the page's own spelling, oBrainfuck; the wiki title's
      capital is MediaWiki's.
    * A closer may precede its opener: the page calls ``][`` "a valid
      program that falls into an infinite loop".
    * Cells, tape growth and ``,`` follow this repo's Brainfuck; the page
      changes only pairing.
    * Brainfuck's compiled fast path is not reused: its ``[-]`` and
      transfer peepholes assume the substring's brackets pair together,
      false under ordinal pairing (``[[-]]`` pairs the first ``[`` with the
      inner ``]``).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from esolangs.languages.brainfuck.interpreter import _Machine
from esolangs.languages.obrainfuck.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._validate import require_text_source
from esolangs.runtime.brackets import BracketProgram, unmatched
from esolangs.runtime.io import IO


def ordinal_brackets(code: str) -> dict[int, int]:
    """Map the k-th ``[`` and k-th ``]`` to each other, both ways.

    Raises :class:`ValueError` on unequal counts, naming the first bracket
    left without a partner.
    """
    opens = [i for i, char in enumerate(code) if char == "["]
    closes = [i for i, char in enumerate(code) if char == "]"]
    if len(opens) > len(closes):
        raise unmatched("[", opens[len(closes)], "add a ']' for every '['")
    if len(closes) > len(opens):
        raise unmatched("]", closes[len(opens)], "add a '[' for every ']'")
    pairs = dict(zip(opens, closes, strict=True))
    pairs.update(zip(closes, opens, strict=True))
    return pairs


def parse(code: str) -> BracketProgram:
    """Return ``code`` with its read-only ordinal loop map."""
    return BracketProgram(code, MappingProxyType(ordinal_brackets(code)))


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Pair brackets once; each IO port receives a fresh Brainfuck machine."""
    source = require_text_source(source, options, "oBrainfuck")
    program = parse(source)
    return RuntimePlan(
        lambda io: _Machine(program, io),
        lambda io: drive(_Machine(program, io), policy=CAPABILITIES.completion),
    )


def _execute(code: str, io: IO) -> CompletionReport:
    return drive(_Machine(parse(code), io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run ``code`` to completion on ``io``."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
