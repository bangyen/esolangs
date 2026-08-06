"""Unit tests for the coverage badge generator script."""

import importlib.util
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "make_coverage_badge.py"


def load_script() -> object:
    spec = importlib.util.spec_from_file_location("make_coverage_badge", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def badge_module() -> object:
    return load_script()


def write_xml(rate: str, path: Path) -> None:
    ET.ElementTree(ET.Element("coverage", {"line-rate": rate})).write(path)


class TestBadgeScript:
    def test_make_badge_contains_percent(self, badge_module: object) -> None:
        svg = badge_module.make_badge(100.0)  # type: ignore[attr-defined]
        assert "100%" in svg

    def test_color_for_thresholds(self, badge_module: object) -> None:
        color_for = badge_module.color_for  # type: ignore[attr-defined]
        assert color_for(96) == "#4c1"
        assert color_for(90) == "#dfb317"
        assert color_for(80) == "#fe7d37"
        assert color_for(50) == "#e05d44"

    def test_main_writes_badge(
        self, badge_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        xml_path = tmp_path / "coverage.xml"
        write_xml("0.5", xml_path)
        out_path = tmp_path / "out.svg"
        monkeypatch.setattr(
            sys, "argv", ["make_coverage_badge.py", str(xml_path), str(out_path)]
        )
        badge_module.main()  # type: ignore[attr-defined]
        assert "50%" in out_path.read_text()

    def test_script_runs_via_cli(self, tmp_path: Path) -> None:
        xml_path = tmp_path / "coverage.xml"
        write_xml("1.0", xml_path)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(xml_path), str(tmp_path / "b.svg")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "100% coverage" in result.stdout
