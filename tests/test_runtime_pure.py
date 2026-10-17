from __future__ import annotations

import pytest

from bms.runtime.objects import resolve_color, to_bangla_digits
from bms.runtime.protocol import emit_error, emit_progress, emit_warn, parse_line
from bms.runtime.regions import REGIONS, default_region, fit_scale


def test_to_bangla_digits():
    assert to_bangla_digits("Q 12") == "Q ১২"
    assert to_bangla_digits("0 19 2026") == "০ ১৯ ২০২৬"
    assert to_bangla_digits("no digits") == "no digits"


def test_default_region_full_layout():
    assert default_region("full", "mathtex") == "center"
    assert default_region("full", "question_panel") == "center"
    assert default_region("full", "text_bn") == "center"


def test_default_region_split_layout():
    assert default_region("split60_40", "question_panel") == "question"
    assert default_region("split60_40", "mathtex") == "solution"
    assert default_region("split60_40", "text_bn") == "solution"
    assert default_region("split60_40", "function_graph") == "solution"


def test_fit_scale_fits():
    assert fit_scale(2.0, 1.0, "center") == 1.0
    assert fit_scale(13.0, 7.2, "center") == 1.0
    assert fit_scale(0.0, 0.0, "center") == 1.0


def test_fit_scale_shrinks_to_region():
    info = REGIONS["question"]
    assert fit_scale(info.max_width * 2, 1.0, "question") == pytest.approx(0.5)
    assert fit_scale(1.0, info.max_height * 4, "question") == pytest.approx(0.25)
    assert fit_scale(info.max_width * 2, info.max_height * 4, "question") == pytest.approx(
        min(0.5, 0.25)
    )
    assert fit_scale(2.0, 1.0, info) == 1.0


def test_fit_scale_unknown_region():
    with pytest.raises(ValueError):
        fit_scale(1.0, 1.0, "nope")


def test_resolve_color_accepts_hex_and_names():
    assert resolve_color("#ff0000") is not None
    assert resolve_color("#00ff00") is not None
    assert resolve_color("RED") is not None
    assert resolve_color("GRAY_B") is not None


@pytest.mark.parametrize("value", ["notacolor", "RED2", "#GGG000", "", None, 3])
def test_resolve_color_rejects(value):
    with pytest.raises(ValueError):
        resolve_color(value)


def test_protocol_progress_round_trip():
    parsed = parse_line(emit_progress("b1", 2, 5))
    assert parsed == {"type": "progress", "beat": "b1", "index": 2, "total": 5}


def test_protocol_warn_round_trip():
    parsed = parse_line(emit_warn("fit", object="q1", scale="0.75"))
    assert parsed == {
        "type": "warn",
        "kind": "fit",
        "fields": {"object": "q1", "scale": "0.75"},
    }


def test_protocol_warn_without_fields():
    assert parse_line(emit_warn("custom_skipped")) == {
        "type": "warn",
        "kind": "custom_skipped",
        "fields": {},
    }


def test_protocol_error_round_trip():
    error = {
        "kind": "object_build",
        "scene_id": "S",
        "beat_id": "b1",
        "object_id": "gr",
        "step_index": 1,
        "message": "boom",
    }
    assert parse_line(emit_error(error)) == {"type": "error", "error": error}


@pytest.mark.parametrize(
    "line",
    ["", "hello", "BMS_PROGRESS|beat=b1", "BMS_PROGRESS|beat=b1|index=x|total=2",
     "BMS_WARN", "BMS_ERROR|not json", "BMS_ERROR|[1,2]"],
)
def test_parse_line_rejects_malformed(line):
    assert parse_line(line) is None


def test_parse_line_ignores_non_string():
    assert parse_line(None) is None
    assert parse_line(42) is None
