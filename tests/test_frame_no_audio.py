from __future__ import annotations

import tempfile
from pathlib import Path
import shutil

import pytest

from bms.engine import render
from bms.project import Project


@pytest.mark.manim
def test_frame_mode_no_audio():
    sample = Path("/home/mhd/Manim-Helper/samples/demo_project")
    with tempfile.TemporaryDirectory() as d:
        proj_dir = Path(d) / "proj"
        shutil.copytree(sample, proj_dir)
        p = Project.open(proj_dir)
        res = render.run_render(p, "DemoParabola", mode="frame", beat_id="method", quality="draft")
        assert res.exit_code == 0
        assert res.ok
