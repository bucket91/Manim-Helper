from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

REQUIRED: Any = ...  # sentinel: parameter has no default and must be present

_PATH_RE = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\[(?P<idx>\d+|\*)\])?"
    r"(?:\.(?P<attr>value))?$"
)


@dataclass(frozen=True)
class ObjectSpec:
    name: str
    required: tuple[str, ...]
    defaults: dict
    placement: str
    text_fields: tuple[str, ...]


@dataclass(frozen=True)
class AnimSpec:
    name: str
    min_targets: int
    max_targets: int | None
    params: dict
    adds: bool
    removes: bool
    needs_alive: bool


OBJECT_TYPES: dict[str, ObjectSpec] = {
    "text_bn": ObjectSpec("text_bn", ("text",), {"size": 28}, "center", ("text",)),
    "text_en": ObjectSpec("text_en", ("text",), {"size": 28}, "center", ("text",)),
    "mathtex": ObjectSpec("mathtex", ("tex",), {"size": 40}, "center", ("tex",)),
    "bn_math_line": ObjectSpec(
        "bn_math_line", ("bn", "tex"), {"bn_size": 28, "size": 40}, "center", ("bn", "tex")
    ),
    "line": ObjectSpec("line", ("start", "end"), {"stroke": 4}, "origin", ()),
    "arrow": ObjectSpec("arrow", ("start", "end"), {"stroke": 4}, "origin", ()),
    "circle": ObjectSpec("circle", (), {"radius": 1, "fill_opacity": 0}, "center", ()),
    "rect": ObjectSpec(
        "rect", (), {"width": 2, "height": 1, "fill_opacity": 0}, "center", ()
    ),
    "polygon": ObjectSpec("polygon", ("points",), {"fill_opacity": 0}, "origin", ()),
    "dot": ObjectSpec("dot", (), {"point": [0, 0], "radius": 0.08}, "origin", ()),
    "highlight_box": ObjectSpec(
        "highlight_box", ("target",), {"buff": 0.12}, "none", ()
    ),
    "brace": ObjectSpec("brace", ("target",), {"direction": "DOWN"}, "none", ()),
    "axes": ObjectSpec(
        "axes",
        (),
        {"x_range": [-5, 5, 1], "y_range": [-5, 5, 1], "x_length": 6, "y_length": 4, "tips": True},
        "center",
        (),
    ),
    "function_graph": ObjectSpec(
        "function_graph", ("axes", "expr"), {"x_range": [-5, 5]}, "none", ()
    ),
    "number_line": ObjectSpec(
        "number_line", (), {"x_range": [-5, 5, 1], "length": 8}, "center", ()
    ),
    "group": ObjectSpec(
        "group", ("children",), {"arrange": "DOWN", "buff": 0.3}, "center", ()
    ),
    "question_panel": ObjectSpec(
        "question_panel",
        ("num", "qmath", "qtext", "options"),
        {},
        "center",
        ("qmath", "qtext", "options[*]"),
    ),
}

ANIMATIONS: dict[str, AnimSpec] = {
    "Write": AnimSpec("Write", 1, None, {}, True, False, False),
    "Create": AnimSpec("Create", 1, None, {}, True, False, False),
    "FadeIn": AnimSpec("FadeIn", 1, None, {"shift": "none"}, True, False, False),
    "FadeOut": AnimSpec("FadeOut", 1, None, {}, False, True, True),
    "Uncreate": AnimSpec("Uncreate", 1, None, {}, False, True, True),
    "Indicate": AnimSpec("Indicate", 1, None, {"scale_factor": 1.2}, False, False, True),
    "Circumscribe": AnimSpec("Circumscribe", 1, None, {}, False, False, True),
    "ReplacementTransform": AnimSpec(
        "ReplacementTransform", 2, 2, {}, True, True, True
    ),
    "move": AnimSpec("move", 1, None, {"by": REQUIRED}, False, False, True),
    "color_change": AnimSpec("color_change", 1, None, {"color": REQUIRED}, False, False, True),
    "scale": AnimSpec("scale", 1, None, {"factor": REQUIRED}, False, False, True),
    "pick_option": AnimSpec("pick_option", 1, 1, {"option": REQUIRED}, True, False, True),
    "wait": AnimSpec("wait", 0, 0, {}, False, False, False),
    "clear_all": AnimSpec("clear_all", 0, 0, {}, False, False, False),
}

COMMON_FIELD_TYPES: dict[str, str] = {
    "region": "str",
    "dx": "num",
    "dy": "num",
    "color": "color",
    "layer": "num",
}

FIELD_TYPES: dict[str, dict[str, str]] = {
    "text_bn": {"text": "str", "size": "num"},
    "text_en": {"text": "str", "size": "num"},
    "mathtex": {"tex": "str", "size": "num"},
    "bn_math_line": {"bn": "str", "tex": "str", "bn_size": "num", "size": "num"},
    "line": {"start": "vec2", "end": "vec2", "stroke": "num"},
    "arrow": {"start": "vec2", "end": "vec2", "stroke": "num"},
    "circle": {"radius": "num", "fill_opacity": "num"},
    "rect": {"width": "num", "height": "num", "fill_opacity": "num"},
    "polygon": {"points": "points", "fill_opacity": "num"},
    "dot": {"point": "vec2", "radius": "num"},
    "highlight_box": {"target": "str", "buff": "num"},
    "brace": {"target": "str", "direction": "str"},
    "axes": {"x_range": "range", "y_range": "range", "x_length": "num", "y_length": "num", "tips": "bool"},
    "function_graph": {"axes": "str", "expr": "str", "x_range": "range"},
    "number_line": {"x_range": "range", "length": "num"},
    "group": {"children": "strlist", "arrange": "str", "buff": "num"},
    "question_panel": {"num": "int", "qmath": "str", "qtext": "str", "options": "options"},
}

PARAM_TYPES: dict[str, str] = {
    "shift": "str",
    "scale_factor": "num",
    "by": "vec2",
    "color": "color",
    "factor": "num",
    "option": "int",
}


def iter_text_fields(obj: dict) -> list[tuple[str, str]]:
    if not isinstance(obj, dict):
        return []
    otype = obj.get("type")
    spec = OBJECT_TYPES.get(otype) if isinstance(otype, str) else None
    if spec is None:
        return []
    out: list[tuple[str, str]] = []
    for path in spec.text_fields:
        match = _PATH_RE.match(path)
        if match is None:
            continue
        name = match.group("name")
        idx = match.group("idx")
        attr = match.group("attr")
        if attr is not None and idx is None:
            continue
        if idx == "*":
            items = obj.get(name)
            if not isinstance(items, list):
                continue
            for i, item in enumerate(items):
                if isinstance(item, str):
                    out.append((f"{name}[{i}]", item))
                elif isinstance(item, dict) and isinstance(item.get("value"), str):
                    out.append((f"{name}[{i}].value", item["value"]))
        elif idx is not None:
            items = obj.get(name)
            if not isinstance(items, list):
                continue
            i = int(idx)
            if not (0 <= i < len(items)):
                continue
            item = items[i]
            if attr == "value":
                if isinstance(item, dict) and isinstance(item.get("value"), str):
                    out.append((f"{name}[{i}].value", item["value"]))
            elif isinstance(item, str):
                out.append((f"{name}[{i}]", item))
        else:
            value = obj.get(name)
            if isinstance(value, str):
                out.append((name, value))
    return out


def set_text_field(obj: dict, path: str, value: str) -> None:
    match = _PATH_RE.match(path)
    if match is None:
        raise ValueError(f"invalid text field path: {path!r}")
    name = match.group("name")
    idx = match.group("idx")
    attr = match.group("attr")
    if idx == "*":
        raise ValueError(f"invalid text field path: {path!r}")
    if attr is not None and idx is None:
        raise ValueError(f"invalid text field path: {path!r}")
    if idx is None:
        obj[name] = value
        return
    items = obj[name]
    if not isinstance(items, list):
        raise ValueError(f"field {name!r} is not a list")
    i = int(idx)
    if not (0 <= i < len(items)):
        raise IndexError(f"index {i} out of range for {name!r}")
    if attr == "value":
        item = items[i]
        if not isinstance(item, dict):
            raise ValueError(f"item at {name}[{i}] is not an object")
        item["value"] = value
    else:
        items[i] = value


def object_refs(obj: dict) -> list[str]:
    if not isinstance(obj, dict):
        return []
    refs: list[str] = []
    target = obj.get("target")
    if isinstance(target, str):
        refs.append(target)
    axes = obj.get("axes")
    if isinstance(axes, str):
        refs.append(axes)
    children = obj.get("children")
    if isinstance(children, list):
        refs.extend(child for child in children if isinstance(child, str))
    return refs
