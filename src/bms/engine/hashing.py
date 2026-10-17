from __future__ import annotations

import hashlib

from bms import jsonio
from bms.schema.registry import object_refs

_HASH_SETTINGS_KEYS: tuple[str, ...] = (
    "voice",
    "rate",
    "font_bn",
    "pad",
    "narrate",
    "bangla_numerals_on_screen",
    "default_run_time",
)


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _settings_subset(settings: dict) -> dict:
    if not isinstance(settings, dict):
        settings = {}
    return {key: settings.get(key) for key in _HASH_SETTINGS_KEYS}


def _find_beat(scene: dict, beat_id: str) -> dict:
    beats = scene.get("beats") if isinstance(scene, dict) else None
    if isinstance(beats, list):
        for beat in beats:
            if isinstance(beat, dict) and beat.get("id") == beat_id:
                return beat
    raise ValueError(f"unknown beat id: {beat_id!r}")


def _step_referenced_ids(step: dict) -> list[str]:
    ids: list[str] = []
    if not isinstance(step, dict):
        return ids
    for key in ("targets", "adds", "removes"):
        values = step.get(key)
        if isinstance(values, list):
            ids.extend(value for value in values if isinstance(value, str))
    return ids


def _referenced_objects(scene: dict, beat: dict) -> dict:
    objects = scene.get("objects") if isinstance(scene, dict) else None
    if not isinstance(objects, dict):
        objects = {}
    referenced: dict[str, dict] = {}
    stack: list[str] = []
    steps = beat.get("steps") if isinstance(beat, dict) else None
    if isinstance(steps, list):
        for step in steps:
            stack.extend(_step_referenced_ids(step))
    while stack:
        obj_id = stack.pop()
        if obj_id in referenced:
            continue
        obj = objects.get(obj_id)
        if not isinstance(obj, dict):
            continue
        referenced[obj_id] = obj
        stack.extend(object_refs(obj))
    return referenced


def beat_hash(scene: dict, beat_id: str, settings: dict, pron: dict) -> str:
    beat = _find_beat(scene, beat_id)
    payload = {
        "beat": beat,
        "objects": _referenced_objects(scene, beat),
        "layout": scene.get("layout") if isinstance(scene, dict) else None,
        "background": scene.get("background") if isinstance(scene, dict) else None,
        "settings": _settings_subset(settings),
        "pron": pron,
    }
    return _sha1(jsonio.canonical_json(payload))


def settings_hash(settings: dict, pron: dict) -> str:
    payload = {"settings": _settings_subset(settings), "pron": pron}
    return _sha1(jsonio.canonical_json(payload))



def stale_status(project, scene_id: str, quality: str) -> dict:
    from bms import jsonio

    scene = project.load_scene(scene_id)
    renders_dir = project.subdir("renders")
    scene_render_dir = renders_dir / scene_id / quality
    manifest_path = scene_render_dir / "manifest.json"
    video_path = scene_render_dir / "scene.mp4"
    result: dict = {"scene_stale": True, "beats": {}}
    beats_list = scene.get("beats") if isinstance(scene, dict) else []
    beat_ids = []
    if isinstance(beats_list, list):
        for b in beats_list:
            if isinstance(b, dict) and b.get("id"):
                beat_ids.append(str(b["id"]))
    result["beats"] = {bid: True for bid in beat_ids}
    if not manifest_path.exists() or not video_path.exists():
        return result
    try:
        manifest = jsonio.load_json(manifest_path)
    except Exception:
        return result
    if manifest.get("scene_hash") != settings_hash(project.settings, project.pronunciation):
        return result
    if list(manifest.get("beat_ids") or []) != list(beat_ids):
        return result
    result["scene_stale"] = False
    beats_manifest = manifest.get("beats") or {}
    for bid in beat_ids:
        try:
            bh = beat_hash(scene, bid, project.settings, project.pronunciation)
        except Exception:
            result["beats"][bid] = True
            continue
        result["beats"][bid] = beats_manifest.get(bid) != bh
    return result
