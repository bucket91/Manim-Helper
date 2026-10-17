from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List

from bms.procutil import run_hidden
from bms.project import Project


def _escape_single_quote(s: str) -> str:
    return s.replace("'", "'\\''")


def stitch_project(
    project: Project,
    quality: str = "draft",
    output: Path | None = None,
) -> Path:
    renders_dir = project.subdir("renders")
    scene_order = project.settings.get("scene_order") or project.scene_ids()
    missing = []
    for sid in scene_order:
        video = renders_dir / sid / quality / "scene.mp4"
        if not video.exists():
            missing.append(sid)
    if missing:
        raise RuntimeError(f"missing renders for scenes: {', '.join(missing)}")

    out = Path(output) if output else (renders_dir / "_project" / quality / "project.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    fd, list_path = tempfile.mkstemp(
        dir=str(out.parent), prefix="concat_", suffix=".txt"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for sid in scene_order:
                video = renders_dir / sid / quality / "scene.mp4"
                fh.write(f"file '{_escape_single_quote(str(video))}'\n")
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
                str(out),
            ]
        )
    finally:
        try:
            os.unlink(list_path)
        except OSError:
            pass
    return out
