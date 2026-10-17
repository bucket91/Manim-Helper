from __future__ import annotations

import copy

from bms.engine.hashing import beat_hash, settings_hash
from bms.project import DEFAULT_PRONUNCIATION, DEFAULT_SETTINGS


def _settings() -> dict:
    return copy.deepcopy(DEFAULT_SETTINGS)


def _scene() -> dict:
    return {
        "format_version": 1,
        "scene_id": "S",
        "layout": "full",
        "objects": {
            "a": {"type": "axes"},
            "gr": {"type": "function_graph", "axes": "a", "expr": "x**2"},
            "b": {"type": "mathtex", "tex": "x"},
            "other": {"type": "mathtex", "tex": "z"},
        },
        "beats": [
            {
                "id": "b1",
                "narration": "hello",
                "steps": [{"anim": "Create", "targets": ["gr"]}],
            }
        ],
    }


def test_beat_hash_is_stable():
    scene = _scene()
    settings = _settings()
    h1 = beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION)
    h2 = beat_hash(
        copy.deepcopy(scene),
        "b1",
        copy.deepcopy(settings),
        copy.deepcopy(DEFAULT_PRONUNCIATION),
    )
    assert h1 == h2


def test_beat_hash_changes_on_narration():
    scene = _scene()
    settings = _settings()
    h1 = beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION)
    scene["beats"][0]["narration"] = "hellp"
    assert beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION) != h1


def test_beat_hash_changes_on_referenced_object_field():
    scene = _scene()
    settings = _settings()
    h1 = beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION)
    scene["objects"]["gr"]["expr"] = "x**3"
    assert beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION) != h1


def test_beat_hash_changes_on_recursive_reference():
    scene = _scene()
    settings = _settings()
    h1 = beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION)
    # "gr" references "a", so a's fields are included transitively.
    scene["objects"]["a"]["x_range"] = [-5, 5]
    assert beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION) != h1


def test_beat_hash_changes_on_rate():
    scene = _scene()
    h1 = beat_hash(scene, "b1", _settings(), DEFAULT_PRONUNCIATION)
    settings = _settings()
    settings["rate"] = "+30%"
    assert beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION) != h1


def test_beat_hash_ignores_unrelated_object():
    scene = _scene()
    settings = _settings()
    h1 = beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION)
    scene["objects"]["other"]["tex"] = "zzz"
    assert beat_hash(scene, "b1", settings, DEFAULT_PRONUNCIATION) == h1


def test_beat_hash_unknown_beat_raises():
    import pytest

    with pytest.raises(ValueError):
        beat_hash(_scene(), "missing", _settings(), DEFAULT_PRONUNCIATION)


def test_settings_hash_is_stable_and_rate_sensitive():
    settings = _settings()
    h1 = settings_hash(settings, DEFAULT_PRONUNCIATION)
    assert settings_hash(copy.deepcopy(settings), copy.deepcopy(DEFAULT_PRONUNCIATION)) == h1
    changed = _settings()
    changed["rate"] = "+30%"
    assert settings_hash(changed, DEFAULT_PRONUNCIATION) != h1
    changed_pron = copy.deepcopy(DEFAULT_PRONUNCIATION)
    changed_pron["keep_s"] = changed_pron["keep_s"] + ["নতুন"]
    assert settings_hash(settings, changed_pron) != h1
