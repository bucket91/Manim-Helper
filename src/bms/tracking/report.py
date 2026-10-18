from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from bms import __version__


def _write_text(path: Path, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def build_report(project, changes: list, now=None) -> str:
    if isinstance(now, str):
        export_time = now
    elif now is None:
        export_time = datetime.now().isoformat(timespec="seconds")
    else:
        try:
            export_time = datetime.fromisoformat(str(now)).isoformat(timespec="seconds")
        except Exception:
            export_time = datetime.now().isoformat(timespec="seconds")

    by_scene: dict[str, list] = {}
    for ch in changes:
        sid = ch.scene_id if hasattr(ch, "scene_id") else (ch.get("scene_id") if isinstance(ch, dict) else None)
        if sid is None:
            continue
        by_scene.setdefault(sid, []).append(ch)

    n_narr = sum(1 for ch in changes if (getattr(ch, "kind", None) == "narration" or (isinstance(ch, dict) and ch.get("kind") == "narration")))
    n_obj = sum(1 for ch in changes if (getattr(ch, "kind", None) == "object" or (isinstance(ch, dict) and ch.get("kind") == "object")))

    try:
        from bms.tracking import diff as diff_mod

        struct = diff_mod.structure_changes(project)
        patterns = diff_mod.find_patterns(changes)
    except Exception:
        struct = []
        patterns = []

    try:
        proj_name = project.settings.get("name", "")
    except Exception:
        proj_name = ""

    scene_order = list(project.scene_ids())
    for sid in by_scene:
        if sid not in scene_order:
            scene_order.append(sid)

    clean: list[str] = []
    clean.append("# Changes report")
    clean.append(f"Project: {proj_name} | Exported: {export_time} | bms {__version__}")
    clean.append(f"Summary: {n_narr} narration, {n_obj} on-screen, {len(struct)} structure notes")
    clean.append("")

    for sid in scene_order:
        chs = by_scene.get(sid)
        if not chs:
            continue
        narr_ch = []
        obj_ch = []
        for ch in chs:
            k = getattr(ch, "kind", None) or (ch.get("kind") if isinstance(ch, dict) else None)
            if k == "narration":
                narr_ch.append(ch)
            elif k == "object":
                obj_ch.append(ch)
        try:
            cur = project.load_scene(sid)
        except Exception:
            cur = {}
        beat_order = []
        cur_beats = cur.get("beats") if isinstance(cur, dict) else []
        if isinstance(cur_beats, list):
            for b in cur_beats:
                if isinstance(b, dict) and b.get("id") is not None:
                    beat_order.append(str(b["id"]))
        beat_pos = {bid: i for i, bid in enumerate(beat_order)}
        narr_ch.sort(key=lambda c: beat_pos.get(getattr(c, "beat_id", None) or (c.get("beat_id") if isinstance(c, dict) else None), 10**9))
        obj_order_cur = list(cur.get("objects", {}).keys()) if isinstance(cur, dict) and isinstance(cur.get("objects"), dict) else []
        obj_pos = {oid: i for i, oid in enumerate(obj_order_cur)}
        obj_ch_sorted = sorted(obj_ch, key=lambda c: (
            obj_pos.get(getattr(c, "object_id", None) or (c.get("object_id") if isinstance(c, dict) else ""), 10**9),
            getattr(c, "field", None) or (c.get("field") if isinstance(c, dict) else ""),
        ))
        clean.append(f"## {sid}")
        try:
            from bms.tracking import baseline as baseline_mod

            reasons = baseline_mod.load_reasons(project)
        except Exception:
            reasons = {}
        for ch in narr_ch:
            bid = getattr(ch, "beat_id", None) or (ch.get("beat_id") if isinstance(ch, dict) else "")
            before = getattr(ch, "before", "") or (ch.get("before") if isinstance(ch, dict) else "")
            after = getattr(ch, "after", "") or (ch.get("after") if isinstance(ch, dict) else "")
            key = getattr(ch, "key", None) or (ch.get("key") if isinstance(ch, dict) else f"{sid}|narration|{bid}")
            clean.append(f"### Narration · beat `{bid}`")
            clean.append(f"- before: {before}")
            clean.append(f"- after: {after}")
            r = reasons.get(key) if isinstance(reasons, dict) else None
            if r:
                clean.append(f"- reason: {r}")
            clean.append("")
        for ch in obj_ch_sorted:
            oid = getattr(ch, "object_id", None) or (ch.get("object_id") if isinstance(ch, dict) else "")
            otype = getattr(ch, "object_type", None) or (ch.get("object_type") if isinstance(ch, dict) else "")
            field = getattr(ch, "field", None) or (ch.get("field") if isinstance(ch, dict) else "")
            before = getattr(ch, "before", "") or (ch.get("before") if isinstance(ch, dict) else "")
            after = getattr(ch, "after", "") or (ch.get("after") if isinstance(ch, dict) else "")
            clean.append(f"### On-screen · `{oid}` ({otype}) · field `{field}`")
            clean.append(f"- before: {before}")
            clean.append(f"- after: {after}")
            clean.append("")

    if patterns:
        clean.append("## Repeated patterns")
        for p in patterns:
            before_span = p.get("before", "")
            after_span = p.get("after", "")
            count = p.get("count", 0)
            scenes = p.get("scenes", [])
            scenes_str = ", ".join(scenes)
            clean.append(f'- "{before_span}" → "{after_span}" ×{count} (scenes: {scenes_str})')
        clean.append("")

    if struct:
        clean.append("## Structure notes")
        for s in struct:
            clean.append(f"- {s}")
        clean.append("")

    result = "\n".join(clean)
    if not result.endswith("\n"):
        result += "\n"
    return result


def export_report(project, mark: bool = True) -> Path:
    try:
        from bms.tracking import diff as diff_mod

        changes = diff_mod.compute_changes(project)
    except Exception:
        changes = []
    if not changes:
        latest = project.root / "reports" / "latest.md"
        if latest.exists():
            return latest
        raise ValueError("no changes")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_path = project.root / "reports" / f"report_{ts}.md"
    latest = project.root / "reports" / "latest.md"
    ts_path.parent.mkdir(parents=True, exist_ok=True)
    text = build_report(project, changes, now=datetime.now().isoformat(timespec="seconds"))
    try:
        _write_text(ts_path, text)
        _write_text(latest, text)
    except Exception:
        raise
    if mark:
        scenes_with_changes = sorted({c.scene_id if hasattr(c, "scene_id") else (c.get("scene_id") if isinstance(c, dict) else None) for c in changes if c is not None})
        scenes_with_changes = [s for s in scenes_with_changes if s]
        try:
            from bms.tracking import baseline as baseline_mod

            baseline_mod.mark_reported(project, scenes_with_changes if scenes_with_changes else None)
            reasons = baseline_mod.load_reasons(project)
            cur_keys = set()
            for ch in diff_mod.compute_changes(project):
                k = getattr(ch, "key", None) or (ch.get("key") if isinstance(ch, dict) else None)
                if k:
                    cur_keys.add(k)
            changed_r = False
            for k in list(reasons.keys()):
                if k not in cur_keys:
                    reasons.pop(k, None)
                    changed_r = True
            if changed_r:
                from bms import jsonio

                jsonio.save_json_atomic(project.root / ".bms" / "reasons.json", reasons)
        except Exception:
            pass
    return ts_path
