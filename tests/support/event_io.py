"""A ScriptedIO that records each read and write in order."""

from esolangs.runtime.io import ScriptedIO


class EventIO(ScriptedIO):
    """A ``ScriptedIO`` that records each read and write in order."""

    def __init__(self, stdin: str = "") -> None:
        super().__init__(stdin)
        self.events: list[tuple[str, str]] = []

    def print_char(self, char: str) -> None:
        self.events.append(("out", char))
        super().print_char(char)

    def input_char(self, prompt: str = "Input: ") -> int:
        self.events.append(("in", ""))
        return super().input_char(prompt)
