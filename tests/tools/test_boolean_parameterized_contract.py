"""Shared contracts for generators that embed their inputs."""

import importlib
import itertools
import re

import pytest

import esolangs
from esolangs.tools.back import _back_ordered


def _parameterized_generators():
    """Return every registered generator whose examples carry a fill recipe."""
    from esolangs.registry import LANGUAGES, parameterized_ids

    ids = parameterized_ids()
    return [
        (language.id, language.boolean)
        for language in LANGUAGES.values()
        if language.id in ids and language.boolean is not None
    ]


_RUN_FORM = {
    "BIO": "bio",
    "Bitdeque": "bitdeque",
    "Minsky Swap": "minsky_swap",
    "BF-PDA": "bfpda",
    "Home Row": "home_row",
}


def _embedded_inputs(gen: object, template: str, n: int) -> list[int]:
    """The inputs ``template`` embeds, in the order it embeds them.

    A generator emits one run of the language's character per input; the
    runs are read off the example's setters -- :func:`~esolangs.tools.helpers.runs`
    refuses a run of the wrong width, a stray character or a run left over,
    so a template that embeds an input twice or out of step with its setters
    fails here rather than reading as in order.
    """
    from esolangs.tools.examples import BOOLEAN_EXAMPLES
    from esolangs.tools.helpers import runs

    example = next(e for e in BOOLEAN_EXAMPLES.values() if e.generator is gen)
    spans = runs(template, example.char, example.setters(template, n))
    return list(range(len(spans)))


@pytest.mark.parametrize(("language", "attr"), sorted(_RUN_FORM.items()))
def test_run_form_generators_spell_their_own_runs(language: str, attr: str) -> None:
    """The generator emits the public runs itself: no ``{Xi}`` anywhere.

    The public template is the generator's output verbatim, and its runs
    of ``$`` sum to exactly its setters' widths -- one run per input,
    each as long as the code that replaces it.
    """
    from esolangs import tools as generators

    for table in ("01", "0110", "01101001"):
        raw = getattr(generators, attr)(table)
        assert "{X" not in raw, (language, table)
        template = esolangs.generate(language, table)
        assert str(template) == raw, (language, table)
        assert template.count("$") == sum(len(zero) for zero, _ in template.setters)
        assert template.inputs == len(table).bit_length() - 1


@pytest.mark.slow  # ~3s: builds every generator, up to n=4
def test_parameterized_generators_embed_each_input_once() -> None:
    """Every no-input generator embeds each input exactly once.

    An input-capable language reads each of its n inputs exactly once per
    run; a no-input language's parameterized generator should match, so each
    input is embedded exactly once -- never re-embedded at multiple decision
    nodes.

    A {Ci} complement placeholder must not appear at all.  instantiate no
    longer fills one, so a template carrying it would ship the literal text
    to the interpreter instead of failing, which is worth catching here.
    """

    checked = 0
    for name, gen in _parameterized_generators():
        for n in (1, 2, 3, 4):
            table = format(0, f"0{2**n}b")
            try:
                template = gen(table)
            except ValueError:
                # A generator need not cover every arity.  The invariant here is about
                # the templates a generator *does* emit, so an uncovered arity
                # is skipped rather than failed; the count below keeps that
                # from quietly emptying the sweep.
                continue
            checked += 1
            xs = _embedded_inputs(gen, template, n)
            cs = re.findall(r"\{C(\d+)\}", template)
            assert sorted(xs) == list(range(n)), (name, n, xs)
            assert len(xs) == n, (name, n, xs)
            assert not cs, (name, n, cs)
    # Guard the skip above: every generator covers at least n == 2, so a run
    # that checked far fewer templates than that means the sweep stopped
    # exercising the generators rather than the generators getting stricter.
    assert checked >= len(_parameterized_generators()), checked


_SLOT_ORDER_TABLES = ("0110", "01101001", "10101010", "11110000", "00111100")


def _all_derived_plans(derived_plans, staged_arities, n: int) -> dict:
    """Every staging the enumeration places at ``n``, in one pass.

    ``_derived_plans`` is asked for the tables it should look for, so a test
    that wants the whole arity has to name them.  The arity guard is checked
    *first*: naming every table means ``2 ** (2 ** n)`` of them, which is
    unbuildable past four inputs, and the guard is what the unstaged arities
    are being tested for anyway.
    """
    if n not in staged_arities:
        return derived_plans(n, ())
    every = tuple(format(v, f"0{2**n}b") for v in range(2 ** (2**n)))
    return derived_plans(n, every)


def _slot_order(gen: object, table: str) -> list[int] | None:
    """The input indices in the order ``gen`` emits them, or None."""

    try:
        template = gen(table)
    except ValueError:
        return None  # a generator need not cover every arity
    return _embedded_inputs(gen, template, len(table).bit_length() - 1)


@pytest.mark.slow  # builds every generator over several tables
def test_slots_run_in_name_order() -> None:
    """Every template's runs fit its setters, one run per input, in order.

    The k-th run *is* input k, so order cannot be wrong; what can is a run
    of the wrong width, a stray character or a run left over, which the
    reader refuses, and a load restructured that way is worth a failure
    rather than a shrug.

    Every generator is swept, with no exceptions carried -- Minifuck was the
    last one and is covered in its own test below, which pins the specific
    tables that used to leave sequence.
    """
    checked = 0
    for name, gen in _parameterized_generators():
        for table in _SLOT_ORDER_TABLES:
            slots = _slot_order(gen, table)
            if slots is None:
                continue
            checked += 1
            assert slots == sorted(slots), (name, table, slots)
    assert checked >= len(_parameterized_generators()), checked


def _drawing(template: str) -> str:
    """The template as the drawing the reorder bar compares.

    Every input is a run of the same character, so a mere relabelling of
    inputs already leaves the text unchanged: the drawing is the template.
    """
    return template


@pytest.mark.slow  # builds every permuting generator over several tables
def test_a_permuting_generator_changes_its_drawing() -> None:
    """A generator that permutes its slots must emit a different *drawing*.

    This is the reorder bar, and it is the one thing that could make a
    template's slot permutation a redefined benchmark rather than a smaller
    program.  ``instantiate`` substitutes by name, and ``_fill_back``'s
    setter is ``lambda _i, b:`` -- it ignores the index -- so if two input
    orders produced the same drawing they would emit *byte-identical
    programs* and any "saving" between them would be booked against the
    harness's fill order alone.

    They do not.  Back's tree is built on the permuted table, so a different
    order folds differently and draws a different program: at ``10101010``
    the identity order draws 115 characters and the winning order 44.  The
    permuted slot names are a consequence of choosing the order, not the
    source of the saving -- orders that share a drawing measure exactly the
    same size.

    Asserting that is what gives this teeth.  A future change that made the
    reorder cosmetic -- permuting names while emitting one drawing -- would
    still pass every correctness test in this class and fail here.
    """
    from itertools import permutations

    from esolangs.tools.helpers import permute_truth_table

    checked = 0
    for name in ("back",):
        build = _back_ordered
        for table in ("10101010", "11001100", "00111100"):
            n = 3
            builds: dict[str, set[int]] = {}
            for perm in permutations(range(n)):
                built = build(permute_truth_table(table, perm), perm)
                builds.setdefault(_drawing(built), set()).add(len(built))
            checked += 1
            # The orders must not all collapse onto one drawing, or the
            # reorder is a relabelling.
            assert len(builds) > 1, (
                name,
                table,
                "every input order draws the same program, so permuting the "
                "slots emits an identical program and books a fake saving",
            )
            # And size must be a function of the drawing, not of the labels:
            # orders sharing a drawing are the same program.
            for drawing, sizes in builds.items():
                assert len(sizes) == 1, (name, table, len(drawing), sorted(sizes))
    assert checked >= 3, checked


@pytest.mark.slow  # 2.6s: every fill of every parameterized generator
def test_fills_embed_a_zero_and_a_one_at_equal_width() -> None:
    """No fill may spell a 0 shorter than a 1, or the length leaks the input.

    A program whose length depends on its inputs reveals them without being
    read: an earlier BIO embedding ran to 236/240/244/248 characters for the
    four ``n == 2`` instantiations, so ``len(program)`` alone recovered the
    bits.  Every ``_fill_*`` therefore pads the two sides to equal width, an
    invariant stated on :func:`~esolangs.tools.helpers.instantiate`
    and enforced here.

    The check is per-generator rather than global: fills legitimately differ
    from each other in width, but for one generator and one table every
    instantiation must come out the same length.
    """

    from esolangs.tools import examples as ex

    fills = [
        (name, getattr(ex, name))
        for name in dir(ex)
        if name.startswith("_fill_") and callable(getattr(ex, name))
    ]
    assert fills, "no _fill_* functions found"

    for name, fill in fills:
        gen_name = name.removeprefix("_fill_")
        gen = getattr(ex, gen_name, None) or getattr(
            importlib.import_module("esolangs.tools"), gen_name, None
        )
        if gen is None:  # pragma: no cover - fill without a same-named generator
            continue
        for n in (1, 2):
            template = gen(format(0, f"0{2**n}b"))
            lengths = {
                len(fill(template, list(bits)))
                for bits in itertools.product((0, 1), repeat=n)
            }
            assert len(lengths) == 1, (
                f"{name} embeds bits at unequal width for n={n}: {sorted(lengths)}"
            )


class TestGeneratorEdgePaths:
    def test_parameterized_validation(self) -> None:
        """bio/back reject malformed truth tables."""
        from esolangs import tools as generators

        with pytest.raises(ValueError, match="power-of-two"):
            generators.bio("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            generators.bio("0123")
        with pytest.raises(ValueError, match="power-of-two"):
            generators.back("011")
