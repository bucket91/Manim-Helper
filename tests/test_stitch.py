from __future__ import annotations

import tempfile
from pathlib import Path

from bms.engine import stitch
from bms.project import Project


def test_stitch_list_quotes(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        p = Project.create(Path(d) / "p", "P")
        p.settings["scene_order"] = ["s1"]
        p.save_settings()
        r = p.subdir("renders") / "s1" / "draft"
        r.mkdir(parents=True)
        (r / "scene.mp4").write_bytes(b"fake")

        calls = []

        def fake_run_hidden(cmd):
            calls.append(cmd)
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(stitch, "run_hidden", fake_run_hidden)
        out = stitch.stitch_project(p, quality="draft")
        assert out.exists() or calls
        # find concat list
        assert any("concat" in str(c) for c in calls)
