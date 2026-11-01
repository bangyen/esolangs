"""Read all input bytes, then build and print a constant accumulator."""

from .core import _ENTRY, _T_LOW, _build_constants, _main_planner, _prime, _walker
from .digits import _helper_cells
from .isa import _program, _render


def _constant_program(inputs: int, bit: int) -> str:
    """Return straight-line code printing ``bit`` and reading every input."""
    used = set(_T_LOW)
    helper = _helper_cells(used)
    target = _walker(used)(71 if bit else 69)
    main, _ = _main_planner({})
    _build_constants(main, helper)
    _prime(main, helper, (helper["all2"],))
    for _ in range(inputs):
        main.raw("/")
    # Under all-2, crazy maps the fresh 69/71 cell to ASCII 48/49.
    main.op("*", helper["all2"])
    main.op("p", target)
    main.raw("<")
    main.raw("v")
    code = dict.fromkeys(range(_ENTRY), "o") | main.code
    return _render(_program(code), main.c)
