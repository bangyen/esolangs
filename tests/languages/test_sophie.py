"""Sophie through the shared API, CLI and machinery."""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import vm
from tests.cli.test_cli import run_cli


# Every test here spawns `python -m esolangs.cli`; 2.8s over nine tests.
@pytest.mark.medium
class TestSubprocess:
    def test_run(self, tmp_path: Path) -> None:
        program = tmp_path / "prog.soph"
        program.write_text(esolangs.generate("Sophie", "0110"))
        result = run_cli("run", "Sophie", str(program), stdin="01")
        assert result.returncode == 0
        assert result.stdout == "1"


class TestPackageEntryPoint:
    """python -m esolangs dispatches to the CLI via esolangs/__main__.py."""

    def test_run_as_main(self, capsys: pytest.CaptureFixture[str]) -> None:
        import runpy

        with patch.object(sys, "argv", ["esolangs", "generate", "Sophie", "0110"]):
            runpy.run_module("esolangs", run_name="__main__")
        out = capsys.readouterr().out
        assert esolangs.run("Sophie", out, stdin="01") == "1"


@pytest.mark.medium
@pytest.mark.parametrize(
    ("detector", "hint"),
    [
        ("run_until_halt_or_all_branches_cycle", "branching_successors"),
        ("run_until_halt_or_ancestor", "frame_entry_key"),
        ("run_until_halt_or_growth", "rightward-growing tape"),
        ("run_until_halt_or_value_growth", "unbounded affine values"),
    ],
)
def test_unsupported_detectors_name_the_needed_capability(detector, hint):
    with pytest.raises(TypeError) as caught:
        getattr(vm, detector)(vm.make_vm("Sophie", ""))
    assert type(caught.value) is TypeError
    assert str(caught.value).startswith("Sophie is not ")
    assert hint in caught.value.__notes__[0]


class TestWidthEffectSaysWhatWidthDoes:
    """One flag, three behaviours, and no way to tell them apart."""

    def test_layout_is_exactly_the_width_aware_generators(self) -> None:
        """The old field is the new field's `layout` case, and only that."""
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            assert (facts["width_effect"] == "layout") == facts["width_aware"], name

    @pytest.mark.slow
    def test_the_declaration_matches_what_width_actually_does(self) -> None:
        """The drift guard: `none` must really be a no-op."""
        wrong = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["boolean_generator"]:
                continue
            plain = esolangs.generate(name, "0110")
            narrow = esolangs.generate(name, "0110", width=20)
            if facts["width_effect"] == "none" and plain != narrow:
                wrong.append(f"{name}: declared none but --width changed it")
            # `wrap` and `layout` may coincide on a program already narrower
            # than the width, so only the `none` direction is decidable here.
        assert not wrong, "\n".join(wrong)

    def test_a_wrapping_language_really_reflows(self) -> None:
        """The positive control for the check above, which only tests `none`."""
        wide = esolangs.generate("Sophie", "0110")
        narrow = esolangs.generate("Sophie", "0110", width=10)
        assert "\n" not in wide
        assert "\n" in narrow
        assert esolangs.describe("Sophie")["width_effect"] == "wrap"


@pytest.mark.medium
def test_worker_thread_loads_unicode_path(tmp_path: Path) -> None:
    source = tmp_path / "λ program.sophie"
    source.write_text("#λ,", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(
            esolangs.run, "Sophie", source, isolated=True, max_output=1
        )
        assert result.result(timeout=10) == "λ"
