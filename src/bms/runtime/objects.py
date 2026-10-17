from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from bms.runtime.protocol import emit_warn
from bms.runtime.regions import REGIONS, RegionInfo, default_region, fit_scale
from bms.schema.colors import COLOR_NAMES
from bms.schema.registry import OBJECT_TYPES
from bms.schema.validate import compile_expr

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

_BANGLA_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


class CustomSkipped(Exception):
    def __init__(self, obj_id: str) -> None:
        super().__init__(obj_id)
        self.obj_id = obj_id


@dataclass
class BuildContext:
    settings: dict
    objs: dict = field(default_factory=dict)
    cells: dict = field(default_factory=dict)
    font_bn: str = "Noto Sans Bengali"


def to_bangla_digits(text: Any) -> str:
    if not isinstance(text, str):
        text = str(text)
    return text.translate(_BANGLA_DIGITS)


def resolve_color(value: Any) -> Any:
    import manim

    if isinstance(value, str):
        if _HEX_RE.match(value):
            return manim.ManimColor(value)
        if value in COLOR_NAMES:
            return getattr(manim, value)
    raise ValueError(f"invalid color: {value!r}")


def _num(spec: dict, defaults: dict, key: str) -> float:
    value = spec.get(key)
    if value is None:
        value = defaults.get(key)
    return value


def _color(spec: dict) -> Any:
    value = spec.get("color")
    if value is None:
        value = "WHITE"
    return resolve_color(value)


def _text(text: Any, ctx: BuildContext) -> str:
    if ctx.settings.get("bangla_numerals_on_screen"):
        return to_bangla_digits(text)
    return text if isinstance(text, str) else str(text)


def _xy(pair: Any) -> list[float]:
    return [float(pair[0]), float(pair[1]), 0.0]


def _safe_expr(expr: str) -> Callable[[float], float]:
    func = compile_expr(expr)

    def safe(x: float) -> float:
        try:
            return float(func(x))
        except (ZeroDivisionError, ValueError, OverflowError):
            return float("nan")

    return safe


def build_object(obj_id: str, spec: dict, ctx: BuildContext) -> Any:
    import manim

    otype = spec.get("type")
    obj_spec = OBJECT_TYPES.get(otype) if isinstance(otype, str) else None
    if obj_spec is None:
        return _build_custom(obj_id, spec, ctx)
    defaults = obj_spec.defaults

    if otype == "text_bn":
        return manim.Text(
            _text(spec["text"], ctx),
            font=ctx.font_bn,
            font_size=_num(spec, defaults, "size"),
            color=_color(spec),
        )
    if otype == "text_en":
        return manim.Text(
            _text(spec["text"], ctx),
            font_size=_num(spec, defaults, "size"),
            color=_color(spec),
        )
    if otype == "mathtex":
        return manim.MathTex(
            spec["tex"],
            font_size=_num(spec, defaults, "size"),
            color=_color(spec),
        )
    if otype == "bn_math_line":
        return manim.VGroup(
            manim.Text(
                _text(spec["bn"], ctx),
                font=ctx.font_bn,
                font_size=_num(spec, defaults, "bn_size"),
                color=_color(spec),
            ),
            manim.MathTex(
                spec["tex"],
                font_size=_num(spec, defaults, "size"),
                color=_color(spec),
            ),
        ).arrange(manim.RIGHT, buff=0.25)
    if otype == "line":
        return manim.Line(
            _xy(spec["start"]),
            _xy(spec["end"]),
            color=_color(spec),
            stroke_width=_num(spec, defaults, "stroke"),
        )
    if otype == "arrow":
        return manim.Arrow(
            _xy(spec["start"]),
            _xy(spec["end"]),
            buff=0,
            color=_color(spec),
            stroke_width=_num(spec, defaults, "stroke"),
        )
    if otype == "circle":
        return manim.Circle(
            radius=_num(spec, defaults, "radius"),
            color=_color(spec),
            fill_opacity=_num(spec, defaults, "fill_opacity"),
        )
    if otype == "rect":
        return manim.Rectangle(
            width=_num(spec, defaults, "width"),
            height=_num(spec, defaults, "height"),
            color=_color(spec),
            fill_opacity=_num(spec, defaults, "fill_opacity"),
        )
    if otype == "polygon":
        return manim.Polygon(
            *[_xy(point) for point in spec["points"]],
            color=_color(spec),
            fill_opacity=_num(spec, defaults, "fill_opacity"),
        )
    if otype == "dot":
        return manim.Dot(
            _xy(spec.get("point") or defaults["point"]),
            radius=_num(spec, defaults, "radius"),
            color=_color(spec),
        )
    if otype == "highlight_box":
        return manim.SurroundingRectangle(
            ctx.objs[spec["target"]],
            color=_color(spec),
            buff=_num(spec, defaults, "buff"),
        )
    if otype == "brace":
        direction = spec.get("direction") or defaults["direction"]
        return manim.Brace(
            ctx.objs[spec["target"]],
            direction=getattr(manim, direction),
            color=_color(spec),
        )
    if otype == "axes":
        return manim.Axes(
            x_range=spec.get("x_range") or defaults["x_range"],
            y_range=spec.get("y_range") or defaults["y_range"],
            x_length=_num(spec, defaults, "x_length"),
            y_length=_num(spec, defaults, "y_length"),
            axis_config={
                "include_tip": _num(spec, defaults, "tips"),
                "color": _color(spec),
            },
        )
    if otype == "function_graph":
        axes = ctx.objs[spec["axes"]]
        return axes.plot(
            _safe_expr(spec["expr"]),
            x_range=spec.get("x_range") or defaults["x_range"],
            color=_color(spec),
        )
    if otype == "number_line":
        return manim.NumberLine(
            x_range=spec.get("x_range") or defaults["x_range"],
            length=_num(spec, defaults, "length"),
            include_numbers=True,
            color=_color(spec),
        )
    if otype == "group":
        children = [ctx.objs[child] for child in spec["children"]]
        return manim.VGroup(*children).arrange(
            getattr(manim, spec.get("arrange") or defaults["arrange"]),
            buff=_num(spec, defaults, "buff"),
        )
    if otype == "question_panel":
        return _build_question_panel(obj_id, spec, ctx)
    raise CustomSkipped(obj_id)


def _build_custom(obj_id: str, spec: dict, ctx: BuildContext) -> Any:
    import manim

    code = spec.get("code")
    if not isinstance(code, str):
        raise CustomSkipped(obj_id)
    namespace: dict[str, Any] = {
        "font_bn": ctx.font_bn,
        "objs": ctx.objs,
        "mobj": None,
    }
    exec("from manim import *", namespace)  # noqa: S102
    exec(code, namespace)  # noqa: S102
    mobj = namespace.get("mobj")
    if not isinstance(mobj, manim.Mobject):
        raise ValueError("custom object code did not set mobj to a Mobject")
    return mobj


def _option_item(option: Any, font_bn: str) -> Any:
    import manim

    if isinstance(option, str):
        return manim.MathTex(option, font_size=32)
    kind = option.get("kind") if isinstance(option, dict) else None
    value = option.get("value") if isinstance(option, dict) else None
    if kind == "tex":
        return manim.MathTex(value, font_size=32)
    if kind == "bn":
        return manim.Text(value, font=font_bn, font_size=24)
    return manim.Text(value, font_size=24)


def _build_question_panel(obj_id: str, spec: dict, ctx: BuildContext) -> Any:
    import manim

    head = manim.Text(f"প্রশ্ন {spec['num']}", font=ctx.font_bn, font_size=26, color=manim.YELLOW)
    body = manim.VGroup(
        manim.MathTex(spec["qmath"], font_size=38),
        manim.Text(_text(spec["qtext"], ctx), font=ctx.font_bn, font_size=24),
    ).arrange(manim.DOWN, buff=0.2)
    cells = []
    for label, option in zip(["I", "II", "III", "IV"], spec["options"]):
        item = _option_item(option, ctx.font_bn)
        cells.append(
            manim.VGroup(
                manim.Text(label + ")", font_size=22, color=manim.GRAY_B),
                item,
            ).arrange(manim.RIGHT, buff=0.2)
        )
    grid = manim.VGroup(*cells).arrange_in_grid(
        rows=2, cols=2, buff=(0.7, 0.4), col_alignments="ll"
    )
    panel = manim.VGroup(head, body, grid).arrange(manim.DOWN, buff=0.5)
    ctx.cells[obj_id] = cells
    return panel


def place_object(
    obj_id: str,
    mobj: Any,
    spec: dict,
    layout: str,
    ctx: BuildContext,
) -> None:
    import manim

    layer = spec.get("layer")
    if isinstance(layer, (int, float)) and not isinstance(layer, bool):
        mobj.set_z_index(layer)

    otype = spec.get("type")
    obj_spec = OBJECT_TYPES.get(otype) if isinstance(otype, str) else None
    placement = obj_spec.placement if obj_spec is not None else "center"
    if placement == "none":
        return

    region_name = spec.get("region")
    info: RegionInfo
    if isinstance(region_name, str) and region_name in REGIONS:
        info = REGIONS[region_name]
    else:
        info = REGIONS[default_region(layout, otype if isinstance(otype, str) else "")]

    dx = _num(spec, {}, "dx") or 0.0
    dy = _num(spec, {}, "dy") or 0.0
    target = [info.center[0] + dx, info.center[1] + dy, 0.0]

    if placement == "center":
        scale = fit_scale(mobj.width, mobj.height, info)
        if scale < 1.0:
            mobj.scale(scale)
            emit_warn("fit", object=obj_id, scale=f"{scale:.2f}")
        mobj.move_to(target)
    else:
        mobj.shift(target)
