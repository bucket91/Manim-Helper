from __future__ import annotations

import json
from pathlib import Path

from bms import __version__
from bms.project import Project
from bms.schema import registry
from bms.tracking import baseline, diff, report


def _make_min_scene(path: Path, scene_id: str, narration: list[str | None]):
    scene = {
        "format_version": 1,
        "scene_id": scene_id,
        "title": scene_id,
        "layout": "center",
        "beats": [],
        "objects": {},
    }
    for i, n in enumerate(narration):
        scene["beats"].append({"id": f"b{i:02d}", "narration": n})
    import json as _json

    path.write_text(_json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return scene


def test_narration_edit_creates_change(tmp_path):
    proj = Project.create(tmp_path, "P")
    src = tmp_path / "s.scene.json"
    _make_min_scene(src, "S", ["hello", "world"])
    proj.import_scene(src)
    # edit
    s = proj.load_scene("S")
    s["beats"][0]["narration"] = "hi"
    proj.save_scene("S", s)
    changes = diff.compute_changes(proj)
    assert len(changes) == 1
    assert changes[0].key == "S|narration|b00"


def test_object_edits_two_fields(tmp_path):
    proj = Project.create(tmp_path, "P")
    src = tmp_path / "q.scene.json"
    scene = {
        "format_version": 1,
        "scene_id": "Q",
        "title": "Q",
        "layout": "center",
        "beats": [{"id": "b00", "steps": []}],
        "objects": {
            "panel": {
                "type": "question_panel",
                "num": 1,
                "qmath": "x^2",
                "qtext": "solve",
                "options": [
                    {"value": "a"},
                    {"value": "b"},
                    {"value": "c"},
                    {"value": "d"},
                ],
            }
        },
    }
    src.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    proj.import_scene(src)
    # edit options[2] and qmath
    s = proj.load_scene("Q")
    s["objects"]["panel"]["options"][2]["value"] = "C"
    s["objects"]["panel"]["qmath"] = "x^3"
    proj.save_scene("Q", s)
    changes = diff.compute_changes(proj)
    # two object text field changes
    assert len(changes) == 2
    keys = {c.key for c in changes}
    assert "Q|object|panel|options[2].value" in keys
    assert "Q|object|panel|qmath" in keys


def test_unchanged_scene_no_changes(tmp_path):
    proj = Project.create(tmp_path, "P")
    src = tmp_path / "s.scene.json"
    _make_min_scene(src, "S", ["a", "b"])
    proj.import_scene(src)
    assert diff.compute_changes(proj) == []


def test_nfc_does_not_create_change(tmp_path):
    proj = Project.create(tmp_path, "P")
    src = tmp_path / "s.scene.json"
    _make_min_scene(src, "S", ["\u00e0"])  # a with grave
    proj.import_scene(src)
    s = proj.load_scene("S")
    s["beats"][0]["narration"] = "a\u0300"  # decomposed same char
    proj.save_scene("S", s)
    assert diff.compute_changes(proj) == []


def test_pattern_counts_across_beats(tmp_path):
    proj = Project.create(tmp_path, "P")
    src = tmp_path / "s.scene.json"
    # 4 beats with same narration change
    _make_min_scene(src, "S", ["সরালে", "সরালে", "সরালে", "সরালে"])
    proj.import_scene(src)
    s = proj.load_scene("S")
    for b in s["beats"]:
        b["narration"] = "সরল করলে"
    proj.save_scene("S", s)
    changes = diff.compute_changes(proj)
    assert len(changes) == 4
    pats = diff.find_patterns(changes)
    # one pattern with count 4
    assert len(pats) == 1
    assert pats[0]["count"] == 4


def test_build_report_includes_injected_now(tmp_path):
    proj = Project.create(tmp_path, "P")
    src = tmp_path / "s.scene.json"
    _make_min_scene(src, "S", ["a"])
    proj.import_scene(src)
    s = proj.load_scene("S")
    s["beats"][0]["narration"] = "b"
    proj.save_scene("S", s)
    changes = diff.compute_changes(proj)
    text = report.build_report(proj, changes, now="2025-10-01T12:00:00")
    assert "Exported: 2025-10-01T12:00:00" in text
    assert f"bms {__version__}" in text


def test_export_mark_keeps_original_and_clears_changes(tmp_path):
    proj = Project.create(tmp_path, "P")
    src = tmp_path / "s.scene.json"
    _make_min_scene(src, "S", ["a"])
    proj.import_scene(src)
    s = proj.load_scene("S")
    s["beats"][0]["narration"] = "b"
    proj.save_scene("S", s)
    orig = proj.root / ".bms" / "original" / "S.json"
    orig_before = orig.read_bytes()
    out = report.export_report(proj, mark=True)
    assert out.exists()
    assert orig.read_bytes() == orig_before
    # next changes should be empty
    assert diff.compute_changes(proj) == []


def test_failed_write_leaves_baseline_unmarked(tmp_path, monkeypatch):
    proj = Project.create(tmp_path, "P")
    src = tmp_path / "s.scene.json"
    _make_min_scene(src, "S", ["a"])
    proj.import_scene(src)
    # baseline now equals current
    base_before = (proj.root / ".bms" / "baseline" / "S.json").read_bytes()
    s = proj.load_scene("S")
    s["beats"][0]["narration"] = "b"
    proj.save_scene("S", s)
    # monkeypatch Path.write_text to raise
    from pathlib import Path as _Path

    def boom(self, *a, **k):
        raise IOError("no disk")

    monkeypatch.setattr(_Path, "write_text", boom)
    try:
        report.export_report(proj, mark=True)
    except IOError:
        pass
    # baseline should remain unchanged (unmarked)
    assert (proj.root / ".bms" / "baseline" / "S.json").read_bytes() == base_before
