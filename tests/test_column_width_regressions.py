"""Regressions for real per-column-width generation.

Every dimension here is read out of the artifact bytes -- the PNG IHDR chunk,
the SVG root ``width``, the PDF ``/MediaBox`` -- rather than from any field the
pipeline wrote about itself. A run that rendered one figure and rescaled it with
CSS would satisfy a self-reported check and must fail these.
"""

import importlib.util
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from figure_agent.candidates import PAPER_WIDTH_MM
from figure_agent.workflow import generate_from_text


ROOT = Path(__file__).resolve().parents[1]
DEV_TEXT = "用户问题 -> 检索器 -> 生成器 -> 答案；若证据不足则生成器返回检索器"
PT_PER_MM = 72.0 / 25.4


def _png_mm(path, dpi=220):
    """Physical size from the PNG IHDR chunk, not from a sidecar record."""
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"not a PNG: {path}"
    assert data[12:16] == b"IHDR", f"first chunk is not IHDR: {path}"
    width_px, height_px = struct.unpack(">II", data[16:24])
    return width_px / dpi * 25.4, height_px / dpi * 25.4


def _svg_mm(path):
    width = ET.parse(path).getroot().get("width")
    assert width and width.endswith("pt"), f"SVG carries no pt width: {width!r}"
    return float(width[:-2]) / PT_PER_MM


def _pdf_mm(path):
    match = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", Path(path).read_bytes())
    assert match, f"no /MediaBox in {path}"
    return float(match.group(1)) / PT_PER_MM


@pytest.fixture(scope="module")
def both_widths(tmp_path_factory):
    """One real generation run per width, from the same source text."""
    base = tmp_path_factory.mktemp("colwidth")
    return {
        width: generate_from_text(DEV_TEXT, base / width, count=1, paper_width=width)
        for width in PAPER_WIDTH_MM
    }


@pytest.mark.parametrize("width", sorted(PAPER_WIDTH_MM))
def test_svg_pdf_and_png_bytes_carry_the_requested_physical_width(both_widths, width):
    candidate = both_widths[width]["candidates"][0]
    expected = PAPER_WIDTH_MM[width]
    artifacts = candidate["artifacts"]

    svg_mm = _svg_mm(artifacts["svg"])
    pdf_mm = _pdf_mm(artifacts["pdf"])
    png_mm, _ = _png_mm(artifacts["png"])

    assert svg_mm == pytest.approx(expected, abs=0.1), f"SVG is {svg_mm:.2f}mm, expected {expected}mm"
    assert pdf_mm == pytest.approx(expected, abs=0.1), f"PDF is {pdf_mm:.2f}mm, expected {expected}mm"
    assert png_mm == pytest.approx(expected, abs=0.5), f"PNG is {png_mm:.2f}mm, expected {expected}mm"
    # Three independent formats must agree; one format alone could be a coincidence.
    assert svg_mm == pytest.approx(pdf_mm, abs=0.1)
    assert candidate["spec"]["constraints"]["paper_width"] == width


def test_the_two_widths_are_not_one_artifact_rescaled(both_widths):
    """Two genuinely different physical renders, not one figure re-presented."""
    single, double = both_widths["single_column"], both_widths["double_column"]
    single_png = Path(single["candidates"][0]["artifacts"]["png"])
    double_png = Path(double["candidates"][0]["artifacts"]["png"])

    # These two assertions guard different failures, verified against a simulated
    # pre-fix pipeline. Byte inequality only rules out literally reusing one file:
    # it still holds when the width reaches the style layer but not the layout,
    # because smaller fonts on a 180mm canvas already change the bytes. The
    # millimetre comparison is what catches that case, so keep both.
    assert single_png.read_bytes() != double_png.read_bytes()
    assert _png_mm(single_png)[0] < _png_mm(double_png)[0] - 50
    # The width must reach the style layer too, not only the page box.
    fonts = {
        width: payload["candidates"][0]["spec"]["style"]["font_sizes"]["node"]
        for width, payload in both_widths.items()
    }
    assert fonts["single_column"] < fonts["double_column"], fonts


def test_column_width_changes_nothing_semantic(both_widths):
    """Width is a rendering constraint; the science it depicts must not move."""

    def semantics(payload):
        spec = payload["candidates"][0]["spec"]
        labels = {node["id"]: node["label"] for node in spec["nodes"]}
        return (
            [node["label"] for node in spec["nodes"]],
            sorted((labels[edge["source"]], labels[edge["target"]], edge["type"]) for edge in spec["edges"]),
            sorted(item["code"] for item in spec.get("needs_review", [])),
        )

    single = semantics(both_widths["single_column"])
    double = semantics(both_widths["double_column"])
    assert single == double
    # Non-vacuity guard: equality above would also hold for two empty specs.
    # The arrow form of the fixture yields four nodes and three data-flow edges;
    # its trailing feedback clause stays inside the last node label, which is
    # parser behaviour this test deliberately does not assert about.
    assert len(single[0]) == 4 and len(single[1]) == 3, single


def test_existing_default_call_is_unaffected(tmp_path):
    """``paper_width`` defaults to None, so old call shapes must be untouched."""
    candidate = generate_from_text(DEV_TEXT, tmp_path, count=1)["candidates"][0]
    assert _svg_mm(candidate["artifacts"]["svg"]) == pytest.approx(180.0, abs=0.1)
    assert _pdf_mm(candidate["artifacts"]["pdf"]) == pytest.approx(180.0, abs=0.1)


def test_unsupported_width_is_refused_not_silently_defaulted(tmp_path):
    with pytest.raises(ValueError, match="unsupported paper_width"):
        generate_from_text(DEV_TEXT, tmp_path / "bad", count=1, paper_width="three_column")


def _freeze_module():
    spec = importlib.util.spec_from_file_location("freeze_visual_colwidth", ROOT / "scripts/freeze_visual_rc1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_freeze_wiring_produces_a_blind_per_width_package(tmp_path, monkeypatch):
    """End to end: the frozen package must pass the freezer's own blindness gate.

    ``main`` calls ``assert_reviewer_package_is_blind`` itself, so a reviewer
    page carrying candidate identity -- or any ``LEAKY_FIELDS`` substring --
    makes this test raise ``SystemExit`` rather than merely look wrong.
    """
    from figure_agent.visual_eval import generate_benchmark

    module = _freeze_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    # git provenance is not what this test exercises; keep it hermetic.
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **k: f"{'0' * 40}\n")

    cases = [{"id": "dev_case_01", "category": "pipeline", "text": DEV_TEXT}]
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    source = tmp_path / "bench"
    generate_benchmark(cases, source)

    module.main(round_id="devcolwidth", source=source, cases_path=cases_path)

    output = tmp_path / "outputs/visual-benchmark-devcolwidth"
    reviewer = output / "reviewer"
    module.assert_reviewer_package_is_blind(reviewer)

    # The mapping from blind id to candidate stays outside the reviewer directory.
    assert not (reviewer / "private-mapping.json").exists()
    mapping = json.loads((output / "private-mapping.json").read_text(encoding="utf-8"))
    assert len(mapping) == 3 * len(PAPER_WIDTH_MM)
    page = (reviewer / "index.html").read_text(encoding="utf-8")
    for entry in mapping:
        assert entry["candidate_id"] not in page
        assert entry["case_id"] not in page
        assert entry["blind_id"] in page

    # Each width contributes its own real pixels, and no PNG is reused.
    protocol = json.loads((output / "protocol.json").read_text(encoding="utf-8"))
    evidence = protocol["column_width_evidence"]
    assert evidence["display_scaling_used_as_substitute"] is False
    observed = evidence["observed_png_width_px"]
    assert set(observed) == set(PAPER_WIDTH_MM)
    assert max(observed["single_column"]) < min(observed["double_column"])
    assert len({entry["png_sha256"] for entry in mapping}) == len(mapping)
