from __future__ import annotations

import datetime
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

from bms import jsonio
from bms.procutil import popen_hidden
from bms.project import Project, quality_params
from bms.runtime.protocol import parse_line


@dataclass
class RenderResult:
    ok: bool
    exit_code: int
    output: Path | None
    log_path: Path
    errors: List[dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def build_render_spec(
    project: Project,
    scene_id: str,
    quality: str,
    mode: str,
    beat_id: str | None,
    continue_on_error: bool,
    debug: bool,
) -> dict:
    width, height, fps = quality_params(project.settings, quality)
    out_dir = project.subdir("renders") / scene_id / quality
    return {
        "project_root": str(project.root),
        "scene_id": scene_id,
        "mode": mode,
        "beat_id": beat_id,
        "quality": quality,
        "width": width,
        "height": height,
        "fps": fps,
        "out_dir": str(out_dir),
        "continue_on_error": continue_on_error,
        "debug": debug,
    }


def _expected_output(out_dir: Path, mode: str, beat_id: str | None) -> Path:
    if mode == "frame":
        return out_dir / f"frame_{beat_id}.png"
    if mode == "beat":
        return out_dir / f"beat_{beat_id}.mp4"
    return out_dir / "scene.mp4"


def run_render(
    project: Project,
    scene_id: str,
    quality: str,
    mode: str = "scene",
    beat_id: str | None = None,
    continue_on_error: bool = False,
    debug: bool = False,
    on_line: Callable[[str], None] | None = None,
) -> RenderResult:
    spec = build_render_spec(
        project, scene_id, quality, mode, beat_id, continue_on_error, debug
    )
    renders_dir = project.subdir("renders")
    log_dir = project.subdir("logs")
    spec_dir = renders_dir / scene_id / quality
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = (spec_dir / "render_spec.json").resolve()
    jsonio.save_json_atomic(spec_path, spec)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"render_{scene_id}_{ts}.log"
    result = RenderResult(ok=False, exit_code=0, output=None, log_path=log_path)

    proc = popen_hidden(
        [sys.executable, "-m", "bms.runtime.runner", str(spec_path)],
        cwd=project.root,
    )
    try:
        with open(log_path, "w", encoding="utf-8") as logf:
            for line in proc.stdout:
                line_str = (
                    line
                    if isinstance(line, str)
                    else line.decode("utf-8", errors="replace")
                )
                try:
                    logf.write(line_str)
                except Exception:
                    pass
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
                    result.warnings.append(line_str.strip())
        proc.wait()
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
    result.exit_code = proc.returncode if proc.returncode is not None else 1

    output = _expected_output(Path(spec["out_dir"]), mode, beat_id)
    result.output = output if output.exists() else None
    result.ok = result.exit_code == 0
    return result
