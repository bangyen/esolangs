"""Every interpreter spec's ``Errors:`` entry is shown by running a program.

Each language keeps its triggers as ``[[spec_triggers]]`` in
``languages/<id>/tests/cases.toml`` (so they leave with it): a program
(source, hex bytes, or a generated table), stdin, optional dialect settings,
and the exception -- or exact output -- ``esolangs.run`` must produce.
``[spec_untriggerable]`` maps an entry no ``run`` call reaches to the reason.
"""

import ast
import inspect
import pathlib

import pytest

from esolangs import exceptions
from esolangs.registry._describe import interpreter_module
from tests.interpreters.spec_sections import error_entries
from tests.support.spec_triggers import (
    _interpreted,
    all_triggers,
    run_trigger,
    triggers_of,
)

pytestmark = pytest.mark.medium


def _entries(name: str) -> set[str]:
    source = pathlib.Path(inspect.getfile(interpreter_module(name))).read_text()
    return error_entries(ast.get_docstring(ast.parse(source)) or "")


_ALL = all_triggers()


@pytest.mark.parametrize(
    ("name", "trigger"),
    _ALL,
    ids=[f"{name}-{t['expect']}-{i}" for i, (name, t) in enumerate(_ALL)],
)
def test_the_trigger_does_what_the_spec_says(
    name: str, trigger: dict[str, object]
) -> None:
    """The documented exception, or exact output, is what ``run`` gives."""
    if trigger["expect"] == "output":
        assert run_trigger(name, trigger) == trigger["output"]
    else:
        with pytest.raises(getattr(exceptions, str(trigger["expect"]))):
            run_trigger(name, trigger)


def test_every_errors_entry_has_a_trigger() -> None:
    """A new ``Errors:`` line cannot land without a program that shows it."""
    missing = {}
    for name in _interpreted():
        data = triggers_of(name)
        covered = {t["expect"] for t in data["triggers"]}  # type: ignore[attr-defined]
        covered |= set(data.get("untriggerable", {}))  # type: ignore[call-overload]
        if gaps := _entries(name) - covered:
            missing[name] = sorted(gaps)
    assert missing == {}, (
        f"{missing}: give each entry a [[spec_triggers]] program in "
        "languages/<id>/tests/cases.toml, or a reason under [spec_untriggerable]"
    )


def test_untriggerable_entries_are_still_documented() -> None:
    """An exemption leaves with its entry, so it cannot go stale."""
    stale = {
        name: sorted(set(data.get("untriggerable", {})) - _entries(name))  # type: ignore[call-overload]
        for name in _interpreted()
        if (data := triggers_of(name)).get("untriggerable")
    }
    assert {name: found for name, found in stale.items() if found} == {}
