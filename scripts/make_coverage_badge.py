"""Generate coverage-badge.svg from a coverage.py XML report.

Reads coverage.xml (as written by ``pytest --cov --cov-report=xml``) and writes
a shields.io-style SVG badge showing the total line coverage. Uses only the
standard library so it can run anywhere.

Usage:
    python scripts/make_coverage_badge.py [coverage.xml] [out.svg]
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

GREEN = "#4c1"
YELLOW = "#dfb317"
ORANGE = "#fe7d37"
RED = "#e05d44"


def color_for(percent: float) -> str:
    if percent >= 95:
        return GREEN
    if percent >= 90:
        return YELLOW
    if percent >= 75:
        return ORANGE
    return RED


def make_badge(percent: float) -> str:
    label = "coverage"
    value = f"{percent:.0f}%"
    left_w = 8 * len(label) + 10
    right_w = 8 * len(value) + 10
    total_w = left_w + right_w
    color = color_for(percent)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_w}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{left_w}" height="20" fill="#555"/>
    <rect x="{left_w}" width="{right_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{left_w // 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{left_w // 2}" y="14">{label}</text>
    <text x="{left_w + right_w // 2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{left_w + right_w // 2}" y="14">{value}</text>
  </g>
</svg>
"""


def main() -> None:
    xml_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("coverage.xml")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("coverage-badge.svg")

    tree = ET.parse(xml_path)
    root = tree.getroot()
    rate = float(root.get("line-rate", "0"))
    out_path.write_text(make_badge(rate * 100))
    print(f"wrote {out_path} ({rate * 100:.0f}% coverage)")


if __name__ == "__main__":
    main()
