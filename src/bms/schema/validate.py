from __future__ import annotations

import ast
import difflib
import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from bms import jsonio
from bms.schema.colors import COLOR_NAMES
from bms.schema.registry import (
    ANIMATIONS,
    COMMON_FIELD_TYPES,
    FIELD_TYPES,
    ID_RE,
    OBJECT_TYPES,
    PARAM_TYPES,
    REQUIRED,
    AnimSpec,
    ObjectSpec,
    object_refs,
)

if TYPE_CHECKING:
    from bms.project import Project

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

_REGIONS = frozenset(
    {"full", "center", "top", "bottom", "left", "right", "solution", "question"}
)
_SPLIT_REGIONS = frozenset({"solution", "question"})

_EXPR_FUNCS: dict[str, Callable[..., float]] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "exp": math.exp,
    "log": math.log10,
    "ln": math.log,
    "sqrt": math.sqrt,
    "abs": abs,
}
_EXPR_CONSTS: dict[str, float] = {"pi": math.pi, "e": math.e}
_EXPR_NAMES: frozenset[str] = frozenset({"x", "pi", "e"})


def compile_expr(expr: str) -> Callable[[float], float]:
    if not isinstance(expr, str):
        raise ValueError("expr must be a string")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid expression: {exc.msg}") from None
    call_func_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                call_func_names.add(func.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.Expression):
            continue
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
        ):
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            continue
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError(f"invalid constant: {node.value!r}")
            continue
        if isinstance(node, ast.Name):
            if node.id not in _EXPR_NAMES and node.id not in call_func_names:
                raise ValueError(f"unknown name: {node.id!r}")
            continue
        if isinstance(node, ast.Call):
            func = node.func
            if not isinstance(func, ast.Name) or func.id not in _EXPR_FUNCS:
                raise ValueError("only plain calls of allowed functions are permitted")
            if node.keywords:
                raise ValueError("keyword arguments are not allowed")
            continue
        if isinstance(
            node,
            (
                ast.Load,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.Pow,
                ast.Mod,
                ast.UAdd,
                ast.USub,
            ),
        ):
            continue
        raise ValueError(f"disallowed syntax: {type(node).__name__}")
    code = compile(tree, "<expr>", "eval")
    names: dict[str, object] = {"x": 0.0, **_EXPR_CONSTS, **_EXPR_FUNCS}

    def _eval(x: float) -> float:
        names["x"] = x
        try:
            return float(eval(code, {"__builtins__": {}}, names))  # noqa: S307
        except (TypeError, ZeroDivisionError) as exc:
            raise ValueError(f"expression is not evaluable: {exc}") from None

    return _eval


@dataclass
class Issue:
    code: str
    level: str
    scene_id: str
    beat_id: str | None
    object_id: str | None
    step_index: int | None
    field: str | None
    message: str


def format_issue(issue: Issue) -> str:
    parts = [f"[{issue.code}]"]
    if issue.scene_id:
        parts.append(f"scene={issue.scene_id}")
    if issue.beat_id:
        parts.append(f"beat={issue.beat_id}")
    if issue.step_index is not None:
        parts.append(f"step={issue.step_index}")
    if issue.object_id:
        parts.append(f"object={issue.object_id}")
    head = " ".join(parts)
    if issue.field:
        return f"{head} field={issue.field}: {issue.message}"
    return f"{head}: {issue.message}"


def _is_num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _type_ok(kind: str, value: object) -> bool:
    if kind == "str":
        return isinstance(value, str)
    if kind == "num":
        return _is_num(value)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "color":
        return isinstance(value, str)
    if kind == "vec2":
        return (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and all(_is_num(v) for v in value)
        )
    if kind == "range":
        return (
            isinstance(value, (list, tuple))
            and len(value) in (2, 3)
            and all(_is_num(v) for v in value)
        )
    if kind == "points":
        return (
            isinstance(value, (list, tuple))
            and len(value) >= 3
            and all(
                isinstance(p, (list, tuple))
                and len(p) == 2
                and all(_is_num(v) for v in p)
                for p in value
            )
        )
    if kind == "strlist":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if kind == "options":
        if not isinstance(value, list) or len(value) != 4:
            return False
        for item in value:
            if isinstance(item, str):
                continue
            if isinstance(item, dict):
                if item.get("kind") not in ("tex", "bn", "en"):
                    return False
                if not isinstance(item.get("value"), str):
                    return False
                continue
            return False
        return True
    return True


def _color_ok(value: str) -> bool:
    return bool(_HEX_RE.match(value)) or value in COLOR_NAMES


def _did_you_mean(name: str, ids: list[str]) -> str:
    matches = difflib.get_close_matches(name, ids, n=1, cutoff=0.6)
    if matches:
        return f" (did you mean '{matches[0]}'?)"
    return ""


def _target_expectation(spec: AnimSpec) -> str:
    if spec.max_targets is None:
        return f"at least {spec.min_targets}"
    if spec.min_targets == spec.max_targets:
        return f"exactly {spec.min_targets}"
    return f"between {spec.min_targets} and {spec.max_targets}"


def validate_scene(scene: dict, settings: dict) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(scene, dict):
        return [
            Issue(
                "E101",
                "error",
                "",
                None,
                None,
                None,
                None,
                "scene file is not a JSON object",
            )
        ]
    sid = scene.get("scene_id")
    scene_id = sid if isinstance(sid, str) else ""

    def add(
        code: str,
        level: str,
        *,
        beat: str | None = None,
        obj: str | None = None,
        step: int | None = None,
        field: str | None = None,
        msg: str,
    ) -> None:
        issues.append(Issue(code, level, scene_id, beat, obj, step, field, msg))

    settings = settings if isinstance(settings, dict) else {}

    # --- scene-level ------------------------------------------------------
    fv = scene.get("format_version")
    if "format_version" not in scene:
        add("E101", "error", field="format_version", msg="missing format_version")
    elif fv != 1 or isinstance(fv, bool):
        add("E101", "error", field="format_version", msg="format_version must be 1")

    if not isinstance(sid, str) or not ID_RE.fullmatch(sid):
        if isinstance(sid, str):
            add("E102", "error", field="scene_id", msg=f"invalid scene_id: {sid!r}")
        else:
            add("E102", "error", field="scene_id", msg="scene_id is missing")

    layout = scene.get("layout")

    objects = scene.get("objects")
    if objects is None:
        add("E108", "error", field="objects", msg="missing required field: objects")
        objects = {}
    elif not isinstance(objects, dict):
        add("E108", "error", field="objects", msg="objects must be an object")
        objects = {}

    beats = scene.get("beats")
    if beats is None:
        add("E108", "error", field="beats", msg="missing required field: beats")
        beats = []
    elif not isinstance(beats, list):
        add("E108", "error", field="beats", msg="beats must be a list")
        beats = []

    obj_ids = [k for k in objects if isinstance(k, str)]

    # --- objects ----------------------------------------------------------
    group_children: dict[str, list[str]] = {}
    for oid, obj in objects.items():
        if not isinstance(obj, dict):
            add(
                "E119",
                "error",
                obj=oid,
                field="objects",
                msg=f"object {oid!r} is not an object",
            )
            continue

        if not ID_RE.fullmatch(oid):
            add("E104", "error", obj=oid, field="id", msg=f"invalid object id: {oid!r}")
        elif oid.endswith("__pick"):
            add(
                "E104",
                "error",
                obj=oid,
                field="id",
                msg=f"object id {oid!r} uses the reserved '__pick' suffix",
            )

        otype = obj.get("type")
        spec: ObjectSpec | None
        if "type" not in obj or otype is None:
            add("E108", "error", obj=oid, field="type", msg="missing required field: type")
            spec = None
        elif not isinstance(otype, str):
            add("E119", "error", obj=oid, field="type", msg="type has the wrong type")
            spec = None
        else:
            spec = OBJECT_TYPES.get(otype)

        missing: set[str] = set()
        if spec is None:
            if isinstance(otype, str):
                if "code" in obj:
                    add(
                        "W202",
                        "warning",
                        obj=oid,
                        msg=f"custom object {oid!r} runs Python code",
                    )
                else:
                    add(
                        "W201",
                        "warning",
                        obj=oid,
                        msg=f"custom object {oid!r} has no code and is skipped",
                    )
        else:
            for fname in spec.required:
                if fname not in obj or obj[fname] is None:
                    add(
                        "E108",
                        "error",
                        obj=oid,
                        field=fname,
                        msg=f"missing required field: {fname}",
                    )
                    missing.add(fname)
            for fname, kind in FIELD_TYPES[spec.name].items():
                if fname in missing or fname not in obj:
                    continue
                if not _type_ok(kind, obj[fname]):
                    add(
                        "E119",
                        "error",
                        obj=oid,
                        field=fname,
                        msg=f"{fname} has the wrong type",
                    )

        for fname, kind in COMMON_FIELD_TYPES.items():
            if fname not in obj or obj[fname] is None:
                continue
            if not _type_ok(kind, obj[fname]):
                add(
                    "E119",
                    "error",
                    obj=oid,
                    field=fname,
                    msg=f"{fname} has the wrong type",
                )

        color = obj.get("color")
        if isinstance(color, str) and not _color_ok(color):
            add("E111", "error", obj=oid, field="color", msg=f"invalid color: {color!r}")

        region = obj.get("region")
        if isinstance(region, str):
            if region not in _REGIONS:
                add(
                    "E109",
                    "error",
                    obj=oid,
                    field="region",
                    msg=f"unknown region: {region!r}",
                )
            elif region in _SPLIT_REGIONS and layout != "split60_40":
                add(
                    "E109",
                    "error",
                    obj=oid,
                    field="region",
                    msg=f"region {region!r} is not allowed in layout {layout!r}",
                )

        if isinstance(otype, str) and otype == "function_graph":
            expr = obj.get("expr")
            if isinstance(expr, str) and "expr" not in missing:
                try:
                    compile_expr(expr)
                except ValueError as exc:
                    add("E112", "error", obj=oid, field="expr", msg=str(exc))

        for key in ("target", "axes"):
            value = obj.get(key)
            if isinstance(value, str) and value not in objects:
                add(
                    "E105",
                    "error",
                    obj=oid,
                    field=key,
                    msg=f"unknown object id {value!r}{_did_you_mean(value, obj_ids)}",
                )
        children = obj.get("children")
        if isinstance(otype, str) and otype == "group" and isinstance(children, list):
            group_children[oid] = [c for c in children if isinstance(c, str)]
            for child in group_children[oid]:
                if child not in objects:
                    add(
                        "E105",
                        "error",
                        obj=oid,
                        field="children",
                        msg=f"unknown object id {child!r}{_did_you_mean(child, obj_ids)}",
                    )

    child_group: dict[str, str] = {}
    for gid, children in group_children.items():
        for child in children:
            if child in child_group and child_group[child] != gid:
                add(
                    "E117",
                    "error",
                    obj=gid,
                    field="children",
                    msg=(
                        f"object {child!r} is in more than one group "
                        f"({child_group[child]!r}, {gid!r})"
                    ),
                )
            else:
                child_group.setdefault(child, gid)

    # --- beats ------------------------------------------------------------
    alive: set[str] = set()
    seen_beat_ids: set[str] = set()
    referenced: set[str] = set()
    for obj in objects.values():
        if isinstance(obj, dict):
            referenced.update(object_refs(obj))

    project_pad = settings.get("pad")
    if _is_num(project_pad) and project_pad < 0:
        add(
            "E114",
            "error",
            field="pad",
            msg=f"project pad must not be negative: {project_pad}",
        )

    for b_index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            add(
                "E119",
                "error",
                field="beats",
                msg=f"beat at index {b_index} is not an object",
            )
            continue

        bid = beat.get("id")
        beat_id = bid if isinstance(bid, str) else None
        if isinstance(bid, str):
            if bid in seen_beat_ids:
                add(
                    "E103",
                    "error",
                    beat=bid,
                    field="id",
                    msg=f"duplicate beat id: {bid!r}",
                )
            seen_beat_ids.add(bid)

        narration = beat.get("narration")
        has_narration = isinstance(narration, str) and narration.strip() != ""
        if (
            "narration" in beat
            and narration is not None
            and not isinstance(narration, str)
        ):
            add(
                "E118",
                "error",
                beat=beat_id,
                field="narration",
                msg="narration must be a string or null",
            )
            has_narration = False
        elif isinstance(narration, str) and not narration.strip():
            add(
                "W204",
                "warning",
                beat=beat_id,
                field="narration",
                msg="narration is an empty string",
            )
            has_narration = False

        for fname in ("hold", "pad"):
            if fname not in beat or beat[fname] is None:
                continue
            value = beat[fname]
            if not _is_num(value):
                add(
                    "E119",
                    "error",
                    beat=beat_id,
                    field=fname,
                    msg=f"{fname} has the wrong type",
                )
            elif value < 0:
                add(
                    "E114",
                    "error",
                    beat=beat_id,
                    field=fname,
                    msg=f"{fname} must not be negative: {value}",
                )

        steps = beat.get("steps")
        if steps is None:
            steps = []
        elif not isinstance(steps, list):
            add("E108", "error", beat=beat_id, field="steps", msg="steps must be a list")
            steps = []

        for s_index, step in enumerate(steps):
            if not isinstance(step, dict):
                add(
                    "E119",
                    "error",
                    beat=beat_id,
                    step=s_index,
                    field="steps",
                    msg=f"step at index {s_index} is not an object",
                )
                continue

            def step_issue(
                code: str,
                level: str,
                *,
                obj: str | None = None,
                field: str | None = None,
                msg: str,
            ) -> None:
                add(code, level, beat=beat_id, obj=obj, step=s_index, field=field, msg=msg)

            # --- step-level common fields ---------------------------------
            if "anim" not in step or step["anim"] is None:
                step_issue(
                    "E108", "error", field="anim", msg="missing required field: anim"
                )
                continue
            anim = step["anim"]
            if not isinstance(anim, str):
                step_issue(
                    "E119", "error", field="anim", msg="anim has the wrong type"
                )
                continue

            at_val = step.get("at")
            at_pct = step.get("at_pct")
            with_prev = step.get("with_previous")
            targets_raw = step.get("targets")
            targets: list[str] = (
                [t for t in targets_raw if isinstance(t, str)]
                if isinstance(targets_raw, list)
                else []
            )
            referenced.update(targets)

            if "run_time" in step and step["run_time"] is not None:
                rt = step["run_time"]
                if not _is_num(rt):
                    step_issue(
                        "E119",
                        "error",
                        field="run_time",
                        msg="run_time has the wrong type",
                    )
                elif not (0 < rt <= 30):
                    step_issue(
                        "E114",
                        "error",
                        field="run_time",
                        msg=f"run_time must be in (0, 30], got {rt}",
                    )
            for fname in ("at", "at_pct"):
                if fname in step and step[fname] is not None and not _is_num(step[fname]):
                    step_issue(
                        "E119",
                        "error",
                        field=fname,
                        msg=f"{fname} has the wrong type",
                    )
            if at_val is not None and at_pct is not None:
                step_issue("E106", "error", field="at", msg="both at and at_pct are set")
            if _is_num(at_val) and at_val < 0:
                step_issue(
                    "E114",
                    "error",
                    field="at",
                    msg=f"at must not be negative: {at_val}",
                )
            if _is_num(at_pct) and not (0 <= at_pct <= 100):
                step_issue(
                    "E114",
                    "error",
                    field="at_pct",
                    msg=f"at_pct must be in 0..100, got {at_pct}",
                )
            if at_pct is not None and _is_num(at_pct) and not has_narration:
                step_issue(
                    "E107",
                    "error",
                    field="at_pct",
                    msg="at_pct requires a non-empty narration on the beat",
                )
            if with_prev is not None and not isinstance(with_prev, bool):
                step_issue(
                    "E119",
                    "error",
                    field="with_previous",
                    msg="with_previous has the wrong type",
                )
            is_group_start = s_index == 0 or with_prev is not True
            if (at_val is not None or at_pct is not None) and not is_group_start:
                step_issue(
                    "E115",
                    "error",
                    field="at" if at_val is not None else "at_pct",
                    msg="at/at_pct is only allowed on the first step of a group",
                )
            if anim in ("wait", "clear_all") and with_prev is True:
                step_issue(
                    "E115",
                    "error",
                    field="with_previous",
                    msg=f"{anim} cannot have with_previous",
                )

            # --- targets: shape + E105 ------------------------------------
            if targets_raw is None:
                targets_reported = False
            elif not isinstance(targets_raw, list):
                step_issue(
                    "E119", "error", field="targets", msg="targets must be a list"
                )
                targets_reported = True
            else:
                targets_reported = True
                if any(not isinstance(t, str) for t in targets_raw):
                    step_issue(
                        "E119",
                        "error",
                        field="targets",
                        msg="targets must be a list of object ids",
                    )
                for t in targets:
                    if t not in objects:
                        step_issue(
                            "E105",
                            "error",
                            field="targets",
                            msg=f"unknown object id {t!r}{_did_you_mean(t, obj_ids)}",
                        )

            # --- custom step ----------------------------------------------
            spec = ANIMATIONS.get(anim)
            if spec is None:
                if "code" in step:
                    step_issue("W202", "warning", msg=f"custom step {anim!r} runs Python code")
                else:
                    step_issue(
                        "W201",
                        "warning",
                        msg=f"custom step {anim!r} has no code and is skipped",
                    )
                for key in ("adds", "removes"):
                    value = step.get(key)
                    if value is None:
                        continue
                    if not isinstance(value, list):
                        step_issue(
                            "E119",
                            "error",
                            field=key,
                            msg=f"{key} must be a list of object ids",
                        )
                        continue
                    ids = [v for v in value if isinstance(v, str)]
                    if key == "adds":
                        alive.update(ids)
                    else:
                        alive.difference_update(ids)
                        alive.difference_update(f"{i}__pick" for i in ids)
                continue

            # --- known animation ------------------------------------------
            exp = _target_expectation(spec)
            if targets_raw is None:
                if spec.min_targets > 0:
                    step_issue(
                        "E113",
                        "error",
                        field="targets",
                        msg=f"{anim} expects {exp} target(s), got 0",
                    )
            elif targets_reported:
                n = len(targets_raw)
                if n < spec.min_targets or (
                    spec.max_targets is not None and n > spec.max_targets
                ):
                    step_issue(
                        "E113",
                        "error",
                        field="targets",
                        msg=f"{anim} expects {exp} target(s), got {n}",
                    )

            for pname, default in spec.params.items():
                kind = PARAM_TYPES.get(pname, "str")
                if default is REQUIRED and (pname not in step or step[pname] is None):
                    step_issue(
                        "E108",
                        "error",
                        field=pname,
                        msg=f"missing required field: {pname}",
                    )
                if pname in step and step[pname] is not None:
                    if not _type_ok(kind, step[pname]):
                        step_issue(
                            "E119",
                            "error",
                            field=pname,
                            msg=f"{pname} has the wrong type",
                        )
                    elif kind == "color" and isinstance(step[pname], str):
                        if not _color_ok(step[pname]):
                            step_issue(
                                "E111",
                                "error",
                                field=pname,
                                msg=f"invalid color: {step[pname]!r}",
                            )

            if anim == "pick_option":
                option = step.get("option")
                if isinstance(option, int) and not isinstance(option, bool):
                    if not (0 <= option <= 3):
                        step_issue(
                            "E110",
                            "error",
                            field="option",
                            msg=f"option must be in 0..3, got {option}",
                        )
                if len(targets) == 1:
                    t0 = targets[0]
                    obj = objects.get(t0)
                    if isinstance(obj, dict) and obj.get("type") != "question_panel":
                        step_issue(
                            "E110",
                            "error",
                            field="targets",
                            msg=f"pick_option target {t0!r} is not a question_panel",
                        )

            # --- E116 aliveness / E117 direct targeting --------------------
            if anim == "ReplacementTransform":
                check_alive = targets[:1]
            elif spec.needs_alive:
                check_alive = targets
            else:
                check_alive = []
            for t in check_alive:
                if t not in alive:
                    step_issue(
                        "E116",
                        "error",
                        obj=t,
                        msg=f"object {t!r} is used before it was shown",
                    )
            for t in targets:
                gid = child_group.get(t)
                if gid is not None and gid in alive:
                    step_issue(
                        "E117",
                        "error",
                        obj=gid,
                        field="children",
                        msg=f"object {t!r} is targeted directly while group {gid!r} exists",
                    )

            if spec.adds:
                for t in targets:
                    if t in alive:
                        continue
                    obj = objects.get(t)
                    if not isinstance(obj, dict):
                        continue
                    for key in ("target", "axes"):
                        ref = obj.get(key)
                        if isinstance(ref, str) and ref not in alive:
                            step_issue(
                                "E116",
                                "error",
                                obj=t,
                                field=key,
                                msg=f"object {t!r} uses {ref!r} before it was shown",
                            )

            # --- alive-set bookkeeping -------------------------------------
            if anim == "pick_option":
                for t in targets:
                    alive.add(f"{t}__pick")
            elif anim == "clear_all":
                alive.clear()
            elif anim == "ReplacementTransform":
                if len(targets) >= 1:
                    alive.discard(targets[0])
                if len(targets) >= 2:
                    t1 = targets[1]
                    alive.add(t1)
                    obj = objects.get(t1)
                    if isinstance(obj, dict) and obj.get("type") == "group":
                        alive.update(group_children.get(t1, []))
            elif spec.adds:
                alive.update(targets)
                for t in targets:
                    obj = objects.get(t)
                    if isinstance(obj, dict) and obj.get("type") == "group":
                        alive.update(group_children.get(t, []))
            elif spec.removes:
                alive.difference_update(targets)
                alive.difference_update(f"{t}__pick" for t in targets)
                for t in targets:
                    obj = objects.get(t)
                    if isinstance(obj, dict) and obj.get("type") == "group":
                        alive.difference_update(group_children.get(t, []))

    # W205: defined but never referenced
    for oid, obj in objects.items():
        if isinstance(obj, dict) and oid not in referenced:
            add(
                "W205",
                "warning",
                obj=oid,
                msg=f"object {oid!r} is defined but never referenced",
            )

    return issues


def validate_project(project: Project) -> dict[str, list[Issue]]:
    result: dict[str, list[Issue]] = {}
    for scene_id in project.scene_ids():
        path = project.scene_path(scene_id)
        try:
            scene = jsonio.load_json(path)
        except (OSError, ValueError) as exc:
            result[scene_id] = [
                Issue(
                    "E101",
                    "error",
                    scene_id,
                    None,
                    None,
                    None,
                    None,
                    f"cannot read scene file: {exc}",
                )
            ]
            continue
        if not isinstance(scene, dict):
            result[scene_id] = [
                Issue(
                    "E101",
                    "error",
                    scene_id,
                    None,
                    None,
                    None,
                    None,
                    "scene file is not a JSON object",
                )
            ]
            continue
        issues = validate_scene(scene, project.settings)
        content_id = scene.get("scene_id")
        if isinstance(content_id, str) and content_id != scene_id:
            issues.append(
                Issue(
                    "E102",
                    "error",
                    scene_id,
                    None,
                    None,
                    None,
                    "scene_id",
                    f"scene_id {content_id!r} does not match file name {scene_id!r}",
                )
            )
        result[scene_id] = issues
    return result
