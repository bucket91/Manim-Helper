from __future__ import annotations

from bms import jsonio
from bms.project import Project


def get_timing(project: Project, scene_id: str, quality: str) -> dict:
    renders_dir = project.subdir("renders")
    timing_path = renders_dir / scene_id / quality / "timing.json"
    try:
        data = jsonio.load_json(timing_path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
