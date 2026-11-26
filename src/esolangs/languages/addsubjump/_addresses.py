"""Special AddSubJump memory addresses."""

_IO = -1
_CF, _ZF, _NF, _VF = -2, -3, -4, -5
_ONE, _ZERO, _NEG = -6, -7, -8
_FUM = -9
_SPECIAL = set(range(_FUM, _IO + 1))
