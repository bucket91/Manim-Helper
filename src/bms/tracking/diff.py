from __future__ import annotations

import difflib
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

from bms.schema import registry


@dataclass(frozen=True)
class Change:
    key: str
    scene_id: str
    kind: str  # "narration" or "object"
    beat_id: str | None = None
    object_id: str | None = None
    object_type: str | None = None
    field: str | None = None
    before: str = ""
    after: str = ""


def _nfc(s: Any) -> Any:
    if isinstance(s, str):
        return unicodedata.normalize("NFC", s)
    return s


def _norm(s: Any) -> Any:
    return _nfc(s)


def compute_changes(project, scene_id: str | None = None) -> list[Change]:
    results: list[Change] = []
    scene_ids = [scene_id] if scene_id else list(project.scene_ids())
    for sid in scene_ids:
        try:
            from bms.tracking import baseline as baseline_mod

            baseline = baseline_mod.load_baseline(project, sid)
        except Exception:
            baseline = None
        if not isinstance(baseline, dict):
            baseline = None
        try:
            current = project.load_scene(sid)
        except Exception:
            continue
        if baseline is None:
            continue  # no baseline, so no changes to report against last reported

        def beat_map(beats):
            m = {}
            if isinstance(beats, list):
                for b in beats:
                    if isinstance(b, dict) and b.get("id") is not None:
                        m[str(b["id"])] = b
            return m

        bm = beat_map(baseline.get("beats") if isinstance(baseline, dict) else [])
        cm = beat_map(current.get("beats") if isinstance(current, dict) else [])
        cur_beats = current.get("beats") if isinstance(current, dict) else []
        for b in cur_beats if isinstance(cur_beats, list) else []:
            if not isinstance(b, dict) or b.get("id") is None:
                continue
            bid = str(b["id"])
            bb = bm.get(bid)
            if not isinstance(bb, dict):
                continue  # present in only one -> structure note
            bn_cur = b.get("narration")
            bn_base = bb.get("narration")
            if isinstance(bn_cur, str) and isinstance(bn_base, str):
                if _norm(bn_cur) != _norm(bn_base):
                    key = f"{sid}|narration|{bid}"
                    results.append(
                        Change(
                            key=key,
                            scene_id=sid,
                            kind="narration",
                            beat_id=bid,
                            object_id=None,
                            object_type=None,
                            field=None,
                            before=bn_base,
                            after=bn_cur,
                        )
                    )

        base_objs = baseline.get("objects") if isinstance(baseline, dict) else {}
        cur_objs = current.get("objects") if isinstance(current, dict) else {}
        if not isinstance(base_objs, dict):
            base_objs = {}
        if not isinstance(cur_objs, dict):
            cur_objs = {}
        for obj_id in sorted(cur_objs.keys()):
            if not isinstance(obj_id, str):
                continue
            cur_obj = cur_objs.get(obj_id)
            base_obj = base_objs.get(obj_id)
            if not isinstance(cur_obj, dict) or not isinstance(base_obj, dict):
                continue  # present in only one
            cur_type = cur_obj.get("type")
            base_type = base_obj.get("type")
            if cur_type != base_type:
                continue
            cur_fields = registry.iter_text_fields(cur_obj)
            base_fields_map = {p: v for p, v in registry.iter_text_fields(base_obj)}
            for path, cur_val in cur_fields:
                if path not in base_fields_map:
                    continue
                base_val = base_fields_map[path]
                if _norm(cur_val) != _norm(base_val):
                    key = f"{sid}|object|{obj_id}|{path}"
                    results.append(
                        Change(
                            key=key,
                            scene_id=sid,
                            kind="object",
                            beat_id=None,
                            object_id=obj_id,
                            object_type=cur_type if isinstance(cur_type, str) else None,
                            field=path,
                            before=str(base_val),
                            after=str(cur_val),
                        )
                    )
    return results


def structure_changes(project) -> list[str]:
    notes: list[str] = []
    for sid in list(project.scene_ids()):
        try:
            current = project.load_scene(sid)
        except Exception:
            continue
        try:
            from bms.tracking import baseline as baseline_mod

            baseline = baseline_mod.load_baseline(project, sid)
        except Exception:
            baseline = None
        if not isinstance(baseline, dict):
            continue

        def beat_ids(beats):
            ids = []
            if isinstance(beats, list):
                for b in beats:
                    if isinstance(b, dict) and b.get("id") is not None:
                        ids.append(str(b["id"]))
            return ids

        b_cur = set(beat_ids(current.get("beats") if isinstance(current, dict) else []))
        b_base = set(beat_ids(baseline.get("beats") if isinstance(baseline, dict) else []))
        for bid in b_base - b_cur:
            notes.append(f"{sid}: beat '{bid}' removed")
        for bid in b_cur - b_base:
            notes.append(f"{sid}: beat '{bid}' added")

        def obj_ids(objs):
            ids = []
            if isinstance(objs, dict):
                for oid in objs.keys():
                    if isinstance(oid, str):
                        ids.append(oid)
            return ids

        o_cur = set(obj_ids(current.get("objects") if isinstance(current, dict) else {}))
        o_base = set(obj_ids(baseline.get("objects") if isinstance(baseline, dict) else {}))
        for oid in o_base - o_cur:
            notes.append(f"{sid}: object '{oid}' removed")
        for oid in o_cur - o_base:
            notes.append(f"{sid}: object '{oid}' added")
    return notes


def find_patterns(changes: list) -> list[dict]:
    patterns_map: dict[tuple[str, str], dict[str, Any]] = {}
    for ch in changes:
        a = ch.before if hasattr(ch, "before") else (ch.get("before") if isinstance(ch, dict) else "")
        b = ch.after if hasattr(ch, "after") else (ch.get("after") if isinstance(ch, dict) else "")
        if not isinstance(a, str) or not isinstance(b, str):
            continue
        a_tok = a.split()
        b_tok = b.split()
        sm = difflib.SequenceMatcher(None, a_tok, b_tok)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op in ("replace", "delete", "insert"):
                before_span = " ".join(a_tok[i1:i2]) if i1 < i2 else ""
                after_span = " ".join(b_tok[j1:j2]) if j1 < j2 else ""
                key = (before_span, after_span)
                if key not in patterns_map:
                    patterns_map[key] = {
                        "before": before_span,
                        "after": after_span,
                        "count": 0,
                        "scenes": [],
                    }
                patterns_map[key]["count"] += 1
                sid = ch.scene_id if hasattr(ch, "scene_id") else (ch.get("scene_id") if isinstance(ch, dict) else None)
                if sid and sid not in patterns_map[key]["scenes"]:
                    patterns_map[key]["scenes"].append(sid)
    out: list[dict] = []
    for info in patterns_map.values():
        if info["count"] >= 2:
            scenes = sorted(set(info["scenes"]))
            info["scenes"] = scenes
            out.append(info)
    out.sort(key=lambda x: (-x["count"], x["before"], x["after"]))
    return out
