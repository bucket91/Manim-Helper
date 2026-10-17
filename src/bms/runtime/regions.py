from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionInfo:
    name: str
    center: tuple[float, float]
    max_width: float
    max_height: float
    layouts: tuple[str, ...]


_ALL = ("full", "split60_40")
_SPLIT = ("split60_40",)

REGIONS: dict[str, RegionInfo] = {
    "full": RegionInfo("full", (0.0, 0.0), 13.0, 7.2, _ALL),
    "center": RegionInfo("center", (0.0, 0.0), 13.0, 7.2, _ALL),
    "top": RegionInfo("top", (0.0, 3.0), 13.0, 1.8, _ALL),
    "bottom": RegionInfo("bottom", (0.0, -3.0), 13.0, 1.8, _ALL),
    "left": RegionInfo("left", (-3.55, 0.0), 6.6, 7.2, _ALL),
    "right": RegionInfo("right", (3.55, 0.0), 6.6, 7.2, _ALL),
    "solution": RegionInfo("solution", (-2.85, 0.0), 8.2, 7.2, _SPLIT),
    "question": RegionInfo("question", (4.25, 0.3), 5.3, 7.0, _SPLIT),
}


def default_region(layout: str, obj_type: str) -> str:
    if layout == "split60_40":
        if obj_type == "question_panel":
            return "question"
        return "solution"
    return "center"


def _region_info(region: RegionInfo | str) -> RegionInfo:
    if isinstance(region, RegionInfo):
        return region
    info = REGIONS.get(region)
    if info is None:
        raise ValueError(f"unknown region: {region!r}")
    return info


def fit_scale(w: float, h: float, region: RegionInfo | str) -> float:
    info = _region_info(region)
    if w <= 0 or h <= 0:
        return 1.0
    if w <= info.max_width and h <= info.max_height:
        return 1.0
    return min(info.max_width / w, info.max_height / h)
