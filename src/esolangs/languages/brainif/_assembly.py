"""Assemble BrainIf instructions and resolve zero-width labels."""

from collections.abc import Iterable

from esolangs.generation.helpers import _ASCII_ZERO


def _resolve(lines: list[str]) -> str:
    """Resolve zero-width labels and keep all destinations on real lines."""
    labels: dict[str, int] = {}
    emitted: list[str] = []
    for line in lines:
        if line.startswith("@"):
            labels[line[1:]] = len(emitted) + 1
        else:
            emitted.append(line)
    after = len(emitted) + 1
    needs_landing = False
    for i, line in enumerate(emitted):
        if "goto @" in line:
            head, label = line.split("goto @")
            target = labels[label]
            needs_landing |= target == after
            emitted[i] = f"{head}goto {target}"
    if needs_landing:
        # Exit routes carry a printed ASCII bit or a cleared cell here.
        emitted.append("if 255 increment")
    return "\n".join(emitted)


class _Lines:
    """BrainIf lines under construction, with zero-width label markers."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def mark(self, name: str) -> None:
        """Append the zero-width marker ``@name``."""
        self.lines.append(f"@{name}")

    def add(self, line: str) -> None:
        """Append one instruction line."""
        self.lines.append(line)

    def extend(self, lines: Iterable[str]) -> None:
        """Append instruction lines in order."""
        self.lines.extend(lines)


def _climb() -> list[str]:
    """Return the lines that raise a zero cell to the byte ``'0'``."""
    return [f"if {value} increment" for value in range(_ASCII_ZERO)]
