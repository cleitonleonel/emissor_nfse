"""Generate a simple coverage badge SVG from a coverage.xml file.

This script intentionally uses only the Python standard library so it can run
inside GitHub Actions without extra dependencies.
"""

from __future__ import annotations

import argparse
import math
import xml.etree.ElementTree as ET
from pathlib import Path


def coverage_color(percent: float) -> str:
    if percent >= 90:
        return "#4c1"
    if percent >= 80:
        return "#97ca00"
    if percent >= 70:
        return "#a4a61d"
    if percent >= 60:
        return "#dfb317"
    if percent >= 50:
        return "#fe7d37"
    return "#e05d44"


def format_percent(rate: float) -> str:
    percent = rate * 100
    rounded = round(percent, 1)
    if math.isclose(rounded, round(rounded)):
        return f"{int(round(rounded))}%"
    return f"{rounded:.1f}%"


def extract_line_rate(xml_path: Path) -> float:
    root = ET.parse(xml_path).getroot()
    line_rate = root.attrib.get("line-rate")
    if line_rate is None:
        raise ValueError("coverage.xml does not contain a root line-rate attribute")
    return float(line_rate)


def build_svg(percent_text: str, color: str) -> str:
    label = "coverage"
    label_width = 70
    value_width = 54
    width = label_width + value_width

    return f"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"20\" role=\"img\" aria-label=\"coverage: {percent_text}\">
  <title>coverage: {percent_text}</title>
  <linearGradient id=\"s\" x2=\"0\" y2=\"100%\">
    <stop offset=\"0\" stop-color=\"#bbb\" stop-opacity=\".1\"/>
    <stop offset=\"1\" stop-opacity=\".1\"/>
  </linearGradient>
  <clipPath id=\"r\">
    <rect width=\"{width}\" height=\"20\" rx=\"3\" fill=\"#fff\"/>
  </clipPath>
  <g clip-path=\"url(#r)\">
    <rect width=\"{label_width}\" height=\"20\" fill=\"#555\"/>
    <rect x=\"{label_width}\" width=\"{value_width}\" height=\"20\" fill=\"{color}\"/>
    <rect width=\"{width}\" height=\"20\" fill=\"url(#s)\"/>
  </g>
  <g fill=\"#fff\" text-anchor=\"middle\" font-family=\"Verdana,Geneva,DejaVu Sans,sans-serif\" font-size=\"11\">
    <text x=\"35\" y=\"14\">{label}</text>
    <text x=\"97\" y=\"14\">{percent_text}</text>
  </g>
</svg>
"""


def generate_badge(xml_path: Path, output_path: Path) -> Path:
    rate = extract_line_rate(xml_path)
    percent_text = format_percent(rate)
    color = coverage_color(rate * 100)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_svg(percent_text, color), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="coverage.xml", help="Path to coverage.xml")
    parser.add_argument("--output", default="docs/assets/coverage.svg", help="Where to write the SVG badge")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = generate_badge(Path(args.input), Path(args.output))
    print(f"Coverage badge generated at {output}")


if __name__ == "__main__":
    main()

