"""Native files and portable JSON for program and template artifacts."""

from esolangs.operations.export import to_file
from esolangs.operations.source import from_file
from esolangs.portable import from_json, to_json

__all__ = ["from_file", "from_json", "to_file", "to_json"]
