"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.qoibl.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.qoibl.generator import _balance as _balance
    from esolangs.languages.qoibl.generator import _qoibl as _qoibl
    from esolangs.languages.qoibl.generator import _qoibl_enc as _qoibl_enc
    from esolangs.languages.qoibl.generator import qoibl as qoibl

_implementation = importlib.import_module("esolangs.languages.qoibl.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".balance"] = importlib.import_module(
    "esolangs.languages.qoibl.generator.balance"
)
