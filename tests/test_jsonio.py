from __future__ import annotations

from bms import jsonio


def test_roundtrip_bangla_no_temp(tmp_path):
    path = tmp_path / "scene.json"
    data = {"scene_id": "Demo", "text": "উপকেন্দ্রিক লম্বের দৈর্ঘ্য কত?"}
    jsonio.save_json_atomic(path, data)
    loaded = jsonio.load_json(path)
    assert loaded == data
    assert loaded["text"] == data["text"]

    raw = path.read_text(encoding="utf-8")
    assert "উপকেন্দ্রিক" in raw
    assert "\\u" not in raw

    payload = sorted(p.name for p in tmp_path.iterdir())
    assert payload == ["scene.json"]


def test_unknown_keys_and_order_survive(tmp_path):
    path = tmp_path / "s.json"
    data = {
        "z": 1,
        "a": {"nested": True, "extra": [1, 2, 3]},
        "scene_id": "X",
        "unknown_top": "keep me",
    }
    jsonio.save_json_atomic(path, data)
    loaded = jsonio.load_json(path)
    assert list(loaded.keys()) == ["z", "a", "scene_id", "unknown_top"]
    assert loaded["unknown_top"] == "keep me"
    assert loaded["a"] == {"nested": True, "extra": [1, 2, 3]}


def test_trailing_newline(tmp_path):
    path = tmp_path / "s.json"
    jsonio.save_json_atomic(path, {"k": "v"})
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_canonical_json():
    assert jsonio.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert jsonio.canonical_json({"t": "ন"}) == '{"t":"ন"}'
