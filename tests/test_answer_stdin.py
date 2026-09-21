"""Validation and warnings for stdin passed through the public API."""

import pytest

import esolangs


class TestTheStdinJudgeIsReachableFromPython:
    """The one place the API was weaker than the command line."""

    def test_it_accepts_what_encode_inputs_builds(self) -> None:
        """The check must never fire on this package's own encoding.

        The sweep that matters: a judge which rejects the correct stdin for
        any language is worse than no judge, because the correct stdin is
        what every documented path produces.
        """
        wrong = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["reads_input"]:
                continue
            for table, bits in (("0110", [1, 0]), ("00010111", [1, 0, 1])):
                stdin = esolangs.encode_inputs(name, bits, table)
                try:
                    esolangs.check_stdin(name, stdin, table)
                except esolangs.EsolangError as exc:
                    wrong.append(f"{name} n={len(bits)}: {exc}")
        assert not wrong, "\n".join(wrong)

    def test_it_catches_the_wrong_alphabet(self) -> None:
        """0/1 lines into Grapheme, the sharpest edge in the package."""
        with pytest.raises(esolangs.ArgumentError, match="spells its bits"):
            esolangs.check_stdin("Grapheme", "0\n1\n")

    @pytest.mark.parametrize("stdin", ["999", "abc", "   ", "%%%", "ZZZ"])
    def test_it_catches_the_wrong_alphabet_on_one_line_too(self, stdin: str) -> None:
        """Clockwise's declared alphabet was enforced nowhere at all.

        The shape branch for a one-line language returned before the
        alphabet check, and that check is written per *line* while this
        shape spells a bit as a *character*.  So ``"999"`` was accepted,
        and the program answered a different row of the table -- ``0``
        where the correct ``"101"`` answers ``1`` -- with nothing said by
        either guard the documentation promises.
        """
        with pytest.raises(esolangs.ArgumentError, match="spells its bits"):
            esolangs.check_stdin("Clockwise", stdin, "10010110")

    def test_a_good_one_line_stdin_is_still_accepted(self) -> None:
        """A guard that refused the correct input would be worse."""
        esolangs.check_stdin("Clockwise", "101", "10010110")
        assert esolangs.evaluate("Clockwise", "10010110", timeout=30) == "10010110"

    def test_the_run_path_warns_about_it_as_well(self) -> None:
        """Both documented routes, since both were silent.

        The README promises ``run`` warns and ``run --judge`` refuses; the
        refusal is the test above, and this is the warning.
        """
        program = esolangs.generate("Clockwise", "10010110")
        with pytest.warns(UserWarning, match="spells its bits"):
            esolangs.run("Clockwise", program, "999", timeout=30)

    def test_it_catches_a_surplus_line(self) -> None:
        """Six lines into a three-input program answered the first three."""
        with pytest.raises(esolangs.ArgumentError, match="reads 3 line"):
            esolangs.check_stdin("brainfuck", "1\n1\n0\n0\n1\n1\n", "00010111")

    def test_it_catches_a_missing_line(self) -> None:
        """The direction that already errored at run time, now before it."""
        with pytest.raises(esolangs.ArgumentError, match="reads 3 line"):
            esolangs.check_stdin("brainfuck", "1\n0\n", "00010111")

    def test_it_catches_an_out_of_range_row_index(self) -> None:
        """What `run` could not check, because it does not know the arity."""
        with pytest.raises(esolangs.ArgumentError, match="out of range"):
            esolangs.check_stdin("Fargo", "8\n", "00010111")

    def test_it_catches_taglates_pad(self) -> None:
        """Its odd input count costs an extra line, and the shape says so."""
        esolangs.check_stdin(
            "Taglate",
            esolangs.encode_inputs("Taglate", [1, 0, 1], "00010111"),
            "00010111",
        )
        with pytest.raises(esolangs.ArgumentError):
            esolangs.check_stdin("Taglate", "1\n0\n1\n", "00010111")

    def test_it_refuses_a_language_with_no_stdin(self) -> None:
        """A template language reads none, so there is nothing to judge."""
        with pytest.raises(esolangs.ArgumentError, match="reads no stdin"):
            esolangs.check_stdin("Minifuck", "1\n0\n")

    def test_the_table_is_optional(self) -> None:
        """Shape and alphabet are checkable without knowing the arity."""
        esolangs.check_stdin("brainfuck", "1\n0\n")

    def test_a_non_string_stdin_is_named(self) -> None:
        """A caller who passes the bit list itself, which is an easy slip."""
        with pytest.raises(esolangs.ArgumentError, match="stdin must be a string"):
            esolangs.check_stdin("brainfuck", [1, 0], "0110")  # type: ignore[arg-type]

    def test_a_one_line_language_has_its_bits_counted(self) -> None:
        """Clockwise's underfeed is a shorter string, not a missing line.

        Undetectable from the run, which is why it stayed on the documented
        footgun list for three rounds -- but perfectly detectable *here*,
        because the table says how many bits that one line should hold.
        """
        esolangs.check_stdin("Clockwise", "101", "00010111")
        with pytest.raises(esolangs.ArgumentError, match="wants 3 bits"):
            esolangs.check_stdin("Clockwise", "10", "00010111")


class TestRunSaysWhenStdinLooksWrong:
    """Silence was indistinguishable from correctness, from Python."""

    def test_a_surplus_line_is_warned_about(self) -> None:
        """Six lines into a three-input program answered the first three."""
        program = esolangs.generate("brainfuck", "00010111")
        with pytest.warns(UserWarning, match="read 3 of the 6 lines"):
            answer = esolangs.run("brainfuck", program, "1\n1\n0\n0\n1\n1\n", 10)
        # A warning, not a refusal: the run still happened and still answered.
        assert answer == "1"

    def test_the_wrong_alphabet_is_warned_about(self) -> None:
        """The same judgement `check_stdin` raises, rendered as advice."""
        program = esolangs.generate("Grapheme", "0110")
        with pytest.warns(UserWarning, match="spells its bits"):
            esolangs.run("Grapheme", program, "0\n1\n", 10)

    # Generates and runs one program per language, like the wrap test above.
    @pytest.mark.medium
    def test_the_documented_path_is_silent(self) -> None:
        """A warning that fires on correct input is worse than none."""
        import warnings

        noisy = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["boolean_generator"] or facts["parameterized"]:
                continue
            program = esolangs.generate(name, "0110")
            if facts["answer_mode"] == "termination":
                continue
            stdin = esolangs.encode_inputs(name, [1, 0], "0110")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                esolangs.run(name, program, stdin, 20)
            if caught:
                noisy.append(f"{name}: {caught[0].message}")
        assert not noisy, "\n".join(noisy)

    def test_a_program_that_reads_nothing_is_not_warned_about(self) -> None:
        """Reading none of what it was given is not an arity mistake."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            esolangs.run("brainfuck", "+.", "1\n0\n", 10)
        assert not [c for c in caught if "lines supplied" in str(c.message)]

    def test_taking_a_value_from_past_the_end_is_warned_about(self) -> None:
        """The six that answer an underfed program now say they did.

        The signal is the *count of reads past the end*, not a guess from
        the supplied length: an underfeed supplies some input and runs off
        the end after it, which a ``supplied == 0`` test misses entirely.
        """
        for name in ("Circuit Diagram", "Flowchart", "S*bleq"):
            program = esolangs.generate(name, "10010110")
            short = esolangs.encode_inputs(name, [1, 0])
            with pytest.warns(UserWarning, match="past the end"):
                esolangs.run(name, program, short, 10)

    def test_forgetting_stdin_entirely_is_warned_about(self) -> None:
        """Fargo answered row 0 -- the starkest case, since nothing was fed."""
        with pytest.warns(UserWarning, match="past the end"):
            esolangs.run("Fargo", esolangs.generate("Fargo", "10010110"), "", 10)

    def test_a_language_whose_documented_stop_is_eof_is_not_warned_about(
        self,
    ) -> None:
        """Suffolk's programs end *by* running out of input.

        It halts rather than taking a value, so the warning is gated on
        ``eof_is_a_value`` -- counting the read alone warned about every
        correct Suffolk run there is, which is the false positive that
        makes a warning worth less than silence.
        """
        import warnings

        program = esolangs.generate("Suffolk", "0110")
        stdin = esolangs.encode_inputs("Suffolk", [1, 0], "0110")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert esolangs.run("Suffolk", program, stdin, 20) == "1"
        assert not caught

    # The same one-program-per-language sweep as the documented-path test
    # above, and the same band: 0.37s alone, 1.1-1.2s under the gate's
    # overlapped steps, which is where it tripped the fast ceiling.
    @pytest.mark.medium
    def test_no_language_warns_on_its_own_encoding(self) -> None:
        """The sweep that decides whether any of this is worth having."""
        import warnings

        noisy = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if (
                not facts["boolean_generator"]
                or facts["parameterized"]
                or facts["answer_mode"] == "termination"
            ):
                continue
            stdin = esolangs.encode_inputs(name, [1, 0], "0110")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                esolangs.run(name, esolangs.generate(name, "0110"), stdin, 20)
            if caught:
                noisy.append(f"{name}: {caught[0].message}")
        assert not noisy, "\n".join(noisy)
