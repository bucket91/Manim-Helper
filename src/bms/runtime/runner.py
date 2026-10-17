from __future__ import annotations

import json
import sys
import os
from pathlib import Path

from bms import jsonio
from bms.engine.audio import audio_duration, make_audio
from bms.project import Project
from bms.runtime.protocol import emit_error, emit_progress
from bms.schema import format_issue, validate_scene
from manim import config as manim_config
from manim import tempconfig


def _move_outputs(scene_id: str, quality: str, renders_dir: Path) -> None:
    import os
    import shutil
    scene_dir = renders_dir / scene_id / quality
    scene_dir.mkdir(parents=True, exist_ok=True)
    found_mp4 = False
    search_paths = ['.', str(renders_dir.parent.parent), os.getcwd()]
    for sp in search_paths:
        for root, dirs, files in os.walk(sp):
            for f in files:
                if f.endswith('.mp4') and 'BmsScene' in f:
                    src = Path(root) / f
                    dst = scene_dir / 'scene.mp4'
                    try:
                        dst.unlink(missing_ok=True)
                        src.replace(dst)
                        found_mp4 = True
                    except Exception:
                        pass
                    if found_mp4:
                        break
            if found_mp4:
                break
    found_png = False
    for sp in search_paths:
        for root, dirs, files in os.walk(sp):
            for f in files:
                if f.startswith('BmsScene') and f.endswith('.png'):
                    src = Path(root) / f
                    dst = scene_dir / ('frame_' + f.split('_')[-1] if '_' in f else '0.png')
                    try:
                        dst.unlink(missing_ok=True)
                        src.replace(dst)
                        found_png = True
                    except Exception:
                        pass
                    if found_png:
                        break
            if found_png:
                break
    for d in ['media', 'assets', 'videos', 'images', 'partial_movie_files']:
        shutil.rmtree(d, ignore_errors=True)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        emit_error({
            "kind": "other",
            "scene_id": None,
            "beat_id": None,
            "object_id": None,
            "step_index": None,
            "message": "missing render spec path",
        })
        return 2
    spec_path = Path(argv[1])
    try:
        spec = jsonio.load_json(spec_path)
    except Exception as exc:
        emit_error({
            "kind": "other",
            "scene_id": None,
            "beat_id": None,
            "object_id": None,
            "step_index": None,
            "message": f"cannot read spec: {exc}",
        })
        return 2
    project_root = spec.get("project_root")
    scene_id = spec.get("scene_id")
    if not project_root or not scene_id:
        emit_error({
            "kind": "other",
            "scene_id": scene_id,
            "beat_id": None,
            "object_id": None,
            "step_index": None,
            "message": "invalid spec: missing project_root or scene_id",
        })
        return 2
    try:
        project = Project.open(Path(project_root))
        scene_data = project.load_scene(scene_id)
    except Exception as exc:
        emit_error({
            "kind": "other",
            "scene_id": scene_id,
            "beat_id": None,
            "object_id": None,
            "step_index": None,
            "message": f"cannot load scene: {exc}",
        })
        return 2
    issues = validate_scene(scene_data, project.settings)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        for issue in errors:
            emit_error({
                "kind": "other",
                "scene_id": scene_id,
                "beat_id": None,
                "object_id": None,
                "step_index": None,
                "message": format_issue(issue),
            })
        print("BMS_DONE|ok=0")
        sys.stdout.flush()
        return 2
    mode = spec.get("mode", "scene")
    quality = spec.get("quality", "draft")
    beat_id = spec.get("beat_id")
    config = spec.get("manim_config") or {}
    config["output_file"] = "BmsScene"
    manim_config.update(config)
    from bms.runtime import scene  # noqa
    scene.BmsScene.bms_spec = {
        "project_root": str(project_root),
        "scene_id": scene_id,
        "mode": mode,
        "beat_id": beat_id,
        "continue_on_error": bool(spec.get("continue_on_error", False)),
        "debug": bool(spec.get("debug", False)),
    }
    try:
        from manim import tempconfig
        with tempconfig(config):
            scene.BmsScene().render()
    except Exception as exc:
        emit_error({
            "kind": "other",
            "scene_id": scene_id,
            "beat_id": None,
            "object_id": None,
            "step_index": None,
            "message": str(exc)[:2000],
        })
        print("BMS_DONE|ok=0")
        sys.stdout.flush()
        return 1
    renders_dir = project.subdir("renders")
    _move_outputs(scene_id, quality, renders_dir)
    if mode == "scene":
        timing_path = renders_dir / scene_id / quality / "timing.json"
        try:
            from bms.engine import hashing
            timing = getattr(scene.BmsScene, "bms_timing", [])
            jsonio.save_json_atomic(timing_path, timing)
            manifest = {
                "scene_hash": hashing.settings_hash(project.settings, project.pronunciation),
                "beat_ids": [b["id"] for b in (scene_data.get("beats") or []) if isinstance(b, dict)],
                "beats": {},
            }
            for b in manifest["beat_ids"]:
                manifest["beats"][b] = hashing.beat_hash(scene_data, b, project.settings, project.pronunciation)
            jsonio.save_json_atomic(renders_dir / scene_id / quality / "manifest.json", manifest)
        except Exception:
            pass
    print("BMS_DONE|ok=1")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
