r"""The drained-DAG builder's refusals."""

from esolangs.tools.boolean.register import (
    _polynomial_drained_dag,
    _polynomial_drained_dag_cost,
)


class TestDrainedDag:
    def test_a_table_using_its_first_input_is_declined(self) -> None:
        # XOR: both inputs are.
        assert _polynomial_drained_dag("0110") is None
        assert _polynomial_drained_dag_cost("0110") is None

    def test_a_table_ignoring_its_first_input_is_built(self) -> None:
        r"""Only the second input matters, so the first is drained."""
        instrs = _polynomial_drained_dag("0101")
        assert instrs is not None
        cost = _polynomial_drained_dag_cost("0101")
        assert cost == len(instrs)

    def test_two_ignored_inputs_cost_two_instructions_each(self) -> None:
        built = _polynomial_drained_dag("01010101")
        plain = _polynomial_drained_dag("0101")
        assert built is not None
        assert plain is not None
        # One more ignored input than.
        assert len(built) == len(plain) + 2
