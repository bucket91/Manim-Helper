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
