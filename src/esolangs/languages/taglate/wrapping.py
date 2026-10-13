"""Taglate source wrapping with a structural queue seed."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from esolangs.generation.wrap import wrap_chars


def _taglate(program: str, width: int) -> str:
    """Wrap Taglate's commands, leaving its queue-seed line alone.

    The first line seeds the queue and is structural; the rest is joined
    before tokenizing and breaks anywhere.
    """
    seed, _, commands = program.partition("\n")
    if not commands:
        return program
    return seed + "\n" + wrap_chars(commands.replace("\n", ""), width)


def same_layout(template: str, plain: str, _layout: Callable[[int], Any]) -> bool:
    """Whether the queue seed and command sequence agree."""
    seed, _, commands = template.partition("\n")
    plain_seed, _, plain_commands = plain.partition("\n")
    return seed == plain_seed and commands.replace("\n", "") == plain_commands.replace(
        "\n", ""
    )
