"""Root-only original 256-byte reverse/negation workspace preflight."""

from dataclasses import dataclass
from unittest.mock import patch

from . import accounting_core as core

OWNER = (
    "src/esolangs/languages/forbin/tests/test_forbin.py:"
    "test_forbin_for_loop_halts_without_a_false_cycle"
)


def cases():
    """Retain the original owner source builder and independent byte rule."""
    flip = "flip bit { return !bit; }"
    result = []
    for value in range(256):
        names = "a,b,c,d,e,f,g,h"
        inverted_reverse = ",".join(
            f"(flip {bit})" for bit in reversed(names.split(","))
        )
        source = f"{flip} main {{ {names} = (in 0); out {inverted_reverse}; }}"
        reversed_byte = int(f"{value:08b}"[::-1], 2)
        result.append(
            {
                "name": f"original-byte-{value}",
                "owner": OWNER,
                "value": value,
                "source": source,
                "stdin": chr(value) + "unused",
                "output": chr(255 - reversed_byte),
            }
        )
    return result


def check_prediction(record):
    """Prove the admitted exact-three-step shape before executing native code."""
    _, rows = core.predict(record)
    core.exact(len(rows), 7)
    assert all(row.error is None for row in rows)
    core.exact([row.machine.halted for row in rows], [False] * 3 + [True] * 4)
    core.exact([row.machine.state.reads for row in rows], [0] + [8] * 6)
    core.exact([row.port.position for row in rows], [0] + [1] * 6)
    core.exact([row.port.reads for row in rows], [0] + [1] * 6)
    core.exact([row.port.past_end for row in rows], [0] * 7)
    core.exact([row.port.output for row in rows], [""] * 2 + [record["output"]] * 5)
    assert all(row.machine.state.bits == () for row in rows)
    core.exact([row.machine.state.frames[0].position for row in rows[:3]], [0, 1, 2])
    assert all(row.machine.state.frames == [] for row in rows[3:])
    assert all(row.port.text[row.port.position :] == "unused" for row in rows[1:])
    held = []
    for row in rows:
        parts = row.machine.parts()
        held.append((parts, hash(parts)))
    assert all(hash(parts) == digest for parts, digest in held)
    core.exact(rows[-1].machine.parts(), rows[-4].machine.parts())
    core.exact(rows[-2].machine.parts(), rows[-4].machine.parts())
    core.exact(rows[-3].machine.parts(), rows[-4].machine.parts())
    # This exact finite trajectory is inside the unchanged old terminal cap64;
    # no old owner or helper cap is raised to the general model's safety bound.
    active = sum(not row.machine.halted for row in rows[:-1])
    core.exact(active, 3)
    assert active <= 64


@dataclass
class Observed:
    """Actual passthrough counts; retain machines to prevent host-id recycling."""

    machine: object
    boundaries: int = 0
    active: int = 0
    idle: int = 0


def run(route, context):
    """Execute all old byte inputs with unchanged full workspace/IO observer."""
    assert route in ("raw", "prepare")
    records = cases()
    core.exact(len(records), 256)
    for record in records:
        check_prediction(record)
    original_check = core.check_state
    original_step = context.native._Machine.step
    observed = {}

    def check_state(raw, expected, code, types):
        result = original_check(raw, expected, code, types)
        seen = observed.setdefault(id(raw), Observed(raw))
        assert seen.machine is raw
        seen.boundaries += 1
        return result

    def step(raw):
        before = raw.halted
        result = original_step(raw)
        seen = observed[id(raw)]
        if before:
            seen.idle += 1
        else:
            seen.active += 1
        return result

    with (
        patch.object(core, "check_state", check_state),
        patch.object(context.native._Machine, "step", step),
    ):
        result = core.run(records, route, context)
    core.exact(len(observed), 256)
    core.exact([detail["boundaries"] for detail in result["details"]], [7] * 256)
    for detail in result["details"]:
        core.exact(detail["written"], [True, True, True, False, True])
    actual_outputs = []
    physical_reads = physical_bytes = logical_reads = active = idle = boundaries = 0
    for record, seen in zip(records, observed.values(), strict=True):
        raw = seen.machine
        core.exact((seen.active, seen.idle, seen.boundaries), (3, 3, 7))
        assert raw.halted is True
        core.exact(raw.state.frames, ())
        core.exact(raw.state.bits, ())
        core.exact(raw.state.reads, 8)
        port = raw.io
        core.exact(
            (port.position(), port.progress(), port.reads, port.past_end), (1, 1, 1, 0)
        )
        core.exact(port._source[port.position() :], "unused")
        core.exact(port.getvalue(), record["output"])
        actual_outputs.append(ord(port.getvalue()))
        physical_reads += port.reads
        physical_bytes += port.position()
        logical_reads += raw.state.reads
        active += seen.active
        idle += seen.idle
        boundaries += seen.boundaries
    core.exact(
        (physical_reads, physical_bytes, logical_reads, active, idle, boundaries),
        (256, 256, 2048, 768, 768, 1792),
    )
    expected = [ord(record["output"]) for record in records]
    core.exact(actual_outputs, expected)
    return {
        "route": route,
        "source_cases": 256,
        "boundaries": boundaries,
        "active_steps": active,
        "posthalt_steps": idle,
        "physical_reads": physical_reads,
        "physical_bytes": physical_bytes,
        "logical_bit_reads": logical_reads,
        "outputs_hex": bytes(actual_outputs).hex(),
        "workspace": result,
        "old_terminal_cap": 64,
        "original_owner_same_value_loop_tail": False,
        "all78_owners": False,
        "full_owner_acceptance": False,
        "raw_cycle_wire_verified": False,
        "accounting_closure": False,
    }
