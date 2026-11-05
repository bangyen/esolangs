"""A maximal mixed OR/XOR tree, outside the full-parity family."""


def witness(n: int) -> str:
    """Keep distinct maximal children; OR and XOR both cost twelve characters."""
    left, right = "0111", "0110"
    for _ in range(2, n):
        left, right = left + right, right + left
    return left


def workspace_witness(n: int) -> str:
    """Two drained bits and a Gaussian constant peak above the arithmetic tail."""
    return witness(n)[:-4] + "0000"
