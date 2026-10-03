"""bio generator tests."""

from tests.tools.fills import _run_form


class TestParameterizedBIO:
    """Input-by-substitution generators for the no-input language BIO."""

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs import tools as generators
        from esolangs.tools.bio import BIO_PAIR
        from esolangs.tools.helpers import runs

        template = generators.bio("0110")
        # one four-character unit per input; the doubling between them
        # (eight commands, 32 characters) carries the first input's weight
        double = "0ix{1ox;0oy;0oy;};0iy{1oy;0ox;};"
        assert template.startswith("$$$$" + double + "$$$$")
        assert runs(template, "$", (BIO_PAIR,) * 2) == [(0, 4), (36, 40)]

    def test_each_input_is_stored_once(self) -> None:
        """The packing scheme embeds each input exactly once."""

        from esolangs import tools as generators
        from esolangs.tools.bio import BIO_PAIR
        from esolangs.tools.helpers import runs

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = generators.bio(table)
            assert len(runs(template, "$", (BIO_PAIR,) * n)) == n

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """A zero pads against the unread ``z``, so the program's length
        does not reveal the inputs."""
        from esolangs.tools.bio import BIO_PAIR
        from tests.tools.fills import _fill_bio

        for n in (1, 2, 3):
            template = _run_form(BIO_PAIR, n)
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bio(template, zeros)) == len(
                    _fill_bio(template, ones)
                ), f"n={n} input {i}"

    def test_padding_never_touches_a_read_register(self) -> None:
        """``z`` is inert: the generator emits no command that reads it."""
        import esolangs
        from esolangs.interpreters.register_based.bio import parse

        for n in (1, 2, 3):
            template = esolangs.generate("BIO", "0" * (1 << n))
            commands = parse(esolangs.instantiate("BIO", template, [0] * n))
            assert commands.count("0oz;") == n
            assert all(command not in ("0iz{", "1iz;") for command in commands)

    def test_every_input_is_the_same_pair(self) -> None:
        """The weight lives in the template: one ``(zero, one)`` at every arity."""
        import esolangs

        for n in range(1, 7):
            setters = esolangs.generate("BIO", "01" * (2 ** (n - 1))).setters
            assert set(setters) == {("0oz;", "0ox;")}, n
            assert len(setters) == n
