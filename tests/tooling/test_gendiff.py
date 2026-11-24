"""The generator diff: silent on an unchanged tree, loud on a mutant."""

import importlib
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from esolangs.registry import LANGUAGES
from tests.support.reference import REFERENCE
from tests.tooling.script_support import REPO_ROOT, load

gendiff = load(REPO_ROOT / "scripts" / "gendiff.py")

#: The two-input change lies outside the exhaustive corpus used below.
_FUNCTION = LANGUAGES[REFERENCE].backend.generate.__name__
_MUTATION = f"""
_unmutated = {_FUNCTION}

def {_FUNCTION}(request):
    source = _unmutated(request)
    return "+" + source if len(request.table) == 4 else source
"""


def test_outputs_cover_every_request_and_repeat() -> None:
    first = gendiff.outputs(REFERENCE, 2)
    # Tables through n=2 (4 + 16), each at six options.
    assert len(first) == 20 * 6
    assert gendiff.outputs(REFERENCE, 2) == first


def test_differences_include_a_missing_request() -> None:
    assert gendiff.differences({"a": "x", "b": "y"}, {"a": "x"}) == ["b"]


def test_construction_layouts_extend_exhaustive_requests(monkeypatch) -> None:
    from docs import evidence

    witness = evidence.TableWitness(3, "parity")
    default = evidence.ConstructionBoundary((witness,), benchmark=False, test=None)
    narrow = replace(default, width=1)
    records = {
        "default": default,
        "balanced": replace(default, balance=True),
        "narrow": narrow,
        "duplicate": narrow,
    }
    monkeypatch.setattr(evidence, "construction_records", lambda _: records)
    cases = gendiff._construction_tables(REFERENCE, 3)
    assert list(gendiff._requests(0, cases)) == [
        ("balanced n=3 parity", "01101001", {"balance": True}),
        ("narrow n=3 parity", "01101001", {"width": 1}),
    ]


@pytest.mark.parametrize(
    ("arity", "count"),
    [(4, "131,704"), (5, "8,590,066,296"), (100000, "at least 8,590,066,296")],
)
def test_exhaustive_price_is_checked_before_checkout(monkeypatch, capsys, arity, count):
    monkeypatch.setattr(gendiff, "_checkout", lambda *_: pytest.fail("checkout"))
    with pytest.raises(SystemExit) as caught:
        gendiff.main([REFERENCE, "--max-n", str(arity)])
    assert caught.value.code == 2
    diagnostic = capsys.readouterr().err
    assert f"{count} exhaustive requests per pass" in diagnostic
    assert "Use named construction witnesses" in diagnostic


def test_matching_errors_without_a_program_fail(monkeypatch, capsys) -> None:
    monkeypatch.setattr(gendiff, "_checkout", lambda *_: REPO_ROOT / "src")
    monkeypatch.setattr(
        gendiff, "_dump", lambda *_: ({"cap": "GeneratorCapError: cap"}, 0.1)
    )
    assert gendiff.main([REFERENCE]) == 1
    captured = capsys.readouterr()
    assert "0 differ" in captured.out
    assert "no matching successful generation pairs" in captured.err


def test_missing_baseline_fails_before_generator_witnesses(monkeypatch, capsys):
    monkeypatch.setattr(
        gendiff, "_construction_tables", lambda *_: pytest.fail("corpus")
    )
    with pytest.raises(SystemExit) as caught:
        gendiff.main([REFERENCE, "--old", "nosuch-generator-baseline"])
    assert caught.value.code == 2
    assert (
        "--old 'nosuch-generator-baseline' does not resolve" in capsys.readouterr().err
    )


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ([], "--mutant-target requires --mutant"),
        (["--mutant", "mutant.py"], "one of its package files"),
    ],
)
def test_bad_mutant_target_fails_before_generation(
    monkeypatch, capsys, options, message
):
    monkeypatch.setattr(gendiff, "_checkout", lambda *_: pytest.fail("checkout"))
    with pytest.raises(SystemExit) as caught:
        gendiff.main(
            [REFERENCE, "--mutant-target", "src/esolangs/__init__.py", *options]
        )
    assert caught.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("new_generation", "status", "change"),
    [(0.90, 0, "-10%"), (1.0, 0, "+0%"), (1.10, 0, "+10%"), (1.11, 1, "+11%")],
)
def test_speed_gate_uses_only_generation(
    monkeypatch, capsys, new_generation, status, change
):
    old = REPO_ROOT / "old"
    monkeypatch.setattr(gendiff, "_checkout", lambda *_: old)

    def dump(source, *_):
        timing = (
            gendiff.Timings(1.0, 1.0)
            if source == old
            else gendiff.Timings(new_generation, 3.0)
        )
        return {"request": "{}"}, timing

    monkeypatch.setattr(gendiff, "_dump", dump)
    monkeypatch.setattr(gendiff, "_construction_tables", lambda *_: {})
    assert gendiff.main([REFERENCE, "--speed"]) == status
    output = capsys.readouterr().out
    assert "632 generation requests per pass, up to 3,792 across 6 passes" in output
    assert f"speed: generation 1.000s -> {new_generation:.3f}s ({change})" in output
    assert "serialization: 1.000s -> 3.000s" in output


@pytest.mark.parametrize("changes_on", [2, 3, 4])
def test_speed_stops_on_any_output_change(monkeypatch, capsys, changes_on) -> None:
    old = REPO_ROOT / "old"
    monkeypatch.setattr(gendiff, "_checkout", lambda *_: old)
    monkeypatch.setattr(gendiff, "_construction_tables", lambda *_: {})
    visited = []

    def dump(source, *_):
        visited.append(source)
        artifact = '{"different": true}' if len(visited) == changes_on else "{}"
        return {"same": "{}", "changed": artifact}, gendiff.Timings(1.0, 0.0)

    monkeypatch.setattr(gendiff, "_dump", dump)
    assert gendiff.main([REFERENCE, "--max-n", "1", "--speed"]) == 1
    assert visited == [old, REPO_ROOT / "src", old, REPO_ROOT / "src"][:changes_on]
    captured = capsys.readouterr()
    assert "speed: generation" not in captured.out
    if changes_on == 2:
        assert "DIFF changed" in captured.out
    else:
        assert "generation changed on timing pass 2: changed" in captured.err


@pytest.mark.medium  # three generator processes and a copy of src: ~3 s
def test_an_unchanged_tree_matches_and_boundary_witnesses_catch_a_mutant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def snapshot(ref: str, scratch: Path) -> Path:
        assert ref == "snapshot"
        # Generator optimizations legitimately differ from HEAD before commit.
        return shutil.copytree(
            REPO_ROOT / "src",
            scratch / "src",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    monkeypatch.setattr(gendiff, "_checkout", snapshot)
    module = importlib.import_module(LANGUAGES[REFERENCE].backend.generate.__module__)
    mutant = tmp_path / "mutant.py"
    mutant.write_text(Path(module.__file__ or "").read_text() + _MUTATION)
    argv = [REFERENCE, "--old", "snapshot", "--max-n", "1", "--mutant", str(mutant)]
    assert gendiff.main(argv) == 0
    out = capsys.readouterr().out
    assert "0 differ from snapshot" in out
    assert "additional construction witnesses: 2" in out.splitlines()
    assert "control: mutant differs on 2" in out.splitlines()
