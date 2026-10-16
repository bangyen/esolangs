"""Little-endian bit buffering shared by bit-oriented interpreters.

Bytes arrive and leave least-significant-bit first: the first bit read is
the byte's low bit, and the first bit written becomes the emitted byte's low
bit.  The buffers are plain tuples, so immutable-state machines can rebind
them.  Fetching and emitting bytes stays with the caller, whose EOF and
destination policies differ per language; callers refill an empty input
buffer before taking from it.
"""

#: ``(incoming, remaining)``: the buffered input byte and bits left in it.
type InputBuffer = tuple[int, int]

#: ``(outgoing, used)``: the buffered output byte and bits stored in it.
type OutputBuffer = tuple[int, int]


def take_bit(buffer: InputBuffer) -> tuple[InputBuffer, int]:
    """Shift one bit out of ``buffer``; the caller refills at zero remaining."""
    incoming, remaining = buffer
    return (incoming >> 1, remaining - 1), incoming & 1


def put_bit(buffer: OutputBuffer, bit: int) -> tuple[OutputBuffer, int | None]:
    """Shift ``bit`` into ``buffer``; a completed byte is returned."""
    outgoing, used = buffer
    outgoing |= (bit & 1) << used
    used += 1
    if used == 8:
        return (0, 0), outgoing
    return (outgoing, used), None


def flush_byte(buffer: OutputBuffer) -> int | None:
    """Return the partial byte in ``buffer``, if any bits are stored."""
    outgoing, used = buffer
    return outgoing if used else None
