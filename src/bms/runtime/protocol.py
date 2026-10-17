from __future__ import annotations

import json
from typing import Any


def _clean(value: Any) -> str:
    text = str(value)
    return text.replace("|", "/").replace("\n", " ").replace("\r", " ")


def emit_progress(beat_id: str, index: int, total: int) -> str:
    line = f"BMS_PROGRESS|beat={beat_id}|index={index}|total={total}"
    print(line, flush=True)
    return line


def emit_warn(kind: str, **fields: Any) -> str:
    parts = [f"BMS_WARN|{_clean(kind)}"]
    for key, value in fields.items():
        parts.append(f"{_clean(key)}={_clean(value)}")
    line = "|".join(parts)
    print(line, flush=True)
    return line


def emit_error(error: dict) -> str:
    line = "BMS_ERROR|" + json.dumps(error, ensure_ascii=False)
    print(line, flush=True)
    return line


def _parse_fields(parts: list[str]) -> dict[str, str] | None:
    fields: dict[str, str] = {}
    for part in parts:
        key, sep, value = part.partition("=")
        if not sep:
            return None
        fields[key] = value
    return fields


def parse_line(line: Any) -> dict | None:
    if not isinstance(line, str):
        return None
    text = line.strip()
    if text.startswith("BMS_PROGRESS|"):
        fields = _parse_fields(text.split("|")[1:])
        if fields is None or set(fields) != {"beat", "index", "total"}:
            return None
        try:
            index = int(fields["index"])
            total = int(fields["total"])
        except ValueError:
            return None
        return {
            "type": "progress",
            "beat": fields["beat"],
            "index": index,
            "total": total,
        }
    if text.startswith("BMS_WARN|"):
        parts = text.split("|")
        kind = parts[1] if len(parts) > 1 else ""
        fields = _parse_fields(parts[2:])
        if not kind or fields is None:
            return None
        return {"type": "warn", "kind": kind, "fields": fields}
    if text.startswith("BMS_ERROR|"):
        payload = text[len("BMS_ERROR|") :]
        try:
            error = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(error, dict):
            return None
        return {"type": "error", "error": error}
    return None
