"""Validate status-specific measurements and differential findings before reuse."""

import base64
import binascii
import math
from typing import Any

RESOURCE_FIELDS = (
    "inputs",
    "source_units",
    "source_utf8_bits",
    "worst_row_commands",
    "peak_memory_cells",
    "peak_stack_items",
    "peak_control_stack_items",
    "peak_data_bits",
    "peak_control_stack_bits",
    "peak_integer_bits",
    "peak_pc_bits",
    "peak_machine_bits",
)
MINIMIZATION = {"started", "complete", "call-limit", "timeout", "failed", "limit"}


def integer(value: object, minimum: int = 0) -> bool:
    """Accept an exact integer above the floor, excluding booleans."""
    return type(value) is int and value >= minimum


def case(value: Any) -> None:
    """Validate original or minimized input and byte-preserving outcomes."""
    if (
        not isinstance(value, dict)
        or any(
            not isinstance(value.get(key), str) for key in ("program", "stdin", "cause")
        )
        or not value["cause"]
    ):
        raise ValueError("invalid counterexample payload")
    for side in ("ours", "ref"):
        outcome = value.get(side)
        if not isinstance(outcome, dict) or any(
            not isinstance(outcome.get(key), str)
            for key in ("status", "output", "detail")
        ):
            raise ValueError("invalid counterexample outcome")
        status = outcome["status"]
        if status not in {"halt", "eof", "error", "limit", "timeout"} and not (
            status.startswith("crash:") and len(status) > 6
        ):
            raise ValueError("invalid counterexample status")
        try:
            base64.b64decode(outcome["output"], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid counterexample output") from exc


def finding(value: Any) -> None:
    """Require bounded replay arguments and same-cause minimization evidence."""
    if (
        not isinstance(value, dict)
        or type(value.get("schema")) is not int
        or value.get("schema") != 1
        or not isinstance(value.get("minimization_status"), str)
        or value.get("minimization_status") not in MINIMIZATION
    ):
        raise ValueError("invalid minimization evidence")
    case(value.get("original"))
    minimized = value.get("minimized")
    if minimized is not None:
        case(minimized)
        if minimized["cause"] != value["original"]["cause"]:
            raise ValueError("minimization changed the cause")
    if value["minimization_status"] == "complete" and minimized is None:
        raise ValueError("completed minimization lacks its case")
    command = value.get("replay")
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(argument, str) for argument in command)
    ):
        raise ValueError("invalid replay command")
    for flag in (
        "--ref-timeout",
        "--budget-seconds",
        "--setup-seconds",
        "--finalize-seconds",
    ):
        if command.count(flag) != 1:
            raise ValueError("replay lacks a bounded deadline")
        index = command.index(flag) + 1
        try:
            bound = float(command[index])
        except (IndexError, ValueError) as exc:
            raise ValueError("invalid replay deadline") from exc
        if not math.isfinite(bound) or bound <= 0:
            raise ValueError("invalid replay deadline")


def validate(record: dict[str, Any]) -> None:
    """Require the fields that each status claims, before consuming a result."""
    status = record["status"]
    if not isinstance(record.get("language"), str) or not record["language"]:
        raise ValueError("invalid case language")
    if "reused" in record and type(record["reused"]) is not bool:
        raise ValueError("invalid replay bookkeeping")
    if status == "compared":
        if (
            not integer(record.get("index"))
            or type(record.get("seed")) is not int
            or not isinstance(record.get("reference"), str)
            or not record["reference"]
            or type(record.get("disagreement")) is not bool
        ):
            raise ValueError("invalid comparison payload")
        if record["disagreement"]:
            case(record.get("counterexample"))
        elif record.get("counterexample") is not None:
            raise ValueError("unexpected counterexample")
        if "counterexample" not in record or record["rows"] != 0:
            raise ValueError("incomplete comparison payload")
        return
    if status == "skipped":
        return
    if status == "executed" and "profile" in record:
        profile = record["profile"]
        if (
            not isinstance(profile, dict)
            or profile.get("language") != record["language"]
            or any(not integer(profile.get(key)) for key in RESOURCE_FIELDS)
            or not 1 <= profile["inputs"] <= 10
            or record["rows"] != 1 << profile["inputs"]
            or not isinstance(record.get("family"), str)
            or record.get("family") not in {"zero", "one", "parity", "dense"}
            or any(
                not integer(record.get(key)) or record.get(key) != profile[key]
                for key in RESOURCE_FIELDS
            )
        ):
            raise ValueError("invalid resource profile")
        return
    width = record.get("table_bits")
    if type(width) is not int or width < 2 or width & (width - 1):
        raise ValueError("invalid case table width")
    if status == "refused":
        if record["rows"] != 0 or record.get("size") is not None:
            raise ValueError("invalid refusal payload")
    elif status == "measured":
        if not integer(record.get("size")) or record["rows"] != 0:
            raise ValueError("invalid size measurement")
    elif status == "stepped":
        if not integer(record.get("commands")) or record["rows"] != width:
            raise ValueError("invalid step measurement")
    elif status == "dropped":
        if not 1 <= record["rows"] <= width:
            raise ValueError("invalid dropped-row count")
    elif status == "executed" and (
        any(not integer(record.get(key)) for key in ("before", "after", "spaces"))
        or not 1 <= record["after"] <= record["before"]
        or record["spaces"] > record["before"] - record["after"]
        or record["rows"] < width
    ):
        raise ValueError("invalid deletion measurement")
