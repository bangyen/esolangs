"""rotfuck generator tests."""

from collections.abc import Callable, Iterable
from functools import cache

import pytest

from esolangs.languages import generators as boolean
from tests.generators.boolean_runners import _runner
from tests.interpreters.runner import run_program
from tests.support.witness_tables import row_bits


class TestRotfuck:
    """The ROTfuck boolean generator."""

    def test_program_round_trips_every_table_at_n_2(self) -> None:
        """Every two-input table produces the right result."""
        for table_int in range(2 ** (2**2)):
            table = format(table_int, "04b")
            program = boolean.rotfuck(table)
            for combo in range(4):
                bits = [(combo >> (1 - i)) & 1 for i in range(2)]
                got = run_rotfuck(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    @pytest.mark.parametrize("n", [6, 7, 8])
    def test_a_second_index_digit_still_selects_the_right_entry(self, n: int) -> None:
        """The arity where the index stops fitting in one walk."""
        table = "".join(str(bin(row).count("1") & 1) for row in range(2**n))
        program = boolean.rotfuck(table)
        for combo in (0, 1, 2**n - 1, 2**n - 2, 2 ** (n - 1), 2 ** (n - 1) - 1):
            bits = row_bits(combo, n)
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == table[combo], f"n={n} inputs {bits}"

    def test_the_rotation_cycle_is_the_interpreters_default(self) -> None:
        """The prose's ``+-><,.[]`` turned backward, and it is a cycle."""
        from esolangs.languages.rotfuck.generator import _ROTFUCK_CHAIN, _rotfuck_rot
        from esolangs.languages.rotfuck.interpreter import ROTFUCK_CYCLES as CYCLES

        assert _ROTFUCK_CHAIN == "+][.,<>-" == CYCLES["backward"]
        assert CYCLES["forward"] == "+-><,.[]"
        assert "+" + "+-><,.[]"[:0:-1] == _ROTFUCK_CHAIN
        for i, char in enumerate(_ROTFUCK_CHAIN):
            forward = _ROTFUCK_CHAIN[(i + 1) % 8]
            assert _rotfuck_rot(char, 1) == forward, char
            assert _rotfuck_rot(forward, -1) == char, char
            assert _rotfuck_rot(char, 8) == char, char
            assert _rotfuck_rot(char, 0) == char, char
        for i, char in enumerate(CYCLES["forward"]):
            assert (
                _rotfuck_rot(char, 1, CYCLES["forward"])
                == CYCLES["forward"][(i + 1) % 8]
            )

    @pytest.mark.parametrize("rotation", ["backward", "forward"])
    def test_a_command_never_shows_as_a_bracket_inside_a_seek(
        self, rotation: str
    ) -> None:
        """A command's rotation, seen from a seek's, must not be a bracket."""
        from esolangs.languages.rotfuck.generator import _rotfuck_rot, _shows
        from esolangs.languages.rotfuck.interpreter import ROTFUCK_CYCLES as CYCLES

        cycle = CYCLES[rotation]
        for seek in range(8):
            for rot in range(8):
                for cmd in "+-><":
                    assert _shows(cmd, seek, rot, cycle) == (
                        _rotfuck_rot(cmd, seek - rot, cycle) in "[]"
                    ), (rotation, cmd, seek, rot)
        if rotation == "backward":
            assert [c for c in "+-><" if not _shows(c, 0, 4)] == ["+", "-"]
            assert [c for c in "+-><" if not _shows(c, 0, 5)] == ["+", "<"]
            assert [c for c in "+-><" if not _shows(c, 0, 6)] == [">", "<"]

    def test_net_zero_runs_are_pairs_wrapped_in_inverses_and_chained(self) -> None:
        """The brute-force pad set (every ``+-><`` run <= 6) is the grammar's."""
        inverse = {"+": "-", "-": "+", "<": ">", ">": "<"}
        grown: dict[int, set[str]] = {0: {""}}
        for size in range(2, 7, 2):
            made = {
                step + run + inverse[step] for step in "+-><" for run in grown[size - 2]
            }
            for left in range(2, size, 2):
                made |= {a + b for a in grown[left] for b in grown[size - left]}
            grown[size] = made
        assert set(_search_pads()) == set().union(*grown.values()) - {""}

    # 3.8 s alone, but 16-17 s under CI's -n load (3 of 5 runs, 2026-10-16).
    @pytest.mark.slow
    def test_pads_match_the_search_they_replaced(self) -> None:
        """Same length and rotation as the Dijkstra over pads, on every state.

        A state is the open seeks and the rotation; the targets are every
        command hidden, a loop's opening and every phase.  The rule's word is
        hidden and net zero.
        """
        from esolangs.languages.rotfuck import generator as gen
        from esolangs.languages.rotfuck.interpreter import ROTFUCK_CYCLES

        # Open phases are pairwise 0, 3, 4 or 5 apart, so a set never has three.
        stacks = {()}
        for _ in range(2):
            stacks |= {
                tuple(sorted({*stack, phase}))
                for stack in stacks
                for phase in range(8)
                if all((seek - phase) % 8 in (0, 3, 4, 5) for seek in stack)
            }
        checked = 0
        for cycle in ROTFUCK_CYCLES.values():
            for stack in stacks:
                for rot in range(8):
                    for done in _targets(stack, cycle):
                        ruled = gen._Builder(cycle)  # noqa: SLF001
                        ruled._seeks, ruled.rot = list(stack), rot  # noqa: SLF001
                        found = _search_pad_until(ruled, done)
                        try:
                            ruled._pad_until(done)  # noqa: SLF001
                        except gen._UnplaceableError:  # noqa: SLF001
                            assert found is None
                            continue
                        assert found == len(ruled.src)
                        word = [
                            gen._rotfuck_rot(char, rot + at, cycle)  # noqa: SLF001
                            for at, char in enumerate(ruled.src)
                        ]
                        assert not any(
                            gen._shows(cmd, seek, rot + at, cycle)  # noqa: SLF001
                            for at, cmd in enumerate(word)
                            for seek in stack
                        )
                        assert _is_net_zero(word)
                        checked += 1
        assert checked > 4000

    def test_the_stride_is_the_walks_square_root(self) -> None:
        """One closed-form stride: at worst 16% over the scan it replaced.

        The scan won 0.08% of whole programs (94,060 vs 94,134 chars over 40
        random n=7..10 tables).
        """
        from esolangs.languages.rotfuck.generator import _skip

        for fresh in (True, False):
            for distance in (*range(1, 300), 533, 1000, 2047):
                ruled = len(_skip(distance, fresh=fresh))
                assert ruled <= distance
                assert ruled <= len(_scanned_skip(distance, fresh=fresh)) * 1.16

    @pytest.mark.parametrize("trips", range(7))
    def test_a_loop_leaves_the_rotation_where_it_found_it(self, trips: int) -> None:
        """The invariant every loop rests on, checked by running one."""
        from esolangs.generation.helpers import _ASCII_ZERO
        from esolangs.languages.rotfuck.generator import _Builder, _parse

        out = _Builder()
        out.emit(_parse("+" * trips + "[->+<]>" + "+" * _ASCII_ZERO + "."))
        assert run_rotfuck(out.text(), []) == str(trips)

    @pytest.mark.parametrize("body", ["-", "-+-", ">+<-", "[-]"])
    def test_a_body_of_either_parity_closes_at_its_phase(self, body: str) -> None:
        """An even body opens with a ``[`` that cannot fire; an odd one does not."""
        from esolangs.generation.helpers import _ASCII_ZERO
        from esolangs.languages.rotfuck.generator import _Builder, _parse

        out = _Builder()
        out.emit(_parse(f"+++[{body}]" + "+" * _ASCII_ZERO + "."))
        assert run_rotfuck(out.text(), []) == "0"

    def test_the_program_is_only_command_characters(self) -> None:
        """Nothing but the eight commands is emitted."""
        for table in ("01", "0110", "11110000", "01101001"):
            assert set(boolean.rotfuck(table)) <= set("+-><,.[]"), table

    def test_backward_is_the_default_direction(self) -> None:
        assert boolean.rotfuck("01", rotation="backward") == boolean.rotfuck("01")

    @pytest.mark.parametrize("rotation", ["backward", "forward"])
    def test_both_rotations_compute_their_table(self, rotation: str) -> None:
        """Either cycle is targeted; each program runs under its own."""
        run = run_rotfuck if rotation == "backward" else run_rotfuck_forward
        for table in ("01", "0110", "01101001", "11110000"):
            program = boolean.rotfuck(table, rotation=rotation)
            n = len(table).bit_length() - 1
            for combo in range(len(table)):
                bits = row_bits(combo, n)
                assert run(program, [str(b) for b in bits]) == table[combo], (
                    rotation,
                    table,
                    combo,
                )

    @pytest.mark.parametrize("n", [6, 7, 8])
    def test_forward_reaches_a_second_index_digit(self, n: int) -> None:
        """Forward emits its own walks through the arity where the index splits."""
        table = "".join(str(bin(row).count("1") & 1) for row in range(2**n))
        program = boolean.rotfuck(table, rotation="forward")
        for combo in (0, 1, 2**n - 1, 2 ** (n - 1)):
            bits = row_bits(combo, n)
            assert run_rotfuck_forward(program, [str(b) for b in bits]) == table[combo]

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 128),
            ("10", 128),
            ("0001", 211),
            ("0110", 212),
            ("11110000", 134),
            ("01101001", 301),
        ],
    )
    def test_the_emitted_length_is_exact(self, table: str, length: int) -> None:
        """The layout is deterministic down to the character."""
        assert len(boolean.rotfuck(table)) == length

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 144),
            ("10", 144),
            ("0001", 235),
            ("0110", 236),
            ("11110000", 150),
            ("01101001", 333),
        ],
    )
    def test_the_forward_length_is_exact(self, table: str, length: int) -> None:
        """The forward layout is deterministic down to the character."""
        assert len(boolean.rotfuck(table, rotation="forward")) == length

    def test_a_lone_late_one_in_a_64_table_is_exactly_616_long(self) -> None:
        """The loop-phase set (0, 3, 4, 5) mod 8 fixes the pads, so the length."""
        assert len(boolean.rotfuck("0" * 52 + "1" + "0" * 11)) == 616

    def test_a_long_run_of_zero_entries_is_skipped_by_a_walk_and_runs(self) -> None:
        """A zero upper half is one carried count, not 2 * 128 steps."""
        half = "".join(str(bin(row * 37 % 256).count("1") & 1) for row in range(128))
        table = half + "0" * 128
        program = boolean.rotfuck(table)
        assert len(program) < len(boolean.rotfuck(half + half[::-1]))
        for combo in (0, 1, 127, 128, 200, 255):
            bits = [(combo >> (7 - i)) & 1 for i in range(8)]
            assert run_rotfuck(program, [str(b) for b in bits]) == table[combo]


def test_rotation_is_checked() -> None:
    with pytest.raises(ValueError, match="rotation"):
        boolean.rotfuck("01", rotation="sideways")


@pytest.mark.medium
@pytest.mark.parametrize("bit", "01")
def test_every_constant_row_within_written_state_bound(bit: str) -> None:
    from esolangs import generate
    from tests.support.generator_support import assert_shared_program

    language = "ROTfuck"
    table = bit * 256
    commands = len(generate(language, table))

    def workspace(p):
        return (
            2 * 256
            + 5 * 8
            + 35
            + (2080 * len(p)).bit_length()
            + (518).bit_length()
            + len(p).bit_length()
            + 4
        )

    assert_shared_program(language, table, None, commands, workspace)


run_rotfuck = _runner("rotfuck")


def run_rotfuck_forward(program: str, inputs: list[str]) -> str:
    """Run a ROTfuck program under the forward rotation."""
    from esolangs.languages.rotfuck.interpreter import run as _run

    return run_program(_run, program, "".join(inputs), rotation="forward")


@cache
def _search_pads() -> tuple[str, ...]:
    """Every net-zero run of ``+-><`` of even length <= 6 (the old pad set)."""
    from itertools import product

    return tuple(
        "".join(run)
        for length in range(2, 7, 2)
        for run in product("+-><", repeat=length)
        if _is_net_zero(run)
    )


def _scanned_skip(distance: int, *, fresh: bool) -> str:
    """The old ``_skip``: the shortest walk over every stride."""
    best = ">" * distance
    start = "" if fresh else ">"
    room = distance - 1 if fresh else distance - 2
    for stride in range(2, room + 1):
        count = room // stride
        if count < 2:
            break
        walk = f"[[-{'>' * stride}+{'<' * stride}]{'>' * stride}-]"
        left = distance - len(start) - stride * count
        candidate = start + "+" * count + walk + ">" * left
        if len(candidate) < len(best):
            best = candidate
    return best


def _is_net_zero(run: Iterable[str]) -> bool:
    """Whether ``run`` leaves every cell and the pointer where they were."""
    cells: dict[int, int] = {}
    at = 0
    for char in run:
        at += (char == ">") - (char == "<")
        cells[at] = cells.get(at, 0) + (char == "+") - (char == "-")
    return at == 0 and not any(cells.values())


def _targets(stack: tuple[int, ...], cycle: str) -> list[Callable[[int], bool]]:
    """Every ``done`` predicate the builder passes, for open seeks ``stack``."""
    from esolangs.languages.rotfuck.generator import _shows

    hides = [
        lambda rot, cmd=cmd: not any(_shows(cmd, seek, rot, cycle) for seek in stack)
        for cmd in "+-<>,.[]"
    ]

    def opens(rot: int) -> bool:
        return all((seek - rot) % 8 in (0, 3, 4, 5) for seek in stack)

    phases = [lambda rot, phase=phase: rot == phase for phase in range(8)]
    return [*hides, opens, *phases]


def _search_pad_until(builder: object, done: Callable[[int], bool]) -> int | None:
    """The old Dijkstra over pad runs: the shortest pad length, or ``None``."""
    import heapq

    pads = _search_pads()
    queue = [(0, builder.rot, "")]  # type: ignore[attr-defined]
    seen: set[int] = set()
    while queue:
        cost, rot, path = heapq.heappop(queue)
        if done(rot):
            return cost
        if rot in seen:
            continue
        seen.add(rot)
        for run in pads:
            if all(
                builder._hidden(c, rot + i)  # type: ignore[attr-defined]  # noqa: SLF001
                for i, c in enumerate(run)
            ):
                heapq.heappush(
                    queue, (cost + len(run), (rot + len(run)) % 8, path + run)
                )
    return None
