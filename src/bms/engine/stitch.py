from __future__ import annotations

import os
import tempfile
from pathlib import Path

from bms.engine.hashing import stale_status
from bms.procutil import run_hidden
from bms.project import Project


def _escape_single_quote(value: str) -> str:
    return value.replace("'", "'\\''")


def stitch(project: Project, quality: str, out: Path | None = None) -> Path:
    renders_dir = project.subdir("renders")
    scene_order = list(project.settings.get("scene_order") or project.scene_ids())

    missing: list[str] = []
    videos: list[Path] = []
    for scene_id in scene_order:
        video = renders_dir / scene_id / quality / "scene.mp4"
        try:
            is_stale = bool(stale_status(project, scene_id, quality).get("scene_stale"))
        except Exception:
            is_stale = True
        if not video.exists() or is_stale:
            missing.append(scene_id)
        else:
            videos.append(video)
    if missing:
        raise RuntimeError(
            f"missing or stale scene renders: {', '.join(missing)}"
        )

    output = Path(out) if out else (renders_dir / "_project" / quality / "project.mp4")
    output.parent.mkdir(parents=True, exist_ok=True)

    fd, list_path = tempfile.mkstemp(
        dir=str(output.parent), prefix="concat_", suffix=".txt"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for video in videos:
                handle.write(f"file '{_escape_single_quote(str(video))}'\n")
        run_hidden(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output),
            ]
        )
    finally:
        try:
            os.unlink(list_path)
        except OSError:
            pass
    return output
