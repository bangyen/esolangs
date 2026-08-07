"""Public API for the esolangs package.

Provides ``generate`` (produce a program that prints a text), ``run``
(execute a program through an interpreter), and ``list_languages``.
"""

import importlib
import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.tools import generate as _generate

# Display name -> generator function.
GENERATORS = dict(_generate._GENERATORS)

# Display name -> (interpreter module under esolangs.interpreters, split
# the program into lines first, extra run() keyword arguments).
RUNNERS = {
    "6-5": ("tape_based.6-5", False, {}),
    "ASCII art": ("tape_based.ascii-art", False, {}),
    "Back": ("tape_based.back", True, {}),
    "BFStack": ("stack_based.bfstack", False, {}),
    "BIO": ("register_based.bio", False, {}),
    "BitDeque": ("other.bitdeque", False, {}),
    "BrainIf": ("tape_based.brainif", True, {}),
    "CircleFuck": ("tape_based.circlefuck", False, {}),
    "Clockwise": ("other.clockwise", True, {}),
    "Container": ("other.container", True, {}),
    "Dig": ("register_based.dig", True, {}),
    "Dotlang": ("register_based.dotlang", True, {}),
    "DSDLAI": ("register_based.dsdlai", True, {}),
    "Eval": ("stack_based.eval", False, {}),
    "EXCON": ("tape_based.excon", False, {}),
    "huf": ("register_based.huf", False, {}),
    "Keys": ("other.keys", True, {}),
    "Lightlang": ("register_based.lightlang", False, {}),
    "MAMMALIAN": ("tape_based.mammalian", False, {}),
    "Minifuck": ("tape_based.minifuck", False, {}),
    "Minsky Swap": ("register_based.minsky-swap", False, {}),
    "Modulous": ("stack_based.modulous", False, {}),
    "Movesum": ("register_based.movesum", True, {}),
    "Nevermind": ("other.nevermind", True, {}),
    "Polynomial": ("register_based.polynomial", False, {}),
    "Qoibl": ("register_based.qoibl", True, {}),
    "RAM0": ("register_based.RAM0", False, {}),
    "Sophie": ("register_based.sophie", False, {}),
    "Suffolk": ("tape_based.suffolk", False, {"limit": 1}),
    "Temporary": ("stack_based.temporary", False, {}),
    "WII2D": ("register_based.WII2D", True, {}),
    "ZTOALC": ("other.ztoalc", True, {}),
}

# Languages with a generator but no in-repo interpreter (extra/ or a
# compiler provides the executable).
_NO_INTERPRETER = {
    "123",
    "Forþ",
    "Home Row",
    "LaserFuck",
    "Magnitude",
    "NoComment",
    "Painfuck",
    "Unsquare",
}


def generate(language: str, text: str) -> str:
    """Return a program in ``language`` that prints ``text``."""
    try:
        fn = GENERATORS[language]
    except KeyError:
        raise ValueError(f"unknown language: {language}") from None
    return str(fn(text))


def run(language: str, program: str, stdin: str = "") -> str:
    """Execute ``program`` and return its output.

    Input is fed to the program line by line from ``stdin``.
    """
    try:
        module, split, kwargs = RUNNERS[language]
    except KeyError:
        raise ValueError(f"unknown language: {language}") from None
    run_fn = importlib.import_module("esolangs.interpreters." + module).run
    lines = iter(stdin.splitlines())

    def read_input(prompt: str = "") -> str:
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    buffer = io.StringIO()
    with patch("builtins.input", read_input):
        with redirect_stdout(buffer):
            run_fn(program.splitlines() if split else program, **kwargs)
    return buffer.getvalue()


def list_languages() -> list:
    """Return the supported language names, sorted."""
    return sorted(set(GENERATORS) | set(RUNNERS))
