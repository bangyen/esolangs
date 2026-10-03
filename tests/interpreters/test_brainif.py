"""Public BrainIf goto validation and VM parity."""

import esolangs.debugger as debugger_api


def test_nonpositive_goto_targets_are_rejected_by_run_and_vm() -> None:
    import pytest

    import esolangs

    for target in (0, -1):
        for guard in (0, 1):
            code = f"if {guard} goto {target}"
            with pytest.raises(esolangs.ProgramError, match="positive line number"):
                esolangs.run("BrainIf", code)
            vm = debugger_api.make_vm("BrainIf", code)
            with pytest.raises(esolangs.ProgramError, match="positive line number"):
                vm.step()


def test_positive_goto_targets_match_run_and_vm() -> None:
    import esolangs
    from esolangs.vm import run_until_halt

    for code, expected in (
        ("if 0 goto 3\nif 0 output\nif 0 increment\nif 1 output", "\x01"),
        ("if 0 goto 2", ""),
    ):
        assert esolangs.run("BrainIf", code) == expected
        vm = debugger_api.make_vm("BrainIf", code)
        assert run_until_halt(vm, limit=4)
        assert vm.output == expected
