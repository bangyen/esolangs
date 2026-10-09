"""Run every committed example program and check its output."""

import sys
from pathlib import Path

import pytest

import esolangs
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, canonical_id
from esolangs.tools.examples import BOOLEAN_EXAMPLES as BOOLEAN_GENERATED
from esolangs.vm import (
    _FramedMachine,
    _TapeMachine,
    make_vm,
    run_until_halt_or_ancestor,
    run_until_halt_or_cycle,
    run_until_halt_or_growth,
)
from tests.generator_support import CHECK
from tests.pick import first

BASE_DIR = Path(__file__).parents[2]


# The VM registry is keyed by the language's display name, while boolean
# examples are keyed by their filesystem stem.  The interpreter module is
# shared metadata and uniquely identifies the registered display name.
VM_LANGUAGE = {
    lang.interpreter: lang.name
    for lang in LANGUAGES.values()
    if lang.interpreter is not None
}


# Boolean examples whose answer is their *termination* rather than their
# output: each halts for a 0 and loops forever for a 1, so the committed
# program must be the halting branch.
#
# :func:`test_boolean_example` runs a committed program to completion with no
# step cap, which is right for every other language and fatal for these
# two: a file holding the looping branch does not fail, it hangs the
# suite with no diagnostic.  Nothing about the entry forces the halting row
# -- ``bits`` is just data, and a wrong one regenerates a looping file --
# so :func:`test_halt_convention_examples_halt` checks the committed
# program terminates *before* anything runs it unbounded.
HALT_CONVENTION = {
    stem
    for stem in BOOLEAN_GENERATED
    if esolangs.describe(canonical_id(stem.replace("-", " ")))["answer_mode"]
    == "termination"
}

# The command every staleness message names.
REGENERATE = "`uv run python scripts/generate.py examples`"


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(name, marks=pytest.mark.medium)
        if name in {"circuit-diagram", "vandevelo"}
        else name
        for name in sorted(BOOLEAN_GENERATED)
    ],
)
def test_boolean_example_matches_generator(name: str) -> None:
    """Each committed boolean program is what its generator produces today."""
    example = BOOLEAN_GENERATED[name]
    path = BASE_DIR / "examples" / example.filename
    program = example.build(balance=True)
    stale = f"{path.relative_to(BASE_DIR)} is stale; run {REGENERATE}"
    if isinstance(program, Raster):
        # PNG compression differs across platforms; the pixels are the program.
        assert Raster.from_png(path.read_bytes()) == program, stale
    else:
        expected = (program.rstrip("\n") + "\n").encode("utf-8")
        assert path.read_bytes() == expected, stale


@pytest.mark.medium
def test_regeneration_yields_public_balanced_programs() -> None:
    import esolangs
    from scripts.generate_examples import boolean_programs

    programs = dict(boolean_programs())
    assert programs.keys() == BOOLEAN_GENERATED.keys()
    for stem, example in BOOLEAN_GENERATED.items():
        language = canonical_id(stem.replace("-", " "))
        expected = esolangs.generate(
            language, example.table, balance=True, scale=example.scale
        )
        if example.fill is not None:
            expected = esolangs.instantiate(language, expected, example.bits)
        assert programs[stem] == expected, stem


def test_the_manifest_matches_what_the_script_would_write() -> None:
    """The committed table is what ``generate.py examples`` produces today."""
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    from scripts.generate_examples import boolean_manifest_text

    path = BASE_DIR / "examples" / "MANIFEST.md"
    assert path.read_text(encoding="utf-8") == boolean_manifest_text(), (
        f"examples/MANIFEST.md is stale; run {REGENERATE}"
    )


def test_boolean_examples_cover_every_committed_file() -> None:
    """Every file in examples is accounted for, and vice versa."""
    on_disk = {
        p.name
        for p in (BASE_DIR / "examples").iterdir()
        if p.suffix in (".txt", ".png")
    }
    expected = {example.filename for example in BOOLEAN_GENERATED.values()}
    unregistered = sorted(on_disk - expected)
    assert not unregistered, (
        f"examples/ holds {unregistered} with no BooleanExample; delete them "
        "or register them in src/esolangs/tools/examples.py"
    )
    missing = sorted(expected - on_disk)
    assert not missing, f"examples/ lacks {missing}; run {REGENERATE}"


@pytest.mark.parametrize("name", sorted(HALT_CONVENTION))
def test_halt_convention_examples_halt(name: str) -> None:
    """The committed program of a halt-convention language terminates."""
    program = (
        (BASE_DIR / "examples" / f"{name}.txt").read_text(encoding="utf-8").rstrip("\n")
    )
    assert _halts(name, program, list(BOOLEAN_GENERATED[name].inputs)), (
        f"examples/{name}.txt holds the looping branch; the committed "
        f"program must be the halting one or the suite hangs running it"
    )


def _halts(name: str, program: str, _inputs: list[str]) -> bool:
    """Whether ``name``'s committed program terminates, by cycle detection."""
    language = canonical_id(name.replace("-", " "))
    stdin = BOOLEAN_GENERATED[name].stdin
    return run_until_halt_or_cycle(make_vm(language, program, stdin=stdin))


def test_every_boolean_generator_has_an_example() -> None:
    """Every registered boolean generator has a committed example."""
    registered = {lang.id for lang in LANGUAGES.values() if lang.boolean}
    covered = {canonical_id(stem.replace("-", " ")) for stem in BOOLEAN_GENERATED}
    missing = sorted(registered - covered)
    assert not missing, f"no committed example for {missing}; {CHECK}"


# The boolean examples demonstrate a language's boolean-function capability
# that is not an I/O truth machine (see the limitations ledger).  They are derived
# from ``esolangs.tools.examples``, which records for each committed
# program the generator, truth table, and input combination that produced it
# -- so the files stay in sync with the generators.
#
# The input-reading languages take their bits on stdin; the parameterized
# ones have the bits embedded
# in the program text and read no input.  The halt-convention languages have
# no output at all: their result is the halt-vs-loop convention, so only the
# terminating (`0`) branch is committed -- the `1` branch loops forever by
# definition and is not executed.
BOOLEAN_EXAMPLES = {
    stem: (ex.interpreter, list(ex.inputs), ex.expected, ex.split, dict(ex.kwargs))
    for stem, ex in BOOLEAN_GENERATED.items()
}


def _prove_halt(vm: object) -> bool:
    """Drive ``vm`` to its halt with the prover its machine supports."""
    machine = getattr(vm, "_machine", vm)
    if isinstance(machine, _FramedMachine):
        return run_until_halt_or_ancestor(vm)
    if isinstance(machine, _TapeMachine):
        return run_until_halt_or_growth(vm)
    return run_until_halt_or_cycle(vm)


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
@pytest.mark.medium
def test_boolean_example(name: str) -> None:
    _module, _inputs, expected, _splitlines, _kwargs = BOOLEAN_EXAMPLES[name]
    path = BASE_DIR / "examples" / BOOLEAN_GENERATED[name].filename
    stdin = BOOLEAN_GENERATED[name].stdin
    program = (
        Raster.from_png(path.read_bytes())
        if path.suffix == ".png"
        else path.read_text(encoding="utf-8").rstrip("\n")
    )
    if isinstance(program, Raster):
        got = esolangs.run(name, program, stdin=stdin)
    else:
        vm = make_vm(VM_LANGUAGE[_module], program, stdin=stdin)
    if name == "a-painter-ant":
        # Its implicit loop has no halting state: a repeated snapshot is its
        # language-defined stop.  The public interpreter renders only at a
        # pass boundary, so finish this already-proven periodic pass first.
        assert not run_until_halt_or_cycle(vm)
        while vm.ip != 0:
            vm.step()
        got = vm._machine.render()  # type: ignore[attr-defined]  # noqa: SLF001
    elif isinstance(program, str):
        # Suffolk used to need a branch here: its reading programs stopped
        # on an escaping ``EOFError`` rather than halting, so the prover had
        # to be wrapped in ``pytest.raises``.  The exhausted read is a halt
        # now -- which is what ``run`` always treated it as -- so it takes
        # the common path and the branch is gone.
        assert _prove_halt(vm), f"examples/{name}.txt does not reach its halt"
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


class TestTheWritersWriteWhatTheBuildersBuild:
    """The side-effecting half of ``generate_examples``."""

    @staticmethod
    def _redirect(monkeypatch: pytest.MonkeyPatch, target: Path) -> object:
        from scripts import generate_examples

        monkeypatch.setattr(generate_examples, "EXAMPLES", target)
        return generate_examples

    def test_a_second_write_reports_unchanged(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        module = self._redirect(monkeypatch, tmp_path / "examples")
        monkeypatch.setitem(module.SETS, "boolean", lambda: iter([("sample", "x")]))  # type: ignore[attr-defined]
        module.write_set("boolean")  # type: ignore[attr-defined]
        capsys.readouterr()
        module.write_set("boolean")  # type: ignore[attr-defined]

        lines = capsys.readouterr().out.splitlines()
        assert lines
        assert all(line.startswith("unchanged") for line in lines if ".txt" in line)

    def test_a_png_with_the_same_pixels_is_left_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Another zlib's bytes for the same pixels are not a change."""
        from PIL import Image

        module = self._redirect(monkeypatch, tmp_path / "examples")
        painted = esolangs.describe(first(source_kind="raster", boolean_generator=True))
        stem = next(
            stem
            for stem in BOOLEAN_GENERATED
            if canonical_id(stem.replace("-", " ")) == painted["id"]
        )
        raster = Raster.from_png(BOOLEAN_GENERATED[stem].build(balance=True).to_png())
        monkeypatch.setitem(module.SETS, "boolean", lambda: iter([("img", raster)]))  # type: ignore[attr-defined]
        module.write_set("boolean")  # type: ignore[attr-defined]
        path = tmp_path / "examples" / "img.png"
        Image.open(path).save(path, compress_level=1)
        recompressed = path.read_bytes()
        module.write_set("boolean")  # type: ignore[attr-defined]
        assert path.read_bytes() == recompressed

    def test_main_with_no_arguments_writes_every_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = self._redirect(monkeypatch, tmp_path / "examples")
        written: list[str] = []
        monkeypatch.setattr(module, "write_set", written.append)
        monkeypatch.setattr(sys, "argv", ["generate.py"])
        assert module.main() == 0  # type: ignore[attr-defined]
        assert written == list(module.SETS)  # type: ignore[attr-defined]


def test_an_unknown_interpreter_names_the_file_to_fix() -> None:
    from esolangs.tools.examples import _contract_for

    with pytest.raises(LookupError, match=r"src/esolangs/tools/examples\.py"):
        _contract_for("tape_based.no_such_module")
