from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from bms import jsonio


def _reasons_path(project) -> Path:
    return project.root / ".bms" / "reasons.json"


def _baseline_path(project, scene_id: str) -> Path:
    return project.subdir(".bms/baseline") / f"{scene_id}.json"


def _original_path(project, scene_id: str) -> Path:
    return project.subdir(".bms/original") / f"{scene_id}.json"


def load_reasons(project) -> dict[str, str]:
    path = _reasons_path(project)
    try:
        data = jsonio.load_json(path)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            result[k] = v
    return result


def save_reason(project, key: str, reason: str) -> None:
    data = load_reasons(project)
    if not reason:
        if key in data:
            data.pop(key, None)
        jsonio.save_json_atomic(_reasons_path(project), data)
        return
    data[key] = reason
    jsonio.save_json_atomic(_reasons_path(project), data)


def load_baseline(project, scene_id: str) -> dict | None:
    path = _baseline_path(project, scene_id)
    if not path.exists():
        return None
    try:
        data = jsonio.load_json(path)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def init_baseline(project, scene_id: str) -> None:
    # Always writes baseline = current scene; writes original only if missing
    try:
        current = project.load_scene(scene_id)
    except Exception:
        return  # no-op if scene file missing
    baseline_path = _baseline_path(project, scene_id)
    original_path = _original_path(project, scene_id)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.parent.mkdir(parents=True, exist_ok=True)
    jsonio.save_json_atomic(baseline_path, current)
    if not original_path.exists():
        jsonio.save_json_atomic(original_path, current)


def mark_reported(project, scene_ids: list[str] | None = None) -> None:
    if scene_ids is None:
        scene_ids = list(project.scene_ids())
    # Update baseline to current for those scenes and clear reasons for their keys
    reasons = load_reasons(project)
    changed = False
    for scene_id in scene_ids:
        try:
            current = project.load_scene(scene_id)
        except Exception:
            continue
        baseline_path = _baseline_path(project, scene_id)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        jsonio.save_json_atomic(baseline_path, current)
        # clear reasons whose key starts with scene_id + "|"
        prefix = f"{scene_id}|"
        for k in list(reasons.keys()):
            if k.startswith(prefix):
                reasons.pop(k, None)
                changed = True
    if changed:
        jsonio.save_json_atomic(_reasons_path(project), reasons)
    else:
        # still ensure reasons file exists with no stale scene-specific keys? but no scene changed; however clear scene_ids' keys if any
        prefix_any = None
        for scene_id in scene_ids:
            prefix = f"{scene_id}|"
            for k in list(reasons.keys()):
                if k.startswith(prefix):
                    reasons.pop(k, None)
                    changed = True
        if changed:
            jsonio.save_json_atomic(_reasons_path(project), reasons)
