"""Comment ownership cannot delete executable text or string contents."""

from pathlib import Path

import pytest

from scripts.removal.mentions import drop_owned_comments


def test_cohort_removal_preserves_code_and_unowned_comments(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text(
        '# language-owners: ["Tiny", "Other"]\n'
        "# Tiny took 3s; Other took 4s.\n"
        "answer = 42  # Tiny remains executable context.\n"
        "\n# Independent invariant.\n"
        'text = """\n# language-owners: ["Tiny"]\n# Literal data.\n"""\n'
    )
    assert drop_owned_comments(path, "Absent") == 0
    assert drop_owned_comments(path, "Tiny") == 2
    assert path.read_text().startswith(
        "answer = 42  # Tiny remains executable context."
    )
    assert "# Independent invariant." in path.read_text()
    assert "# Literal data." in path.read_text()
    assert drop_owned_comments(path, "Other") == 0


@pytest.mark.parametrize("owners", ["[]", '"Tiny"', "[42]"])
def test_invalid_comment_ownership_aborts(tmp_path: Path, owners: str) -> None:
    path = tmp_path / "sample.py"
    source = f"# language-owners: {owners}\n# Evidence.\nanswer = 42\n"
    path.write_text(source)
    with pytest.raises(ValueError, match="invalid comment owners"):
        drop_owned_comments(path, "Tiny")
    assert path.read_text() == source


def test_library_binding_does_not_hide_language_calls(tmp_path: Path) -> None:
    from scripts.removal.mentions import mention_edit

    path = tmp_path / "sample.py"
    name = "Sequence"
    path.write_text(
        f"from collections.abc import {name}\n"
        f"value: {name}[str]\n"
        f'esolangs.run("{name}", {name}())\n'
    )
    assert mention_edit(tmp_path, "sample.py:1:import", name).startswith("identifier")
    assert mention_edit(tmp_path, "sample.py:2:annotation", name).startswith(
        "identifier"
    )
    assert mention_edit(tmp_path, "sample.py:3:call", name).startswith("code")


def test_adjacent_declarations_keep_the_other_cohort(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text(
        '# language-owners: ["Tiny"]\n# First cohort.\n'
        '# language-owners: ["Other"]\n# Second cohort.\nanswer = 42\n'
    )
    assert drop_owned_comments(path, "Tiny") == 2
    assert path.read_text().startswith('# language-owners: ["Other"]')


def test_arithmetic_literal_keeps_real_language_calls_visible(tmp_path: Path) -> None:
    from scripts.removal.mentions import mention_edit

    name = "3" + "x"
    path = tmp_path / "sample.py"
    path.write_text(f'source = "f(x)={name}^2+1"\nesolangs.run("{name}", source)\n')
    assert mention_edit(tmp_path, "sample.py:1:coefficient", name).startswith(
        "identifier"
    )
    assert mention_edit(tmp_path, "sample.py:2:call", name).startswith("code")


def test_proof_ownership_preserves_shared_index_and_evidence(
    tmp_path, monkeypatch
) -> None:
    from scripts.removal import language as remove_language

    monkeypatch.setattr(remove_language, "ROOT", tmp_path)
    proofs = tmp_path / "docs/proofs"
    proofs.mkdir(parents=True)
    for name in ("index.md", "private.md", "shared.md"):
        (proofs / name).write_text("Proof evidence.\n")
    packages = tmp_path / "src/esolangs/languages"
    ledger = (
        "[proof_status]\n"
        'labels = ["tree"]\nqualification = "q"\nscaling = "linear: s"\n'
        'execution = "linear: e"\nworkspace = "linear: w"\n'
        'evidence = "{evidence}"\n'
    )
    audit = (
        "[proof_status.audit]\n"
        'totality = "Total"\ngeneration_time = "Linear"\n'
        'output_size = "Linear"\nevidence = "{evidence}"\n'
    )
    for slug, sections in (
        (
            "tiny",
            ledger.format(evidence="docs/proofs/private.md#bound")
            + "\n"
            + audit.format(evidence="docs/proofs/index.md#bound"),
        ),
        ("other", ledger.format(evidence="docs/proofs/shared.md")),
        ("third", audit.format(evidence="docs/proofs/shared.md")),
    ):
        package = packages / slug
        package.mkdir(parents=True)
        (package / "language.toml").write_text(sections)
    assert remove_language._owned_evidence("Tiny") == {proofs / "private.md"}  # noqa: SLF001
    assert remove_language._owned_evidence("Other") == set()  # noqa: SLF001
