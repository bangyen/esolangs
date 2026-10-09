"""Typo suggestions and repair previews in CLI errors."""

import pytest

from esolangs._execution import interpreter_module
from esolangs.registry import LANGUAGES, SourceKind
from tests.cli_support import _FakeStdin, call_both
from tests.samples import SAMPLES
from tests.test_language_coupling import REFERENCE


def _offering() -> list[str]:
    """Languages whose interpreter offers ``suggest_corrections``."""
    return [
        name
        for name, lang in LANGUAGES.items()
        if lang.interpreter and hasattr(interpreter_module(name), "suggest_corrections")
    ]


@pytest.mark.parametrize("language", _offering())
def test_previews_neither_execute_nor_edit(language, tmp_path, capsys, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("preview executed or read stdin")

    monkeypatch.setattr(_FakeStdin, "read", forbidden)
    machine = getattr(interpreter_module(language), "_Machine", None)
    if machine is not None:
        monkeypatch.setattr(machine, "step", forbidden)
    path = tmp_path / "program"
    path.write_text(str(SAMPLES[language][0]), encoding="utf-8")
    before = path.read_bytes()
    out, err = call_both(["suggest", language, str(path)], capsys)
    assert not err
    assert "->" not in out
    assert path.read_bytes() == before


_RASTER = next(n for n, x in LANGUAGES.items() if x.source_kind == SourceKind.RASTER)


@pytest.mark.parametrize("language", [REFERENCE, _RASTER])
def test_other_languages_offer_explicit_no_edit_result(language, tmp_path, capsys):
    from PIL import Image

    path = tmp_path / "program"
    if LANGUAGES[language].source_kind == SourceKind.RASTER:
        Image.new("RGB", (1, 1), "white").save(path, format="PNG")
        reason = "raster source has no command spellings"
    else:
        path.write_text("pussh arbitrary identifiers", encoding="utf-8")
        reason = "no safe keyword correction rules"
    before = path.read_bytes()
    out, err = call_both(["suggest", language, str(path)], capsys)
    assert reason in out
    assert "not validated" in out
    assert "->" not in out
    assert not err
    assert path.read_bytes() == before
