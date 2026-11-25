"""Language-specific execution tests."""

from pathlib import Path

from tests.support.paths import ROOT

FIXTURES = Path(__file__).parent / "fixtures"
SHARED_IMAGES = {
    name: ROOT / "tests/support/fixtures" / name
    for name in ("addition.png", "multiplication_2x.png")
}


def fixture_image(name: str) -> Path:
    """Find a Line image, including the shared codec fixtures."""
    return SHARED_IMAGES.get(name, FIXTURES / name)
