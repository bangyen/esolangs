"""Run every committed example program and check its output.

``examples/`` holds only programs sampled from a *parameterized* generator:
the boolean programs from ``esolangs.tools.boolean``, which take a truth
table and an input combination.  Each committed file is one point sampled
from that space, so a companion test keeps it in sync with whatever the
generator produces today -- the check has teeth precisely because the
generator could produce something else.

Fixed programs with no such space -- cat, truth-machine, and multiply -- are
plain test fixtures rather than examples, and live inline in the matching
``tests/interpreters/test_*.py`` instead.
"""

from pathlib import Path

import pytest

from esolangs.registry import LANGUAGES, canonical_id
from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES as BOOLEAN_GENERATED
from esolangs.tools.boolean.examples import HAND_WRITTEN
from esolangs.vm import (
    _FramedMachine,
    _TapeMachine,
    make_vm,
    run_until_halt_or_ancestor,
    run_until_halt_or_cycle,
    run_until_halt_or_growth,
)
from tests.tools.boolean_runners import one_two_three_result, point_break_result

BASE_DIR = Path(__file__).parents[2]


def _file_name(display_name: str) -> str:
    return display_name.lower().replace(" ", "-")


# The VM registry is keyed by the language's display name, while boolean
# examples are keyed by their filesystem stem.  The interpreter module is
# shared metadata and uniquely identifies the registered display name.
VM_LANGUAGE = {
    lang.interpreter: lang.name
    for lang in LANGUAGES.values()
    if lang.interpreter is not None
}

# container halts by calling sys.exit(0)
EXITS = {"container"}

# Boolean examples whose answer is their *termination* rather than their
# output: each halts for a 0 and loops forever for a 1, so the committed
# program must be the halting branch.
#
# :func:`test_boolean_example` runs a committed program to completion with no
# step cap, which is right for every other language and fatal for these
# three: a file holding the looping branch does not fail, it hangs the
# suite with no diagnostic.  Nothing about the entry forces the halting row
# -- ``bits`` is just data, and a wrong one regenerates a looping file --
# so :func:`test_halt_convention_examples_halt` checks the committed
# program terminates *before* anything runs it unbounded.
HALT_CONVENTION = {"123", "arrowqueue", "point-break"}

# Boolean generators deliberately without a committed example, by canonical
# id, each for a stated reason.  A language qualifies for an example when its
# answer is recoverable from what its program prints (see
# ``esolangs.tools.boolean.examples``); one whose answer no program can
# report belongs here rather than silently missing.
#
# Empty, and that is the claim: every boolean generator currently has one.
_NO_EXAMPLE: set[str] = set()


@pytest.mark.parametrize("name", sorted(BOOLEAN_GENERATED))
def test_boolean_example_matches_generator(name: str) -> None:
    """Each committed boolean program is what its generator produces today.

    The counterpart of :func:`test_example_files_match_generator` for the
    boolean examples; refresh them with
    ``python scripts/write_examples.py boolean``. The file ends with a
    single POSIX newline.
    """
    path = BASE_DIR / "examples" / "boolean" / f"{name}.txt"
    expected = BOOLEAN_GENERATED[name].build().rstrip("\n") + "\n"
    assert path.read_text(encoding="utf-8") == expected


def test_boolean_examples_cover_every_committed_file() -> None:
    """Every file in examples/boolean is accounted for, and vice versa."""
    on_disk = {p.stem for p in (BASE_DIR / "examples" / "boolean").glob("*.txt")}
    assert on_disk == set(BOOLEAN_GENERATED) | set(HAND_WRITTEN)


@pytest.mark.parametrize("name", sorted(HALT_CONVENTION))
def test_halt_convention_examples_halt(name: str) -> None:
    """The committed program of a halt-convention language terminates.

    These three answer with termination rather than output, so the
    committed file is the halting (0) branch; ArrowQueue and Point Break
    print nothing on it, and 123's junk write-bytes are ignored.
    :func:`test_boolean_example` then runs it with no step cap -- which
    turns a file holding the *looping* branch into a hung suite rather
    than a failure, with nothing to say which file did it.

    The bound is state-cycle detection, not a step budget: these
    interpreters are step-capable, and a deterministic run that revisits
    its whole internal state has looped forever, so the repeated state
    proves divergence immediately instead of after an arbitrary wait.
    """
    program = (
        (BASE_DIR / "examples" / "boolean" / f"{name}.txt")
        .read_text(encoding="utf-8")
        .rstrip("\n")
    )
    assert _halts(name, program, list(BOOLEAN_GENERATED[name].inputs)), (
        f"examples/boolean/{name}.txt holds the looping branch; the committed "
        f"program must be the halting one or the suite hangs running it"
    )


def _halts(name: str, program: str, inputs: list[str]) -> bool:
    """Whether ``name``'s committed program terminates, by cycle detection.

    ``inputs`` are the example's own stdin lines: 123 and ArrowQueue embed
    their bits and read nothing, but Point Break reads its two with ``?``,
    so running it on an empty stdin raises ``EOFError`` instead of
    answering the question this test asks.
    """
    from esolangs.vm import run_until_halt_or_cycle

    if name == "arrowqueue":
        from esolangs.interpreters.grid_based.arrowqueue import _Machine as AQ

        return run_until_halt_or_cycle(AQ(program.splitlines()))
    if name == "123":
        return one_two_three_result(program) == "0"
    return point_break_result(program, inputs) == "0"


def test_every_boolean_generator_has_an_example() -> None:
    """Every registered boolean generator has a committed example.

    The check above compares the files on disk against
    :data:`BOOLEAN_EXAMPLES`, which is the hand-maintained table in
    ``esolangs.tools.boolean.examples``.  A generator absent from *both* --
    no entry and so no file -- cancels out of that comparison and is
    invisible to it, which is how seven generators (%^2^-1, 123, CV(N)(C),
    Fargo, Minifuck, SLOW ACV MAMMALIAN and Super SNUSP) went uncovered.

    The registry is the only source that knows a generator exists, so it is
    what this test compares against.  A language whose answer no program can
    report belongs in :data:`_NO_EXAMPLE` with the reason, not silently
    missing -- an empty exemption set is the assertion that none exist.
    """
    registered = {
        canonical_id(lang.name) for lang in LANGUAGES.values() if lang.boolean
    }
    covered = {
        canonical_id(stem.replace("-", " "))
        for stem in set(BOOLEAN_GENERATED) | set(HAND_WRITTEN)
    }
    assert registered - covered == _NO_EXAMPLE, (
        "boolean generators with no committed example: "
        f"{sorted(registered - covered - _NO_EXAMPLE)}"
    )


# The boolean examples demonstrate a language's boolean-function capability
# that is not an I/O truth machine (see docs/walls.md).  They are derived
# from ``esolangs.tools.boolean.examples``, which records for each committed
# program the generator, truth table, and input combination that produced it
# -- so the files stay in sync with the generators.
#
# The input-reading languages take their bits on stdin; the parameterized
# ones (see ``esolangs.tools.boolean.parameterized``) have the bits embedded
# in the program text and read no input.  ArrowQueue and Point Break have no
# output at all: their result is the halt-vs-loop convention, so only the
# terminating (`0`) branch is committed -- the `1` branch loops forever by
# definition and is not executed.
BOOLEAN_EXAMPLES = {
    stem: (ex.interpreter, list(ex.inputs), ex.expected, ex.split, dict(ex.kwargs))
    for stem, ex in BOOLEAN_GENERATED.items()
} | {
    stem: (interpreter, list(inputs), expected, split, {})
    for stem, (interpreter, inputs, expected, split) in HAND_WRITTEN.items()
}


def _prove_halt(vm: object) -> bool:
    """Drive ``vm`` to its halt with the prover its machine supports.

    Every example here is expected to halt, so any of the three provers
    answers ``True`` on a correct file.  Which one runs matters for the
    *incorrect* file, which is what this test exists to catch: the three
    disagree on what they can conclude, and only about non-halting.

    ``run_until_halt_or_cycle`` decides exact state repeats and nothing
    else.  A machine whose state grows every step -- a recursion that
    pushes a frame per call, a tape that gains a cell per lap -- never
    repeats one, so on those the exact-state prover does not run long, it
    *cannot terminate*, and a broken example would hang the suite instead
    of failing it.  ``docs/walls.md`` carries the measured instance: a
    Suptiftam program short of its input grows the snapshot about 32 bytes
    per step, and holding those states OOM-killed the probe, while the
    ancestor prover answered in under a second.

    So dispatch on what the machine actually implements.  The protocols
    are ``runtime_checkable`` and opting into one is a claim about the
    language's semantics, not merely about having the attributes -- five
    tape-shaped languages here define ``tape`` and ``ptr`` yet are
    deliberately not ``_TapeMachine``, and ``isinstance`` is what tells
    them apart.  The provers raise ``TypeError`` on a machine outside
    their protocol, so a wrong branch here fails loudly rather than
    reporting a verdict about state the machine does not have.
    """
    machine = getattr(vm, "_machine", vm)
    if isinstance(machine, _FramedMachine):
        return run_until_halt_or_ancestor(vm)
    if isinstance(machine, _TapeMachine):
        return run_until_halt_or_growth(vm)
    return run_until_halt_or_cycle(vm)


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
def test_boolean_example(name: str) -> None:
    _module, inputs, expected, _splitlines, _kwargs = BOOLEAN_EXAMPLES[name]
    program = (
        (BASE_DIR / "examples" / "boolean" / f"{name}.txt")
        .read_text(encoding="utf-8")
        .rstrip("\n")
    )
    vm = make_vm(VM_LANGUAGE[_module], program, "".join(f"{line}\n" for line in inputs))
    if name == "a-painter-ant":
        # Its implicit loop has no halting state: a repeated snapshot is its
        # language-defined stop.  The public interpreter renders only at a
        # pass boundary, so finish this already-proven periodic pass first.
        assert not run_until_halt_or_cycle(vm)
        while vm.ip != 0:
            vm.step()
        got = vm._machine.render()  # type: ignore[attr-defined]  # noqa: SLF001
    elif name == "suffolk":
        # Suffolk's input-reading programs stop on the next EOF rather than
        # halting; the prover still drives every preceding step.
        with pytest.raises(EOFError):
            _prove_halt(vm)
        got = vm.output
    else:
        assert _prove_halt(vm), f"examples/boolean/{name}.txt does not reach its halt"
        # A few state-dumping languages deliberately write on the first step
        # after their halt.  That step is otherwise a no-op, so taking it for
        # every VM exactly matches each interpreter's public ``run`` behavior.
        vm.step()
        got = vm.output
    if not BOOLEAN_GENERATED[name].expected_compared:
        # The constructed 123 template pops through location -2 while
        # merging, and a ``2`` there prints whatever the cell holds --
        # junk bytes that are deliberately not the answer, which is the
        # proven halt asserted above.  The retired stored plans happened
        # to have a silent halting row; the construction does not, so the
        # bytes are not compared.
        #
        # Read from the entry rather than matched on the name, so the
        # manifest generated from these entries can say the same thing:
        # rendering ``expected`` for this one advertised "outputs nothing"
        # for a program that prints two bytes.
        return
    assert got == expected
