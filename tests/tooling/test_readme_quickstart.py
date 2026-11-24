"""Exercise the published README commands with the checkout's CLI."""

import shutil

import pytest

from scripts.ci.release import _smoke_quickstart


@pytest.mark.skipif(shutil.which("bash") is None, reason="quickstart uses Bash")
def test_readme_quickstart() -> None:
    _smoke_quickstart()
