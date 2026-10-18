"""The deep-arities tuning lives in each language package's ``language.toml``.

``tests/proofs/deep`` aggregates the files' ``[deep_arities]`` sections
by registry id, skipping a package whose file or section is absent;
these tests pin the accounting (every section belongs to a registered
language, and the aggregate names exactly the packages holding a
section), the skip semantics, and the loader's failure modes.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

from esolangs.registry import LANGUAGES
from tests.proofs.deep import (
    FRAGMENT,
    PACKAGES,
    SECTIONS,
    TABLE,
    aggregate_fragments,
    deep_arities,
)


def _fragment_packages(tmp_path: Path) -> Path:
    """Copy the real language files into a disposable package tree."""
    packages = tmp_path / "languages"
    for source in PACKAGES.glob(f"*/{FRAGMENT}"):
        target = packages / source.parent.name
        target.mkdir(parents=True)
        shutil.copyfile(source, target / FRAGMENT)
    return packages


def test_a_file_without_the_section_is_skipped(tmp_path: Path) -> None:
    """Another dataset's section is not this suite's business."""
    packages = tmp_path / "languages"
    package = packages / "line"
    package.mkdir(parents=True)
    (package / FRAGMENT).write_text("[curation]\nbacklinks = 2\n", encoding="utf-8")
    sections = aggregate_fragments(packages, ["line"])
    assert all(not entries for entries in sections.values())


def test_every_fragment_belongs_to_a_registered_language() -> None:
    registered = {lang.id for lang in LANGUAGES.values()}
    on_disk = {
        path.parent.name
        for path in PACKAGES.glob(f"*/{FRAGMENT}")
        if TABLE in tomllib.loads(path.read_text("utf-8"))
    }
    with_entries = {lid for section in SECTIONS for lid in deep_arities(section)}
    assert on_disk == with_entries
    assert on_disk <= registered


def test_a_duplicate_language_id_fails(tmp_path: Path) -> None:
    packages = _fragment_packages(tmp_path)
    with pytest.raises(ValueError, match="duplicate language id"):
        aggregate_fragments(packages, ["line", "line"])


def test_an_unregistered_packages_fragment_fails(tmp_path: Path) -> None:
    packages = _fragment_packages(tmp_path)
    orphan = packages / "not_a_language"
    orphan.mkdir()
    (orphan / FRAGMENT).write_text("[deep_arities]\nworkspace = 5\n", encoding="utf-8")
    ids = [lang.id for lang in LANGUAGES.values()]
    with pytest.raises(ValueError, match="not registered"):
        aggregate_fragments(packages, ids)


def test_an_unknown_section_fails(tmp_path: Path) -> None:
    packages = _fragment_packages(tmp_path)
    fragment = packages / "line" / FRAGMENT
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(
            "[deep_arities]\n", "[deep_arities]\nbogus = 3\n", 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown section"):
        aggregate_fragments(packages, ["line"])


def test_a_wrongly_typed_value_fails(tmp_path: Path) -> None:
    packages = _fragment_packages(tmp_path)
    fragment = packages / "line" / FRAGMENT
    fragment.write_text('[deep_arities]\nexecution = "six"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="must be an int"):
        aggregate_fragments(packages, ["line"])


def test_a_removed_package_takes_its_entries_with_it(tmp_path: Path) -> None:
    """Simulated removal: deleting one package drops only its entries."""
    packages = _fragment_packages(tmp_path)
    ids = [lang.id for lang in LANGUAGES.values()]
    before = aggregate_fragments(packages, ids)
    # The language holding entries in the most sections is the fullest test.
    victim = max(
        (lid for entries in before.values() for lid in entries),
        key=lambda lid: sum(lid in entries for entries in before.values()),
    )
    shutil.rmtree(packages / victim)
    after = aggregate_fragments(packages, ids)
    for section in SECTIONS:
        expected = {
            lid: value for lid, value in before[section].items() if lid != victim
        }
        assert after[section] == expected
    assert any(victim in entries for entries in before.values())
    assert all(victim not in entries for entries in after.values())
