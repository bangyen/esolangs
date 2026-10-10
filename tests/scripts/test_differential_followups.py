"""Replay verdicts, interrupted shrinking and independent evidence recovery."""

# ruff: noqa: SLF001, I001

import json
import random
import sys
from collections import Counter
from types import SimpleNamespace

import pytest

from scripts import _differential_campaign as campaign
from scripts import _screen_evidence as evidence
from scripts import _screen_phase as phase
from scripts import promote_differential as promotion

import differential as d


def saved(tmp_path):
    runner = SimpleNamespace(
        spec=SimpleNamespace(language="brainfuck"), template="ref", timeout=1
    )
    original = d.Case(
        "++.", "abc", "output differs", d.Outcome("halt", b"2"), d.Outcome("halt", b"3")
    )
    _, value = campaign.artifact(runner, 0, 0, d._case_record(original))
    path = tmp_path / "finding.json"
    path.write_text(json.dumps(value))
    return path, original


@pytest.mark.parametrize(
    ("cause", "status", "verdict", "code"),
    [
        ("output differs", "halt", "reproduced", 1),
        ("termination", "halt", "changed cause", 2),
        (None, "halt", "resolved", 0),
        (None, "limit", "inconclusive", 3),
        ("output differs", "timeout", "inconclusive", 3),
    ],
)
def test_replay_verdict(tmp_path, capsys, monkeypatch, cause, status, verdict, code):
    path, original = saved(tmp_path)
    identity = {"checkout": {}, "runtime": {}, "reference": {}}
    value = evidence.read(path)
    value["identity"] = identity
    path.write_text(json.dumps(value))
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"identity": identity}))
    monkeypatch.setenv("ESOLANGS_SCREEN_RESUME", str(context))
    observed = (
        d.Case(original.program, original.stdin, cause, original.ours, original.ref)
        if cause
        else None
    )
    runner = SimpleNamespace(
        spec=SimpleNamespace(language="brainfuck"),
        template="ref",
        check=lambda *_: observed,
        last_outcomes=(d.Outcome(status, b""), original.ref),
    )
    assert campaign.replay(runner, path, 0, d._case_record) == code
    assert json.loads(capsys.readouterr().out)["verdict"] == verdict


def test_checkpoint_retains_smallest_confirmed_case(tmp_path):
    path, original = saved(tmp_path)
    smaller = d._case_record(original) | {"program": "+.", "stdin": ""}
    campaign.checkpoint(path, smaller)
    campaign.checkpoint(path, d._case_record(original))
    campaign.checkpoint(path, smaller | {"program": ".", "cause": "changed"})
    assert evidence.read(path)["minimized"] == smaller


def test_minimizer_checkpoints_before_next_probe(tmp_path):
    path, original = saved(tmp_path)
    runner = d.Runner(d.SPECS["brainfuck"], "ref", 1)
    runner.checkpoint = path
    calls = Counter()

    def check(program, stdin):
        calls["count"] += 1
        if calls["count"] > 1:
            assert evidence.read(path)["minimized"] is not None
            raise RuntimeError("interrupted")
        return d.Case(program, stdin, original.cause, original.ours, original.ref)

    runner.check = check
    with pytest.raises(RuntimeError, match="interrupted"):
        runner._minimize(original)
    assert len(evidence.read(path)["minimized"]["program"]) < len(original.program)


def test_collection_preserves_later_valid_records_and_findings(tmp_path):
    path, _ = saved(tmp_path)
    valid = {
        "ordinal": 0,
        "rows": 0,
        "status": "measured",
        "case_id": "a",
        "language": "brainfuck",
        "table_bits": 8,
        "size": 1,
    }
    valid["evidence_sha256"] = evidence.checksum(valid)
    second = valid | {"ordinal": 2, "case_id": "b"}
    second["evidence_sha256"] = evidence.checksum(second)
    progress = tmp_path / "progress"
    progress.write_text(json.dumps(valid) + "\n{broken}\n" + json.dumps(second) + "\n")
    (tmp_path / "broken.json").write_text("no json")
    collected = phase.execute(
        "collect",
        {
            "progress": str(progress),
            "expected": ["a", "b"],
            "status": "timeout",
            "findings": str(tmp_path),
        },
    )
    assert [record["case_id"] for record in collected["cases"]] == ["a", "b"]
    assert len(collected["rejected"]) == 2
    assert collected["findings"][0]["path"] == str(path)
    evidence.validate(collected["cases"], ["a", "b"])


def test_promotion_generated_test_executes_and_detects_wrong_expectation(
    tmp_path, monkeypatch
):
    path, original = saved(tmp_path)
    original = d.Case(
        "++.",
        "",
        "output differs",
        d.Outcome("halt", b"\x02"),
        d.Outcome("halt", b"\x03"),
    )
    value = evidence.read(path)
    value["original"] = d._case_record(original)
    path.write_text(json.dumps(value))
    observation = json.dumps(
        {
            "expected_cause": original.cause,
            "observed": d._case_record(original),
            "verdict": "reproduced",
        }
    ).encode()
    monkeypatch.setattr(promotion, "run", lambda *_: (1, observation, b"", None))
    for side in ("ours", "ref"):
        destination = tmp_path / f"test_{side}.py"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "promote",
                str(path),
                str(destination),
                "--reason",
                "execution contract",
                "--allow-drift",
                "--expected-side",
                side,
            ],
        )
        promotion.main()
        namespace = {}
        exec(compile(destination.read_text(), str(destination), "exec"), namespace)
        if side == "ours":
            namespace["test_promoted_finding"]()
        else:
            with pytest.raises(AssertionError):
                namespace["test_promoted_finding"]()


@pytest.mark.medium
def test_promotion_confirms_through_bounded_replay(tmp_path, monkeypatch):
    import shlex

    runner = d.Runner(
        d.SPECS["brainfuck"],
        shlex.join(
            [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'\\x03')"]
        ),
        2,  # not .5: fresh interpreter startup exceeds that on Windows
    )
    case = runner.check("++.", "")
    assert case is not None
    _, value = campaign.artifact(runner, 0, 0, d._case_record(case))
    path = tmp_path / "case.json"
    value["replay"][value["replay"].index("--replay-case") + 1] = str(path)
    value["replay"].extend(["--report", str(tmp_path / "replay.json")])
    path.write_text(json.dumps(value))
    destination = tmp_path / "test_promoted.py"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "promote",
            str(path),
            str(destination),
            "--reason",
            "execution contract",
            "--allow-drift",
            "--expected-side",
            "ours",
        ],
    )
    promotion.main()
    namespace = {}
    exec(compile(destination.read_text(), str(destination), "exec"), namespace)
    namespace["test_promoted_finding"]()


def test_minimizer_recovers_checkpoint_after_child_timeout(tmp_path, monkeypatch):
    path, original = saved(tmp_path)
    runner = d.Runner(d.SPECS["brainfuck"], "ref", 1)
    runner.checkpoint = path
    smaller = d._case_record(original) | {"program": "+.", "stdin": ""}

    def interrupted(command, *_):
        assert command[command.index("--minimize-checkpoint") + 1] == str(path)
        campaign.checkpoint(path, smaller)
        return -1, b"", b"", "timeout"

    monkeypatch.setattr(d, "run_reference", interrupted)
    result = runner.minimize(original)
    assert d._case_record(result) == smaller
    assert runner.minimize_status == "timeout"


@pytest.mark.parametrize("verdict", ["resolved", "changed cause", "inconclusive"])
def test_promotion_refuses_unconfirmed_findings(tmp_path, monkeypatch, verdict):
    path, _ = saved(tmp_path)
    observation = json.dumps(
        {"expected_cause": "output differs", "verdict": verdict}
    ).encode()
    monkeypatch.setattr(promotion, "run", lambda *_: (1, observation, b"", None))
    destination = tmp_path / "test_promoted.py"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "promote",
            str(path),
            str(destination),
            "--reason",
            "execution contract",
            "--allow-drift",
            "--expected-side",
            "ref",
        ],
    )
    with pytest.raises(SystemExit):
        promotion.main()
    assert not destination.exists()


def test_regression_uses_language_comparison_adapter(monkeypatch):
    expected = d.Outcome("halt", b"rendered state")
    monkeypatch.setitem(
        promotion.SPECS,
        "adapter",
        SimpleNamespace(language="adapter", ours=lambda *_: expected),
    )
    monkeypatch.setattr(
        promotion, "run_ours", lambda *_: pytest.fail("bypassed adapter")
    )
    monkeypatch.setattr(
        promotion, "run_ours_fast", lambda *_: pytest.fail("unsupported fast path")
    )
    assert promotion.regression_outcomes("adapter", "program", "input", 10) == [
        expected
    ]


def test_regression_checks_both_execution_paths(monkeypatch):
    stepped = d.Outcome("halt", b"step")
    fast = d.Outcome("halt", b"fast")
    monkeypatch.setattr(promotion, "run_ours", lambda *_: stepped)
    monkeypatch.setattr(promotion, "run_ours_fast", lambda *_: fast)
    assert promotion.regression_outcomes("brainfuck", ".", "", 10) == [stepped, fast]


@pytest.mark.parametrize("language", sorted(d.SPECS))
def test_every_spec_generates_a_program(language: str) -> None:
    """Each plug-in's generator emits a program and an input.

    Catches a shard that rots into a generator raising or returning nothing,
    which a manual campaign would only find when someone next ran one.
    """
    spec = d.SPECS[language]
    rng = random.Random(0)
    program = spec.program(rng)
    assert isinstance(program, str), language
    assert program, language
    assert isinstance(spec.stdin(rng, program), str), language
