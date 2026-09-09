"""Minifuck simulator paths the generator's own runs never take."""

from esolangs.tools.boolean.minifuck_sim import _Joint, _Sim


class TestJointEmit:
    def test_an_empty_emission_advances_no_row(self) -> None:
        """The template is still appended, so the program text is unchanged.

        The rows are left where they stood: there is nothing to apply.
        """
        joint = _Joint(2, size=32)
        before = [m.key() for m in joint.ms]
        joint.emit("")
        assert joint.parts == [""]
        assert [m.key() for m in joint.ms] == before

    def test_a_non_empty_emission_advances_every_row(self) -> None:
        joint = _Joint(2, size=32)
        before = [m.key() for m in joint.ms]
        joint.emit("[")
        assert [m.key() for m in joint.ms] != before


class TestSimKey:
    def test_the_key_is_the_whole_state(self) -> None:
        """Two machines agree on their key exactly when they agree."""
        one, two = _Sim(32), _Sim(32)
        assert one.key() == two.key()
        one.exec("[")
        assert one.key() != two.key()
        two.exec("[")
        assert one.key() == two.key()
