r"""Run every committed example program and check its output."""

import sys
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


# The VM registry is keyed by.
# examples are keyed by their.
# shared metadata and uniquely.
VM_LANGUAGE = {
    lang.interpreter: lang.name
    for lang in LANGUAGES.values()
    if lang.interpreter is not None
}

# container halts by calling.
EXITS = {"container"}

# Boolean examples whose answer.
# output: each halts for a 0.
# program must be the halting.
# .
# :func:`test_boolean_example`.
# step cap, which is right for.
# three: a file holding the.
# suite with no diagnostic.
# -- ``bits`` is just data, and.
# so.
# program terminates *before*.
HALT_CONVENTION = {"123", "arrowqueue", "point-break"}

# Boolean generators.
# id, each for a stated reason.
# answer is recoverable from.
# ``esolangs.tools.boolean.examp.
# report belongs here rather.
# .
# Empty, and that is the claim:.
_NO_EXAMPLE: set[str] = set()


@pytest.mark.parametrize("name", sorted(BOOLEAN_GENERATED))
def test_boolean_example_matches_generator(name: str) -> None:
    r"""Each committed boolean program is what its generator produces today."""
    path = BASE_DIR / "examples" / "boolean" / f"{name}.txt"
    expected = BOOLEAN_GENERATED[name].build().rstrip("\n") + "\n"
    assert path.read_text(encoding="utf-8") == expected


def test_the_manifest_matches_what_the_script_would_write() -> None:
    r"""The committed table is what ``write_examples.py`` produces today."""
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    from write_examples import boolean_manifest_text

    path = BASE_DIR / "examples" / "boolean" / "MANIFEST.md"
    assert path.read_text(encoding="utf-8") == boolean_manifest_text(), (
        "examples/boolean/MANIFEST.md is stale; "
        "run `python scripts/write_examples.py boolean`"
    )


def test_boolean_examples_cover_every_committed_file() -> None:
    r"""Every file in examples/boolean is accounted for, and vice versa."""
    on_disk = {p.stem for p in (BASE_DIR / "examples" / "boolean").glob("*.txt")}
    assert on_disk == set(BOOLEAN_GENERATED) | set(HAND_WRITTEN)


@pytest.mark.parametrize("name", sorted(HALT_CONVENTION))
def test_halt_convention_examples_halt(name: str) -> None:
    r"""The committed program of a halt-convention language terminates."""
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
    r"""Whether ``name``'s committed program terminates, by cycle detection."""
    from esolangs.vm import run_until_halt_or_cycle

    if name == "arrowqueue":
        from esolangs.interpreters.grid_based.arrowqueue import _Machine as AQ

        return run_until_halt_or_cycle(AQ(program.splitlines()))
    if name == "123":
        return one_two_three_result(program) == "0"
    return point_break_result(program, inputs) == "0"


def test_every_boolean_generator_has_an_example() -> None:
    r"""Every registered boolean generator has a committed example."""
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


# The boolean examples.
# that is not an I/O truth.
# from.
# program the generator, truth.
# -- so the files stay in sync.
# .
# The input-reading languages.
# ones (see.
# in the program text and read.
# output at all: their result.
# terminating (`0`) branch is.
# definition and is not.
BOOLEAN_EXAMPLES = {
    stem: (ex.interpreter, list(ex.inputs), ex.expected, ex.split, dict(ex.kwargs))
    for stem, ex in BOOLEAN_GENERATED.items()
} | {
    stem: (interpreter, list(inputs), expected, split, {})
    for stem, (interpreter, inputs, expected, split) in HAND_WRITTEN.items()
}


def _prove_halt(vm: object) -> bool:
    r"""Drive ``vm`` to its halt with the prover its machine supports."""
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
        # Its implicit loop has no.
        # language-defined stop.
        # pass boundary, so finish this.
        assert not run_until_halt_or_cycle(vm)
        while vm.ip != 0:
            vm.step()
        got = vm._machine.render()  # type: ignore[attr-defined]  # noqa: SLF001
    else:
        # Suffolk used to need a branch.
        # on an escaping ``EOFError``.
        # to be wrapped in.
        # now -- which is what ``run``.
        # the common path and the.
        assert _prove_halt(vm), f"examples/boolean/{name}.txt does not reach its halt"
        # A few state-dumping languages.
        # after their halt.
        # every VM exactly matches each.
        vm.step()
        got = vm.output
    if not BOOLEAN_GENERATED[name].expected_compared:
        # The constructed 123 template.
        # merging, and a ``2`` there.
        # junk bytes that are.
        # proven halt asserted above.
        # to have a silent halting row;.
        # bytes are not compared.
        # .
        # Read from the entry rather.
        # manifest generated from these.
        # rendering ``expected`` for.
        # for a program that prints two.
        return
    assert got == expected
