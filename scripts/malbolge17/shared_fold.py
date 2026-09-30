"""The canonical shared address-fold setup used by decoder consumers."""

from address_gadget import build
from planner import _Planner


def build_shared_fold(
    *,
    outputs: dict[str, int] | None = None,
    occupied: set[int] | None = None,
    decoder_constants: bool = False,
    decoder_plans: list[_Planner] | None = None,
) -> tuple[str, tuple[tuple[int, int, int], ...], int, int]:
    """Emit the complete shared fold, optionally with decoder setup constants."""
    return build(
        None,
        dispatch_ab=True,
        parity=True,
        shared_special_fold=True,
        guard_scratch=True,
        prepare_returns=True,
        result_first=True,
        slot_pointers=True,
        high_pointer=True,
        high_parity=True,
        outputs=outputs,
        occupied=occupied,
        decoder_constants=decoder_constants,
        decoder_plans=decoder_plans,
    )
