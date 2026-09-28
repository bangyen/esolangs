"""Screen every boolean generator for characters its programs do not need.

For each registry language with a text generator, take a few small tables,
and greedily delete every maximal run of one character (and, failing that,
each single character of the run) left to right, keeping a deletion when
every row still answers correctly.  The figure is the share of the program
deleted, summed over the tables, with the whitespace share apart: a
language that tolerates missing spaces loses them all, which is layout,
not construction.  A template's input runs are never
touched, so a deletion holds for every fill of it.

Unlike ``input_reorder.py`` and ``transforms.py`` this is not
a bound on what a construction could buy: every deletion kept is a program
that still computes its table.  But it is one program per table, so a
deletion that relies on that table (a branch no row of it reaches) says
the construction emits dead text for that table, not that the character is
never needed.  A row that runs past ``--timeout`` counts as wrong, so a
deletion that makes a program diverge or merely slow is never kept.
"""

import argparse
import sys
import warnings
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _build import generators

import esolangs
from esolangs._answers import encode_inputs, read_answer
from esolangs._describe import describe
from esolangs.exceptions import EsolangError, ExecutionTimeoutError
from esolangs.registry import resolve
from esolangs.tagged import _Template

#: AND, XOR, a one-input table wearing a second input, and a three-input
#: majority: a fold, no fold, an ignored input, and a deeper tree.
TABLES = ("0001", "0110", "0011", "00010111")


class _Program:
    """One generated program: its text, and how to run a row of it."""

    def __init__(self, name: str, table: str, timeout: float) -> None:
        self.name, self.table, self.timeout = name, table, timeout
        self.inputs = len(table).bit_length() - 1
        facts = describe(name)
        self.terminating = facts["answer_mode"] == "termination"
        generated = esolangs.generate(name, table)
        self.text = str(generated)
        if isinstance(generated, _Template):
            self.char: str | None = generated.char
            self.setters = generated.setters
        else:
            self.char = None
        if self.terminating:
            encoding = list(facts["answer_encoding"])
            self.halts = str(encoding.index("halts"))
            self.diverges = str(encoding.index("diverges"))

    def frozen(self) -> set[int]:
        """Return the positions of the template's input runs."""
        if self.char is None:
            return set()
        return {i for i, c in enumerate(self.text) if c == self.char}

    def correct(self, text: str) -> bool:
        """Return whether ``text`` answers every row of the table."""
        for row in range(len(self.table)):
            bits = [(row >> (self.inputs - 1 - i)) & 1 for i in range(self.inputs)]
            try:
                if self.char is not None:
                    template = _Template(text, self.name, self.char, self.setters)
                    source = str(esolangs.instantiate(self.name, template, bits))
                    stdin = ""
                else:
                    source = text
                    stdin = encode_inputs(self.name, bits, self.table)
                if self.terminating:
                    answer = self._terminates(source, stdin)
                else:
                    output = esolangs.run(self.name, source, stdin, self.timeout)
                    answer = read_answer(self.name, output)
            except (EsolangError, ValueError, RecursionError):
                return False
            if answer != self.table[row]:
                return False
        return True

    def _terminates(self, source: str, stdin: str) -> str:
        """Return a termination-answer row's bit, as ``esolangs.evaluate``."""
        from esolangs._evaluate import _terminates

        try:
            return _terminates(
                self.name, source, stdin, self.timeout, self.halts, self.diverges
            )
        except ExecutionTimeoutError:
            return self.diverges


def _runs(text: str, frozen: set[int]) -> list[tuple[int, int]]:
    """Return the maximal runs of one character outside ``frozen``."""
    spans, start = [], 0
    for i in range(1, len(text) + 1):
        if i == len(text) or text[i] != text[start] or i in frozen or start in frozen:
            if start not in frozen:
                spans.append((start, i))
            start = i
    return spans


def shrink(program: _Program) -> str:
    """Delete greedily, left to right, keeping what leaves the table intact."""
    text = program.text
    position = 0
    while True:
        frozen = {i for i, c in enumerate(text) if c == program.char}
        spans = [s for s in _runs(text, frozen) if s[0] >= position]
        if not spans:
            return text
        start, end = spans[0]
        for cut_end in (end, start + 1) if end - start > 1 else (end,):
            candidate = text[:start] + text[cut_end:]
            if candidate and program.correct(candidate):
                text = candidate
                break
        else:
            position = end
            continue
        position = start


def _spaces(text: str) -> int:
    return sum(c.isspace() for c in text)


def screen(
    name: str, limit: int, timeout: float
) -> tuple[float, float, int, float] | None:
    """Return (deleted %, whitespace %, chars deleted, seconds), or None."""
    start = perf_counter()
    before = after = spaces = 0
    for table in TABLES:
        try:
            program = _Program(name, table, timeout)
        except (EsolangError, ValueError):
            continue
        if len(program.text) > limit or not program.correct(program.text):
            continue
        shrunk = shrink(program)
        before += len(program.text)
        after += len(shrunk)
        spaces += _spaces(program.text) - _spaces(shrunk)
    if not before:
        return None
    dead, blank = 100 * (1 - after / before), 100 * spaces / before
    return dead, blank, before - after, perf_counter() - start


def main() -> None:
    """Screen the registry and print one row per language, most dead first."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("languages", nargs="*", help="registry names (default all)")
    parser.add_argument("--limit", type=int, default=2000, help="skip longer programs")
    parser.add_argument("--timeout", type=float, default=0.5, help="seconds per row")
    args = parser.parse_args()
    # ``resolve`` takes keys and aliases too: ``bf-pda`` failed every row.
    names = [resolve(name) for name in args.languages] or [
        key for key, _gen in generators()
    ]
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name in names:
            result = screen(name, args.limit, args.timeout)
            if result is not None:
                rows.append((name, *result))
                print(f"  {name}: {result[0]:.1f}%", flush=True)
    rows.sort(key=lambda row: (row[2] - row[1], row[0]))
    print(
        f"{'language':<32}{'dead%':>7}{'space%':>7}{'other%':>7}{'chars':>7}{'sec':>7}"
    )
    for name, dead, blank, chars, elapsed in rows:
        print(
            f"{name:<32}{dead:>7.1f}{blank:>7.1f}{dead - blank:>7.1f}"
            f"{chars:>7}{elapsed:>7.1f}"
        )


if __name__ == "__main__":
    main()
