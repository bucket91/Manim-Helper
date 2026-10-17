from __future__ import annotations

from typing import Any

from bms.runtime.objects import BuildContext, resolve_color
from bms.schema.registry import ANIMATIONS


class CustomStepSkipped(Exception):
    def __init__(self, anim: Any) -> None:
        super().__init__(anim)
        self.anim = anim


def effective_run_time(step: dict, ctx: BuildContext) -> float:
    run_time = step.get("run_time")
    if run_time is None:
        run_time = ctx.settings.get("default_run_time", 1.0)
    return float(run_time)


def step_targets(step: dict) -> list[str]:
    targets = step.get("targets")
    if not isinstance(targets, list):
        return []
    return [target for target in targets if isinstance(target, str)]


def build_groups(beat: dict) -> list[list[int]]:
    steps = beat.get("steps") if isinstance(beat, dict) else None
    if not isinstance(steps, list):
        return []
    groups: list[list[int]] = []
    for index, step in enumerate(steps):
        if index == 0 or not (isinstance(step, dict) and step.get("with_previous") is True):
            groups.append([index])
        else:
            groups[-1].append(index)
    return groups


def _present(ctx: BuildContext, targets: list[str]) -> list[str]:
    return [target for target in targets if target in ctx.objs]


def _custom_animations(step: dict, scene: Any, ctx: BuildContext, targets: list[str]) -> list[Any]:
    code = step.get("code")
    if not isinstance(code, str):
        raise CustomStepSkipped(step.get("anim"))
    namespace: dict[str, Any] = {
        "self": scene,
        "objs": ctx.objs,
        "targets": [ctx.objs[target] for target in _present(ctx, targets)],
    }
    exec(code, namespace)  # noqa: S102
    anims = namespace.get("anims")
    if not isinstance(anims, list):
        raise ValueError("custom step code did not assign a list to anims")
    return anims


def make_animations(step: dict, scene: Any, ctx: BuildContext) -> list[Any]:
    import manim

    anim = step.get("anim")
    if anim not in ANIMATIONS:
        return _custom_animations(step, scene, ctx, step_targets(step))

    run_time = effective_run_time(step, ctx)
    targets = _present(ctx, step_targets(step))
    objs = ctx.objs

    if anim == "Write":
        return [manim.Write(objs[target], run_time=run_time) for target in targets]
    if anim == "Create":
        return [manim.Create(objs[target], run_time=run_time) for target in targets]
    if anim == "FadeIn":
        shift = step.get("shift", "none")
        anims = []
        for target in targets:
            if shift and shift != "none":
                anims.append(
                    manim.FadeIn(objs[target], shift=getattr(manim, shift) * 0.3, run_time=run_time)
                )
            else:
                anims.append(manim.FadeIn(objs[target], run_time=run_time))
        return anims
    if anim == "FadeOut":
        anims = []
        for target in targets:
            anims.append(manim.FadeOut(objs[target], run_time=run_time))
            pick = objs.get(f"{target}__pick")
            if pick is not None:
                anims.append(manim.FadeOut(pick, run_time=run_time))
        return anims
    if anim == "Uncreate":
        return [manim.Uncreate(objs[target], run_time=run_time) for target in targets]
    if anim == "Indicate":
        scale_factor = step.get("scale_factor", 1.2)
        return [
            manim.Indicate(objs[target], scale_factor=scale_factor, run_time=run_time)
            for target in targets
        ]
    if anim == "Circumscribe":
        return [manim.Circumscribe(objs[target], run_time=run_time) for target in targets]
    if anim == "ReplacementTransform":
        if len(targets) != 2:
            return []
        return [
            manim.ReplacementTransform(objs[targets[0]], objs[targets[1]], run_time=run_time)
        ]
    if anim == "move":
        by = step["by"]
        offset = [by[0], by[1], 0]
        return [objs[target].animate(run_time=run_time).shift(offset) for target in targets]
    if anim == "color_change":
        color = resolve_color(step["color"])
        return [objs[target].animate(run_time=run_time).set_color(color) for target in targets]
    if anim == "scale":
        factor = step["factor"]
        return [objs[target].animate(run_time=run_time).scale(factor) for target in targets]
    if anim == "pick_option":
        if not targets:
            return []
        target = targets[0]
        option = int(step["option"])
        cell = ctx.cells[target][option]
        box = manim.SurroundingRectangle(cell, color=manim.GREEN, buff=0.12)
        ctx.objs[f"{target}__pick"] = box
        return [
            manim.Create(box, run_time=run_time),
            cell.animate(run_time=run_time).set_color(manim.GREEN),
        ]
    if anim == "wait":
        return [manim.Wait(run_time=run_time)]
    if anim == "clear_all":
        alive = getattr(scene, "alive", None) or set()
        mobjects = [objs[obj_id] for obj_id in sorted(alive) if obj_id in objs]
        if not mobjects:
            return [manim.Wait(run_time=run_time)]
        return [manim.FadeOut(*mobjects, run_time=run_time)]
    return []


def update_alive(step: dict, alive: set[str]) -> None:
    anim = step.get("anim")
    targets = step_targets(step)
    spec = ANIMATIONS.get(anim)
    if spec is None:
        adds = step.get("adds")
        if isinstance(adds, list):
            alive.update(item for item in adds if isinstance(item, str))
        removes = step.get("removes")
        if isinstance(removes, list):
            for item in removes:
                if isinstance(item, str):
                    alive.discard(item)
                    alive.discard(f"{item}__pick")
        return
    if anim == "pick_option":
        for target in targets:
            alive.add(f"{target}__pick")
    elif anim == "clear_all":
        alive.clear()
    elif anim == "ReplacementTransform":
        if targets:
            alive.discard(targets[0])
        if len(targets) >= 2:
            alive.add(targets[1])
    elif spec.adds:
        alive.update(targets)
    elif spec.removes:
        for target in targets:
            alive.discard(target)
            alive.discard(f"{target}__pick")
