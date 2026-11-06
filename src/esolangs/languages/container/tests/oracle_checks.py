"""Simultaneous rule evaluation over a structured network."""

from itertools import product
from operator import ge, le

import pytest

from esolangs.languages.container.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed, stalled
from tests.support.workspace_oracle import missing_workspace, workspace_view


def _source(network):
    lines = []
    for name, (initial, rules) in network.items():
        lines.append(f"{name}={initial}:" if initial else name + ":")
        lines.extend(f"  {delta} {left}{op}{right}" for delta, left, op, right in rules)
    return lines


def _model(network, stdin):
    values = {name: initial for name, (initial, _) in network.items()}
    cursor = 0
    output = ""
    exit_code = None
    trace = []
    for tick in range(9):
        halted = exit_code is not None or not network
        row = (values, exit_code, tick, cursor), halted, output, cursor, cursor
        trace.append(row)
        if halted:
            trace.extend([row] * 3)
            break
        if tick == 8:
            break

        def get(term, values=values):
            return term if isinstance(term, int) else values[term]

        updated = {
            name: max(
                0,
                values[name]
                + sum(
                    delta
                    for delta, left, op, right in rules
                    if (ge if op == ">=" else le)(get(left), get(right))
                ),
            )
            for name, (_, rules) in network.items()
        }
        if values.get("PRINT") == 0 and updated["PRINT"] and "OUT" in updated:
            output += chr(updated["OUT"] % 128)
        if values.get("") == 0 and updated[""]:
            updated["IN"] = ord(stdin[cursor]) if cursor < len(stdin) else 0
            cursor += cursor < len(stdin)
        if updated.get("EXIT") != values.get("EXIT"):
            exit_code = updated["EXIT"]
        values = updated
    return None, trace


def _check(factory, network, stdin):
    expected = _model(network, stdin)

    def state(machine):
        return machine.var, machine.exit_code, machine.tick, machine.state[3]

    assert (
        observed(
            factory,
            _source(network),
            stdin,
            workspace_view(
                expected[1],
                WorkspaceModel(
                    "container-v1",
                    ("variables", "exit_code", "input_cursor", "input_reads"),
                ),
                lambda row: (
                    frozenset(row[0][0].items()),
                    row[0][1],
                    row[-1],
                    row[0][3],
                ),
                state,
            ),
            cap=8,
        )
        == expected
    ), network


def check_raw_container():
    for initial, delta, threshold, stdin in product(
        (0, 1, 130), (-3, 0, 2), (0, 1, 4), ("", "Ω")
    ):
        network = {
            "IN": (0, ()),
            "OUT": (initial, ((delta, "OUT", ">=", threshold), (1, "IN", ">=", "OUT"))),
            "PRINT": (0, ((1, "OUT", ">=", threshold), (-2, "PRINT", ">=", 1))),
            "": (0, ((1, "PRINT", "<=", 0), (-2, "", ">=", 1))),
            "EXIT": (1, ((-1, "OUT", ">=", 133),)),
        }
        _check(_Machine, network, stdin)
    _check(_Machine, {}, "")

    with pytest.raises(AssertionError):
        _check(stalled(_Machine), {"OUT": (0, ((1, "OUT", ">=", 0),))}, "")
    for component in ("variables", "exit_code", "input_cursor", "input_reads"):
        with pytest.raises(AssertionError):
            _check(
                missing_workspace(_Machine, component),
                {"EXIT": (0, ((1, "EXIT", ">=", 0),))},
                "",
            )
