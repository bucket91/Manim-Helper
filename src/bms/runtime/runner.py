from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

from bms import jsonio
from bms.engine import hashing
from bms.project import Project
from bms.runtime.protocol import emit_error, emit_warn
from bms.schema import format_issue, validate_scene
from manim import tempconfig


def _newest(media_dir: Path, suffix: str) -> Path | None:
    best: Path | None = None
    for path in media_dir.rglob(f"*{suffix}"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if best is None or mtime > best.stat().st_mtime:
            best = path
    return best


def _dest_path(out_dir: Path, mode: str, beat_id: str | None) -> Path:
    if mode == "frame":
        return out_dir / f"frame_{beat_id}.png"
    if mode == "beat":
        return out_dir / f"beat_{beat_id}.mp4"
    return out_dir / "scene.mp4"


def _locate_output(scene, mode: str, media_dir: Path) -> Path | None:
    file_writer = getattr(scene.renderer, "file_writer", None)
    if file_writer is not None:
        attr = "image_file_path" if mode == "frame" else "movie_file_path"
        try:
            raw = getattr(file_writer, attr)
        except Exception:
            raw = None
        if raw is not None:
            candidate = Path(raw)
            if candidate.exists():
                return candidate
    return _newest(media_dir, ".png" if mode == "frame" else ".mp4")


def _write_or_warn(path: Path, data: dict) -> None:
    try:
        jsonio.save_json_atomic(path, data)
    except Exception:
        emit_warn("write_failed", file=path.name)


def _finish(ok: bool, code: int) -> int:
    print(f"BMS_DONE|ok={1 if ok else 0}")
    sys.stdout.flush()
    return code


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        emit_error(
            {
                "kind": "other",
                "scene_id": None,
                "beat_id": None,
                "object_id": None,
                "step_index": None,
                "message": "missing render spec path",
            }
        )
        return _finish(False, 2)
    spec_path = Path(argv[1])
    try:
        spec = jsonio.load_json(spec_path)
    except Exception as exc:
        emit_error(
            {
                "kind": "other",
                "scene_id": None,
                "beat_id": None,
                "object_id": None,
                "step_index": None,
                "message": f"cannot read spec: {exc}",
            }
        )
        return _finish(False, 2)

    project_root = spec.get("project_root")
    scene_id = spec.get("scene_id")
    if not project_root or not scene_id:
        emit_error(
            {
                "kind": "other",
                "scene_id": scene_id,
                "beat_id": None,
                "object_id": None,
                "step_index": None,
                "message": "invalid spec: missing project_root or scene_id",
            }
        )
        return _finish(False, 2)

    try:
        project = Project.open(Path(project_root))
        scene_data = project.load_scene(scene_id)
    except Exception as exc:
        emit_error(
            {
                "kind": "other",
                "scene_id": scene_id,
                "beat_id": None,
                "object_id": None,
                "step_index": None,
                "message": f"cannot load scene: {exc}",
            }
        )
        return _finish(False, 2)

    issues = validate_scene(scene_data, project.settings)
    errors = [issue for issue in issues if issue.level == "error"]
    if errors:
        for issue in errors:
            emit_error(
                {
                    "kind": "other",
                    "scene_id": scene_id,
                    "beat_id": None,
                    "object_id": None,
                    "step_index": None,
                    "message": format_issue(issue),
                }
            )
        return _finish(False, 2)

    mode = spec.get("mode", "scene")
    quality = spec.get("quality", "draft")
    beat_id = spec.get("beat_id")
    width = int(spec.get("width", 854))
    height = int(spec.get("height", 480))
    fps = int(spec.get("fps", 15))
    out_dir = Path(spec.get("out_dir") or (project.subdir("renders") / scene_id / quality))
    out_dir.mkdir(parents=True, exist_ok=True)
    media_dir = out_dir / "_media"

    config = {
        "pixel_width": width,
        "pixel_height": height,
        "frame_rate": fps,
        "media_dir": str(media_dir),
        "output_file": "BmsScene",
        "verbosity": "WARNING",
        "disable_caching": False,
        "save_last_frame": mode == "frame",
    }

    from bms.runtime import scene as scene_module  # noqa: PLC0415

    try:
        with tempconfig(config):
            bms_scene = scene_module.BmsScene()
            bms_scene.bms_spec = dict(spec)
            bms_scene.render()
    except Exception as exc:
        emit_error(
            {
                "kind": "other",
                "scene_id": scene_id,
                "beat_id": beat_id,
                "object_id": None,
                "step_index": None,
                "message": str(exc)[:2000],
            }
        )
        return _finish(False, 2)

    source = _locate_output(bms_scene, mode, media_dir)
    if source is not None:
        dest = _dest_path(out_dir, mode, beat_id)
        try:
            os.replace(source, dest)
        except Exception:
            emit_warn("write_failed", file=dest.name)

    if mode == "scene":
        timing_beats = [
            beat
            for beat in getattr(scene_module.BmsScene, "bms_timing", [])
            if isinstance(beat, dict)
        ]
        timing = {
            "scene_id": scene_id,
            "quality": quality,
            "fps": fps,
            "beats": [
                {
                    "id": beat.get("id"),
                    "start": round(float(beat.get("start", 0.0)), 3),
                    "end": round(float(beat.get("end", 0.0)), 3),
                }
                for beat in timing_beats
            ],
            "total": (
                round(float(timing_beats[-1].get("end", 0.0)), 3)
                if timing_beats
                else 0.0
            ),
        }
        _write_or_warn(out_dir / "timing.json", timing)

        beat_ids = [
            str(beat["id"])
            for beat in (scene_data.get("beats") or [])
            if isinstance(beat, dict) and beat.get("id") is not None
        ]
        manifest = {
            "rendered_at": datetime.datetime.now().astimezone().isoformat(),
            "settings_hash": hashing.settings_hash(
                project.settings, project.pronunciation
            ),
            "beat_hashes": {
                beat_id_: hashing.beat_hash(
                    scene_data, beat_id_, project.settings, project.pronunciation
                )
                for beat_id_ in beat_ids
            },
        }
        _write_or_warn(out_dir / "manifest.json", manifest)

    return _finish(True, 0)


if __name__ == "__main__":
    try:
        _code = main(sys.argv)
    except SystemExit:
        raise
    except BaseException as _exc:  # noqa: BLE001
        emit_error(
            {
                "kind": "other",
                "scene_id": None,
                "beat_id": None,
                "object_id": None,
                "step_index": None,
                "message": f"runner crashed: {_exc}",
            }
        )
        print("BMS_DONE|ok=0")
        _code = 2
    raise SystemExit(_code)
