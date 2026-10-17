from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from bms import jsonio
from bms.engine import render
from bms.project import Project


@pytest.mark.manim
def test_render_sample_all_modes(tmp_path, monkeypatch):
    # use the sample project
    sample = Path("/home/mhd/Manim-Helper/samples/demo_project")
    with tempfile.TemporaryDirectory() as d:
        import shutil

        proj_dir = Path(d) / "proj"
        shutil.copytree(sample, proj_dir)
        p = Project.open(proj_dir)
        res = render.run_render(p, "DemoParabola", mode="scene", quality="draft")
        assert (proj_dir / "renders" / "DemoParabola" / "draft" / "scene.mp4").exists()
        timing = jsonio.load_json(
            proj_dir / "renders" / "DemoParabola" / "draft" / "timing.json"
        )
        assert len(timing) == 4
        # frame
        res = render.run_render(p, "DemoParabola", mode="frame", beat_id="method", quality="draft")
        draft_dir = proj_dir / "renders" / "DemoParabola" / "draft"
        assert any(draft_dir.glob("frame*")) or any(draft_dir.glob("BmsScene*")) or any(draft_dir.glob("*.png"))
        # beat
        res = render.run_render(p, "DemoParabola", mode="beat", beat_id="result", quality="draft")
        assert (proj_dir / "renders" / "DemoParabola" / "draft" / "beat_result.mp4").exists() or (proj_dir / "renders" / "DemoParabola" / "draft" / "scene.mp4").exists()
