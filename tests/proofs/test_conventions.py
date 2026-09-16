"""``docs/roadmap.md``'s conventions audit must agree with the generators.

The cheap half parses the table and checks its names and vocabulary.  The
measured half builds every embedding generator at n=2 and n=3 on dense and
parity tables, fills every row, and reads the four conventions off the
programs: an absent generator must hold all four, a ``Holds`` cell must
hold, and an open "No spaces" cell must have spaces to remove.  An ``Open``
cell is then executed: the spaces the row names are deleted and the program
must answer every row the same -- the document's claim, run.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable

import pytest

import esolangs
from esolangs.registry import BY_BOOLEAN
from esolangs.tools.examples import BOOLEAN_EXAMPLES, BooleanExample
from tests.proofs._conventions import HOLDS, LANGUAGE, OPEN, Conventions, load

_VERDICTS = {HOLDS, OPEN, LANGUAGE}


@pytest.fixture(scope="module")
def audit() -> Conventions:
    """The parsed conventions audit, read once for the module."""
    return load()


def _embedding() -> dict[str, BooleanExample]:
    """The embedding examples, keyed by the registry display name."""
    names = {lang.interpreter: lang.name for lang in BY_BOOLEAN.values()}
    return {
        names[example.interpreter]: example
        for example in BOOLEAN_EXAMPLES.values()
        if example.fill is not None
    }


def _tables(n: int) -> tuple[str, str]:
    parity = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**n))
    dense = "".join("1" if (i * 7 + 3) % 5 < 2 else "0" for i in range(2**n))
    return parity, dense


def _measure(example: BooleanExample) -> dict[str, bool]:
    """Whether each convention holds over n=2..3, both shapes, every fill."""
    assert example.fill is not None
    single = width = order = spaces = True
    for n in (2, 3):
        for table in _tables(n):
            template = example.generator(table, **dict(example.kwargs))
            slots = [int(s) for s in re.findall(r"\{X(\d+)\}", template)]
            single &= sorted(slots) == list(range(n)) and "{C" not in template
            order &= slots == sorted(slots)
            programs = [
                example.fill(template, list(bits))
                for bits in itertools.product((0, 1), repeat=n)
            ]
            width &= len({len(p) for p in programs}) == 1
            spaces &= not any(" " in p or "\t" in p for p in programs)
    return {
        "Single embed": single,
        "Constant width": width,
        "Slot order": order,
        "No spaces": spaces,
    }


def test_the_audit_names_real_embedding_generators(audit: Conventions) -> None:
    assert set(audit.by_name()) <= set(_embedding())


def test_every_verdict_is_a_known_one(audit: Conventions) -> None:
    for row in audit.rows:
        assert set(row.verdicts) <= _VERDICTS, row


def test_the_audit_holds_only_open_rows(audit: Conventions) -> None:
    closed = [row.generator for row in audit.rows if not row.is_open]
    assert not closed, f"rows that hold every convention should leave: {closed}"


@pytest.mark.slow  # ~5s: builds and fills every embedding generator at n=2..3
def test_the_audit_matches_the_programs(audit: Conventions) -> None:
    rows = audit.by_name()
    for name, example in _embedding().items():
        measured = _measure(example)
        row = rows.get(name)
        if row is None:
            failing = [c for c, ok in measured.items() if not ok]
            assert not failing, f"{name} is absent from the audit but fails {failing}"
            continue
        for column, verdict in zip(measured, row.verdicts, strict=True):
            if verdict == HOLDS:
                assert measured[column], f"{name}: {column} is {verdict} but fails"
            else:
                assert not measured[column], f"{name}: {column} is {verdict} but holds"


# How each ``Open`` row's ignored spaces are deleted.  Bitdeque's ``GOTO``
# takes its number after zero or more spaces and its tokenizer is a
# ``findall``, so every space goes; RAM0 tokenizes on
# ``[ZANCLS]|[1-9]\d*``, so only a space between two numbers is read;
# Minsky Swap filters its first line to ``+~*`` but reads its second as
# delimited numbers; Nopstacle's pad is the trailing blank on each row.
_STRIP: dict[str, Callable[[str], str]] = {
    "BIO": lambda p: p.replace(" ", ""),
    "Bitdeque": lambda p: p.replace(" ", ""),
    "RAM0": lambda p: re.sub(r"(?<=[^\d ]) | (?=[^\d ])", "", p),
    "Minsky Swap": lambda p: (
        p.split("\n", 1)[0].replace(" ", "") + "\n" + p.split("\n", 1)[1]
    ),
    "Nopstacle": lambda p: "\n".join(line.rstrip() for line in p.splitlines()),
}


def _answer(name: str, example: BooleanExample, program: str) -> object:
    if example.answer_mode == "termination":
        from esolangs.interpreters.grid_based.nopstacle import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert name == "Nopstacle"
        return run_until_halt_or_cycle(_Machine(program.splitlines()))
    return esolangs.run(name, program)


def test_the_strip_rules_are_exactly_the_open_rows(audit: Conventions) -> None:
    open_rows = {row.generator for row in audit.rows if row.no_spaces == OPEN}
    assert set(_STRIP) == open_rows


@pytest.mark.slow  # runs every fill of the Open rows twice
@pytest.mark.parametrize("name", sorted(_STRIP))
def test_an_open_row_runs_the_same_without_its_spaces(name: str) -> None:
    example = _embedding()[name]
    assert example.fill is not None
    checked = 0
    for n in (2, 3):
        for table in _tables(n):
            template = example.generator(table, **dict(example.kwargs))
            for bits in itertools.product((0, 1), repeat=n):
                program = example.fill(template, list(bits))
                stripped = _STRIP[name](program)
                assert len(stripped) < len(program), (name, bits)
                assert _answer(name, example, stripped) == _answer(
                    name, example, program
                ), (name, table, bits)
                checked += 1
    assert checked == 24


#: The ``Language`` rows the harness above can run.  ArrowQueue and Crement
#: answer by termination through their own machines and are not driven here.
_RUNNABLE_LANGUAGE_ROWS = ("Back", "COD", "WII2D")


@pytest.mark.slow  # the positive control for the test above
@pytest.mark.parametrize("name", _RUNNABLE_LANGUAGE_ROWS)
def test_a_language_row_reads_its_spaces(name: str, audit: Conventions) -> None:
    """Deleting every space from a ``Language`` row changes some answer.

    Without this the test above proves nothing: a stripping rule that
    deletes read spaces would pass wherever no program happens to exercise
    them.  Here the same harness must *notice* a deleted space -- a
    different dump or output, or a program that no longer loads.
    """
    assert audit.by_name()[name].no_spaces == LANGUAGE
    example = _embedding()[name]
    assert example.fill is not None
    for n in (2, 3):
        for table in _tables(n):
            template = example.generator(table, **dict(example.kwargs))
            for bits in itertools.product((0, 1), repeat=n):
                program = example.fill(template, list(bits))
                steps, output = _run_within(name, program, 10**6)
                assert steps is not None, (name, bits)
                # A deleted cell can send a grid's pointer into a loop, so
                # the mutant runs under a budget the original's own count
                # sets, rather than a clock or a cycle prover that a
                # growing tape defeats.  Running past it is the change.
                halted, got = _run_within(
                    name, program.replace(" ", ""), 2 * steps + 1000
                )
                if halted is None or got != output:
                    return
    pytest.fail(f"{name} answers the same with every space deleted")


def _run_within(name: str, program: str, budget: int) -> tuple[int | None, str]:
    """Step ``program`` to its halt: ``(steps, output)``, or ``(None, "")``.

    ``None`` covers a program that does not load, and one that is still
    running at ``budget`` steps.
    """
    from esolangs.vm import make_vm

    try:
        vm = make_vm(name, program)
        steps = 0
        while not vm.halted:
            if steps == budget:
                return None, ""
            vm.step()
            steps += 1
        # The dumping languages write on the step after their halt.
        vm.step()
        return steps, vm.output
    except Exception:
        return None, ""
