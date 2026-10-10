"""Persist original and minimized differential cases with bounded replay commands."""

import json
import os
import random
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from _atomic import write_text
from _screen_evidence import case_id, read, reused
from _screen_payload import finding


def artifact(
    runner: Any, seed: int, index: int, original: dict[str, Any]
) -> tuple[Path | None, dict[str, Any]]:
    """Publish the original before minimization starts, if supervised."""
    name = os.environ.get("ESOLANGS_SCREEN_FINDINGS")
    path = (
        Path(name) / (case_id(runner.spec.language, seed, index) + ".json")
        if name
        else None
    )
    context_name = os.environ.get("ESOLANGS_SCREEN_RESUME")
    context = read(Path(context_name)).get("identity") if context_name else None
    value = {
        "schema": 1,
        "language": runner.spec.language,
        "seed": seed,
        "index": index,
        "identity": context,
        "original": original,
        "minimized": None,
        "minimization_status": "started",
        "replay": [
            sys.executable,
            str(Path(__file__).with_name("differential.py")),
            runner.spec.language,
            "--ref",
            runner.template,
            "--replay-case",
            str(path),
            "--ref-timeout",
            str(runner.timeout),
            "--budget-seconds",
            str(max(1, runner.timeout * 6 + 1)),
            "--setup-seconds",
            "5",
            "--finalize-seconds",
            "5",
        ],
    }
    if path is not None:
        finding(value)
        write_text(path, json.dumps(value, sort_keys=True))
    return path, value


def campaign(
    runner: Any,
    programs: int,
    seed: int,
    serialize: Callable[[Any], dict[str, Any]],
    deserialize: Callable[[dict[str, Any]], Any],
) -> list[tuple[Any, int]]:
    """Run cases and preserve the original and same-cause minimized finding."""
    from _budget import completed

    rng = random.Random(seed)
    groups: dict[str, list[tuple[Any, int]]] = {}
    for index in range(programs):
        program = runner.spec.program(rng)
        stdin = runner.spec.stdin(rng, program)
        identifier = case_id(runner.spec.language, seed, index)
        cached = reused(identifier)
        case = (
            (
                deserialize(cached["counterexample"])
                if cached["counterexample"] is not None
                else None
            )
            if cached is not None
            else runner.check(program, stdin)
        )
        completed(
            "compared",
            case_id=identifier,
            language=runner.spec.language,
            seed=seed,
            index=index,
            reference=runner.template,
            disagreement=case is not None,
            counterexample=serialize(case) if case is not None else None,
            reused=cached is not None,
        )
        if case is not None:
            groups.setdefault(case.cause, []).append((case, index))
    print(f"statuses (ours/ref): {dict(runner.tally.most_common())}")
    found = []
    for cases in groups.values():
        shortest, index = min(
            cases[:20], key=lambda pair: len(pair[0].program) + len(pair[0].stdin)
        )
        path, value = artifact(runner, seed, index, serialize(shortest))
        minimized = runner.minimize(shortest, runner.minimize_calls)
        value.update(
            minimized=serialize(minimized),
            minimization_status=getattr(runner, "minimize_status", "complete"),
        )
        if path is not None:
            finding(value)
            write_text(path, json.dumps(value, sort_keys=True))
        found.append((minimized, len(cases)))
    print(f"minimization statuses: {dict(runner.tally.most_common())}")
    return found


def replay(
    runner: Any, path: Path, seed: int, serialize: Callable[[Any], dict[str, Any]]
) -> int:
    """Re-run the saved minimized input, or the original when minimization stopped."""
    from _budget import completed

    value = read(path)
    finding(value)
    if value["language"] != runner.spec.language:
        raise ValueError("replay language does not match")
    saved = value["minimized"] or value["original"]
    observed = runner.check(saved["program"], saved["stdin"])
    completed(
        "compared",
        case_id=case_id(runner.spec.language, seed, 0),
        language=runner.spec.language,
        seed=seed,
        index=0,
        reference=runner.template,
        disagreement=observed is not None,
        counterexample=serialize(observed) if observed is not None else None,
    )
    print(
        json.dumps(
            {
                "expected_cause": saved["cause"],
                "observed": serialize(observed) if observed is not None else None,
            }
        )
    )
    return 1 if observed is not None else 0
