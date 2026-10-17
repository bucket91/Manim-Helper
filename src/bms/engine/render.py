from __future__ import annotations

import datetime
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from bms import jsonio
from bms.engine.hashing import stale_status
from bms.procutil import popen_hidden
from bms.project import Project
from bms.runtime.protocol import parse_line


@dataclass
class RenderResult:
    returncode: int
    errors: List[dict] = field(default_factory=list)
    warnings: List[dict] = field(default_factory=list)
    log_path: Path | None = None


def quality_params(quality: str, final_fps: int) -> dict:
    q = (quality or "draft").lower()
    if q == "final":
        fps = int(final_fps) if final_fps in (30, 60) else 60
        return {
            "quality": "high_quality",
            "progress_bar": "none",
            "frame_rate": fps,
        }
    if q == "medium":
        fps = int(final_fps) if final_fps in (30, 60) else 30
        return {
            "quality": "medium_quality",
            "progress_bar": "none",
            "frame_rate": fps,
        }
    return {
        "quality": "low_quality",
        "progress_bar": "none",
        "frame_rate": 15,
    }


def build_render_spec(
    project: Project,
    scene_id: str,
    mode: str = "scene",
    beat_id: str | None = None,
    quality: str = "draft",
    continue_on_error: bool = False,
    debug: bool = False,
) -> dict:
    spec = {
        "project_root": str(project.root),
        "scene_id": scene_id,
        "mode": mode,
        "beat_id": beat_id,
        "quality": quality,
        "continue_on_error": continue_on_error,
        "debug": debug,
        "narrate": project.settings.get("narrate", True),
        "manim_config": {},
    }
    params = quality_params(quality, project.settings.get("final_fps", 30))
    spec["manim_config"] = params
    if mode == "frame" and beat_id is not None:
        spec["manim_config"]["save_last_frame"] = True
    return spec


def run_render(
    project: Project,
    scene_id: str,
    mode: str = "scene",
    beat_id: str | None = None,
    quality: str = "draft",
    continue_on_error: bool = False,
    debug: bool = False,
    on_line: Callable[[str], None] | None = None,
) -> RenderResult:
    spec = build_render_spec(
        project, scene_id, mode, beat_id, quality, continue_on_error, debug
    )
    renders_dir = project.subdir("renders")
    log_dir = project.subdir("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    spec_dir = renders_dir / scene_id / quality
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / "render_spec.json"
    jsonio.save_json_atomic(spec_path, spec)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"render_{scene_id}_{ts}.log"
    result = RenderResult(returncode=0, log_path=log_path)

    proc = popen_hidden(
        [sys.executable, "-m", "bms.runtime.runner", str(spec_path)],
        cwd=project.root,
    )
    try:
        with open(log_path, "w", encoding="utf-8") as logf:
            for line in proc.stdout:
                try:
                    logf.write(line)
                except Exception:
                    pass
                line_str = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
                if on_line:
                    try:
                        on_line(line_str)
                    except Exception:
                        pass
                parsed = parse_line(line_str)
                if parsed is None:
                    continue
                if parsed.get("type") == "error":
                    result.errors.append(parsed.get("error") or {})
                elif parsed.get("type") == "warn":
                    kind = parsed.get("kind", "unknown")
                    fields = parsed.get("fields") or {}
                    result.warnings.append({"kind": kind, "fields": fields})
        proc.wait()
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
    result.returncode = proc.returncode
    return result
