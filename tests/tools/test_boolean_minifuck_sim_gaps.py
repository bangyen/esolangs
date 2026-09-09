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


class TestSimStateRoundTrip:
    def test_restore_rebuilds_what_key_described(self) -> None:
        """``restore`` is ``key``'s inverse, so the pair round-trips."""
        sim = _Sim(32)
        sim.exec("[")
        sim.exec(".")
        rebuilt = _Sim.restore(sim.key())
        assert rebuilt.key() == sim.key()

    def test_a_restored_machine_advances_like_the_original(self) -> None:
        sim = _Sim(32)
        sim.exec("[")
        rebuilt = _Sim.restore(sim.key())
        sim.exec("[")
        rebuilt.exec("[")
        assert rebuilt.key() == sim.key()
