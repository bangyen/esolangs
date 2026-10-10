"""Rebuild bounded replay commands and compare saved execution provenance."""

import json
import os
import sys
from pathlib import Path
from typing import Any

from _screen_evidence import read

FLAGS = {
    "reference_timeout": "--ref-timeout",
    "budget_seconds": "--budget-seconds",
    "setup_seconds": "--setup-seconds",
    "finalize_seconds": "--finalize-seconds",
}


def parameters(value: dict[str, Any]) -> dict[str, Any]:
    """Read structured parameters or migrate a legacy command without executing it."""
    from differential import SPECS

    key = next(
        (k for k, spec in SPECS.items() if spec.language == value["language"]), None
    )
    if key is None:
        raise ValueError("unknown replay language")
    if "replay_parameters" in value:
        result = dict(value["replay_parameters"])
    else:
        command = value["replay"]
        if command.count("--ref") != 1:
            raise ValueError("replay requires one reference")
        try:
            result = {"language": key, "reference": command[command.index("--ref") + 1]}
            result.update(
                {
                    name: float(command[command.index(flag) + 1])
                    for name, flag in FLAGS.items()
                }
            )
        except (IndexError, ValueError) as error:
            raise ValueError("invalid legacy replay parameters") from error
    if result["language"] != key:
        raise ValueError("replay language does not match finding")
    return result


def command(
    value: dict[str, Any],
    path: Path,
    *,
    allow_drift: bool = False,
    reference: str | None = None,
) -> list[str]:
    """Use the current interpreter, checkout and artifact path, never saved argv."""
    from _screen_payload import finding

    finding(value)
    params = parameters(value)
    result = [
        sys.executable,
        str(Path(__file__).with_name("differential.py")),
        params["language"],
        "--ref",
        reference or params["reference"],
        "--replay-case",
        str(path),
    ]
    for name, flag in FLAGS.items():
        result.extend([flag, str(params[name])])
    if allow_drift:
        result.append("--allow-drift")
    return result


def provenance(
    value: dict[str, Any], template: str, *, allow_drift: bool
) -> dict[str, Any]:
    """Refuse changed or missing identities unless the caller explicitly overrides."""
    context = os.environ.get("ESOLANGS_SCREEN_RESUME")
    if context:
        current = read(Path(context))["identity"]
    else:
        from _screen_phase import execute

        current = execute("metadata", {})
        current["reference"] = execute("reference", {"template": template})
    current = json.loads(json.dumps(current))
    saved = value.get("identity")
    drift = [
        key
        for key in ("checkout", "runtime", "reference")
        if not isinstance(saved, dict)
        or saved.get(key) is None
        or saved[key] != current.get(key)
    ]
    if drift and not allow_drift:
        raise ValueError(
            "replay provenance differs: " + ", ".join(drift) + "; use --allow-drift"
        )
    return {"drift": drift, "override": bool(drift and allow_drift), "current": current}
