"""An input source with no cursor, for snapshot-progress regressions."""

from esolangs.interpreters.io import IO, ScriptedIO


class CursorlessIO(IO):
    """Reads ``text`` once, then EOF; ``position()`` stays 0 and output is dropped."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._lines = [text]

    def _read(self, _prompt: str) -> str:
        if not self._lines:
            raise EOFError
        return self._lines.pop()

    def _write(self, value: object) -> None:
        pass

    @property
    def exhausted(self) -> bool:
        """Whether every character has been read."""
        return not self._lines and not self._pending


class PositionlessIO(ScriptedIO):
    """Scripted input whose ``position()`` stays 0, as a port with no cursor."""

    def position(self) -> int:
        return 0
