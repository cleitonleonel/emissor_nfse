
from scripts.generate_coverage_badge import (
    build_svg,
    coverage_color,
    extract_line_rate,
    format_percent,
    generate_badge,
)


def test_format_percent_and_color_thresholds():
    assert format_percent(0.8914) == "89.1%"
    assert format_percent(0.9) == "90%"
    assert coverage_color(91) == "#4c1"
    assert coverage_color(80) == "#97ca00"
    assert coverage_color(70) == "#a4a61d"
    assert coverage_color(60) == "#dfb317"
    assert coverage_color(50) == "#fe7d37"
    assert coverage_color(49.9) == "#e05d44"


def test_extract_line_rate_and_generate_badge(tmp_path):
    coverage_xml = tmp_path / "coverage.xml"
    coverage_xml.write_text(
        '<?xml version="1.0"?><coverage line-rate="0.875"></coverage>',
        encoding="utf-8",
    )

    assert extract_line_rate(coverage_xml) == 0.875

    output = tmp_path / "docs" / "assets" / "coverage.svg"
    result = generate_badge(coverage_xml, output)

    assert result == output
    assert output.exists()
    svg = output.read_text(encoding="utf-8")
    assert "coverage: 87.5%" in svg
    assert "#97ca00" in svg
    assert "coverage" in svg


def test_build_svg_contains_expected_labels():
    svg = build_svg("100%", "#4c1")
    assert "coverage: 100%" in svg
    assert "#4c1" in svg
    assert "width=\"124\"" in svg

