"""Container through the shared API, CLI and machinery."""

import io
from typing import Any

import pytest

import esolangs
from tests.reference import REFERENCE


@pytest.mark.parametrize("container", ["bytes", "stream"])
@pytest.mark.parametrize("mode", ["normal", "steps", "isolated"])
def test_invalid_utf8_input_is_an_argument_error(container: str, mode: str) -> None:
    argument = b"\xff" if container == "bytes" else io.BytesIO(b"\xff")
    bounds: dict[str, Any] = {}
    if mode == "steps":
        bounds["max_steps"] = 100
    elif mode == "isolated":
        bounds["isolated"] = True
    with pytest.raises(esolangs.ArgumentError, match="cannot read stdin"):
        esolangs.run(REFERENCE, ",.", stdin=argument, **bounds)
