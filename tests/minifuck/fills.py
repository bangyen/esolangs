"""Fill Minifuck's positional and state-accumulator templates."""

from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.tools.minifuck import minifuck_setters


def fill(template: str, bits: list[int]) -> str:
    return fill_runs(
        template, TEMPLATE_CHAR, minifuck_setters(template, len(bits)), bits
    )
