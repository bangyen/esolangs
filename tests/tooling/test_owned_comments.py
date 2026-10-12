"""Comment ownership cannot delete executable text or string contents."""

from pathlib import Path

import pytest

from scripts.removal_mentions import drop_owned_comments


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
    from scripts.removal_mentions import mention_edit

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
    from scripts.removal_mentions import mention_edit

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
    from scripts import remove_language

    monkeypatch.setattr(remove_language, "ROOT", tmp_path)
    proofs = tmp_path / "docs/proofs"
    proofs.mkdir(parents=True)
    for name in ("index.md", "private.md", "shared.md"):
        (proofs / name).write_text("Proof evidence.\n")
    manifest = tmp_path / "src/esolangs/proof_status.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '[[ledger]]\ngenerator="Tiny"\nevidence="docs/proofs/private.md#bound"\n'
        '[[audit]]\ngenerator="Tiny"\nevidence="docs/proofs/index.md#bound"\n'
        '[[ledger]]\ngenerator="Tiny"\nevidence="docs/proofs/shared.md"\n'
        '[[ledger]]\ngenerator="Other"\nevidence="docs/proofs/shared.md"\n'
    )
    assert remove_language._owned_evidence("Tiny") == {proofs / "private.md"}  # noqa: SLF001
    assert remove_language._owned_evidence("Other") == set()  # noqa: SLF001
