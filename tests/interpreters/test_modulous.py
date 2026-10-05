"""Unit tests for the Modulous interpreter."""

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.stack_based.modulous import run
from tests.raises import raises_message


class TestModulous:
    def test_missing_jump_operand_rejected(self) -> None:
        """A command missing a required operand is malformed."""
        with pytest.raises(ValueError, match="missing operand"):
            run("[JMP]", IO())

    def test_push_string_without_quotes_is_rejected(self) -> None:
        """``[PSH STR hello]`` has no quoted section to push.

        ``mod.split('"')[1]`` on it raised a bare ``IndexError`` past
        ``run``'s ``ValueError`` boundary.
        """
        with raises_message(
            ValueError,
            'missing quoted string in PSH STR hello; expected [PSH STR "text"]',
        ):
            run("[PSH STR hello]", IO())

    def test_missing_operand_message_quotes_the_whole_command(self) -> None:
        """The message echoes the command with its tokens spaced normally.

        ``[JMP]`` is a single token, so it reads the same however the parts
        are joined -- the separator only shows once there are two of them.
        ``match=`` would not see it either way, being a substring search,
        so this asserts the message entire.
        """
        with raises_message(ValueError, "missing operand in JMP F"):
            run("[JMP F]", IO())

    def test_an_unknown_command_is_refused(self) -> None:
        """This test used to run ``[p 5]`` and assert it was a no-op.

        Its docstring is about the *empty* block, and ``[p 5]`` is not
        empty -- the case rode along without one.  Silently doing nothing is
        the worst answer to a typo: ``[PRTINT]``, a plausible slip for
        ``[PRT INT]``, exited 0 having printed nothing.

        The wiki does not settle it.  It says only that "a module is a
        command surrounded by square brackets" and never says what to do
        with anything else, so this is a choice, and the choice is to say
        so.  ``[]`` remains the way to write nothing.
        """
        with pytest.raises(ValueError, match="is not a Modulous command"):
            run("[p 5]", IO())
        with pytest.raises(ValueError, match="PRTINT"):
            run('[PSH STR "x"][PRTINT][END]', IO())

    @pytest.mark.parametrize(
        ("source", "hint"),
        [("[PHS INT 5]", "PSH"), ("[PRTT INT]", "PRT")],
    )
    def test_unknown_command_suggests_one_match(self, source: str, hint: str) -> None:
        with pytest.raises(ValueError, match=rf"did you mean {hint}\?"):
            run(source, IO())

    @pytest.mark.parametrize("source", ["[XYZ]", "[PRP]", "[P]", "[S]", "[p 5]"])
    def test_unknown_command_without_unique_match_has_no_hint(
        self, source: str
    ) -> None:
        with pytest.raises(ValueError, match="is not a Modulous command") as error:
            run(source, IO())
        assert "did you mean" not in str(error.value)

    def test_text_outside_a_command_is_refused(self) -> None:
        """``findall`` dropped it, so an unbalanced bracket ran half a program.

        ``[PSH INT 1[END]`` lost its first half -- the regex cannot match
        the unbalanced ``[`` -- and ran ``END``, exiting 0 with nothing
        printed and nothing said.
        """
        with pytest.raises(ValueError, match="outside any"):
            run("[PSH INT 1[END]", IO())
        with pytest.raises(ValueError, match="outside any"):
            run("[END] trailing junk", IO())

    def test_missing_add_operand_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing operand"):
            run("[ADD]", IO())

    def test_missing_push_operand_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing operand"):
            run("[PSH INT]", IO())

    def test_missing_random_operand_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing operand"):
            run("[RND]", IO())


class TestStepMachine:
    def test_a_token_less_state_starts_halted(self) -> None:
        from esolangs.interpreters.stack_based.modulous import _Machine

        # `step` has no halted guard of its own -- the caller checks first,
        # which is what the VM's run loop does.
        assert _Machine("", IO()).halted
