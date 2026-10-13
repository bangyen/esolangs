"""CPython's int/str digit cap, lifted for one block."""

import contextlib
import sys
from collections.abc import Iterator


@contextlib.contextmanager
def digit_limit_for(digits: int) -> Iterator[None]:
    """Raise the int/str digit cap to fit ``digits``, then restore it.

    The 4300 default is a DoS guard, not a language limit. A limit of 0 is
    already unlimited, and ``set_int_max_str_digits`` rejects values under 640.
    """
    limit = sys.get_int_max_str_digits()
    if limit == 0 or digits <= limit:
        yield
        return
    sys.set_int_max_str_digits(digits + 1)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(limit)
