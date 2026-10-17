from __future__ import annotations

from bms.project import Project


def get_timing(project: Project, scene_id: str, quality: str) -> list[dict]:
    renders_dir = project.subdir("renders")
    timing_path = renders_dir / scene_id / quality / "timing.json"
    try:
        from bms import jsonio

        return jsonio.load_json(timing_path)
    except Exception:
        return []
