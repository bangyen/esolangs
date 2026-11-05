"""Runtime capabilities for Deadfish."""

from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Deadfish", RuntimeSpec("deadfish", category="register_based"), id="deadfish"
)
