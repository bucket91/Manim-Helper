from __future__ import annotations

import tempfile
from pathlib import Path

from bms.engine.render import build_render_spec, quality_params
from bms.project import Project


def test_quality_params_all():
    assert quality_params("draft", 30)["frame_rate"] == 15
    assert quality_params("medium", 30)["frame_rate"] == 30
    assert quality_params("medium", 60)["frame_rate"] == 60
    assert quality_params("final", 30)["frame_rate"] == 30
    assert quality_params("final", 60)["frame_rate"] == 60


def test_build_render_spec_frame_beat():
    with tempfile.TemporaryDirectory() as d:
        p = Project.create(Path(d) / "p", "P")
        spec = build_render_spec(p, "s1", mode="frame", beat_id="b1", quality="draft")
        assert spec["manim_config"]["save_last_frame"] is True
        # write_to_movie not set for this manim version
