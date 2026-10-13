"""Internal resumption signal for faulting interpreters."""


class _Fault(Exception):  # noqa: N818 - an internal resumption signal
    """Carries the output prefix computed before a fault, and the fault.

    The shell flushes ``effects`` and re-raises ``error``, so output written
    before a later read fails or an operation halts is not lost.
    """

    def __init__(self, effects: tuple[str, ...], error: BaseException) -> None:
        super().__init__(str(error))
        self.effects = effects
        self.error = error
