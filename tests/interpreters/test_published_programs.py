"""Revision-pinned published programs, independent of this repo's generators.

Each ``tests/fixtures/wiki_examples/<language>.json`` holds one wiki page's
examples (CC0): ``{"language", "oldid", "examples": [...]}``.  An example has
an ``id``, its ``source`` (or a ``source_file`` beside the JSON), optional
``stdin``, and the page's stated output as ``expected`` (or ``expected_file``).
Expected values come from the cited page, not local execution.

``stop`` says how the run ends: ``halt`` (default); ``steps`` for a program
that never halts, whose output after ``max_steps`` must start with
``expected``; ``eof`` for one that reads past its input, which these
interpreters refuse rather than invent a value for.  ``decode`` names a
converter from our I/O convention to the page's (bits versus bytes, say).
A halting run is also stepped to completion, unless ``"vm": false``.
"""

import json
from pathlib import Path

import pytest

import esolangs
from esolangs.exceptions import ExecutionTimeoutError, InputExhaustedError
from esolangs.vm import complete_vm, make_vm

_DIR = Path(__file__).parent.parent / "fixtures" / "wiki_examples"


def _bits(text: str, *, lsb_first: bool) -> str:
    """Pack a stream of '0'/'1' output characters into bytes."""
    bits = [c for c in text if c in "01"]
    chunks = ["".join(bits[i : i + 8]) for i in range(0, len(bits) - 7, 8)]
    return "".join(chr(int(c[::-1] if lsb_first else c, 2)) for c in chunks)


_DECODERS = {
    "bits_lsb": lambda out: _bits(out, lsb_first=True),
    "bits_msb": lambda out: _bits(out, lsb_first=False),
}


def _text(page: Path, example: dict, key: str) -> str:
    if f"{key}_file" in example:
        return (page.parent / example[f"{key}_file"]).read_text(encoding="utf-8")
    return example.get(key, "")


def _cases():
    for page in sorted(_DIR.glob("*.json")):
        data = json.loads(page.read_text(encoding="utf-8"))
        for example in data["examples"]:
            yield pytest.param(
                data["language"],
                page,
                example,
                f"https://esolangs.org/w/index.php?oldid={data['oldid']}",
                id=f"{page.stem}-{example['id']}",
            )


@pytest.mark.parametrize(("language", "page", "example", "citation"), _cases())
def test_wiki_examples(language, page, example, citation):
    source = _text(page, example, "source")
    stdin = example.get("stdin", "")
    expected = _text(page, example, "expected")
    stop = example.get("stop", "halt")
    if stop == "halt":
        output = esolangs.run(language, source, stdin, timeout=5)
        if example.get("vm", True):
            vm = make_vm(language, source, stdin)
            assert complete_vm(vm, max_steps=None) == output, "stepping parity"
    else:
        error = {"steps": ExecutionTimeoutError, "eof": InputExhaustedError}[stop]
        with pytest.raises(error) as info:
            esolangs.run(
                language, source, stdin, timeout=5, max_steps=example.get("max_steps")
            )
        output = info.value.partial_output
    output = _DECODERS[example["decode"]](output) if "decode" in example else output
    if stop == "steps":
        assert output.startswith(expected), citation
    else:
        assert output == expected, citation
