"""The %^2^-1 template's shape: the header and the runs.

A template is a header naming every input's two branches, a blank line, and
the body with one run of the template character per input.
"""

from collections.abc import Sequence

from esolangs.tools.helpers import TEMPLATE_CHAR
from esolangs.tools.pct_codes import _HEADER_END


def _header(setters: Sequence[tuple[str, str]]) -> str:
    """Spell the header naming every setter's two branches, and its end."""
    header = ";".join(f"{k}={zero}|{one}" for k, (zero, one) in enumerate(setters))
    return header + _HEADER_END


def _run(setter: tuple[str, str]) -> str:
    """Spell one input as its run: the template character, one per branch cell."""
    zero, _one = setter
    return TEMPLATE_CHAR * len(zero)


def _runs(setters: Sequence[tuple[str, str]]) -> str:
    """Spell every input's run in name order, with no separator between."""
    return "".join(_run(setter) for setter in setters)
