from __future__ import annotations

from pathlib import Path
from typing import Any

from manim import Scene

from bms.engine.audio import audio_duration, make_audio
from bms.project import Project
from bms.runtime.objects import BuildContext, CustomSkipped, build_object, place_object
from bms.runtime.protocol import emit_error, emit_progress, emit_warn
from bms.runtime.steps import (
    CustomStepSkipped,
    build_groups,
    make_animations,
    step_targets,
    update_alive,
)
from bms.schema.registry import OBJECT_TYPES, object_refs


class BmsScene(Scene):
    bms_spec: dict = {}

    def _now(self) -> float:
        try:
            return float(self.time)
        except AttributeError:
            return float(self.renderer.time)

    def construct(self) -> None:
        spec = dict(self.bms_spec)
        project = Project.open(Path(spec["project_root"]))
        self.settings = project.settings
        self.pron = project.pronunciation
        self.narrate = bool(self.settings.get("narrate", True))
        self.audio_dir = project.subdir("narration_cache")
        self.scene_id = spec["scene_id"]
        self.mode = spec.get("mode", "scene")
        self.beat_id = spec.get("beat_id")
        self.continue_on_error = bool(spec.get("continue_on_error", False))
        self.debug = bool(spec.get("debug", False))

        self.scene_data = project.load_scene(self.scene_id)
        self.layout = self.scene_data.get("layout", "full")
        self.objects = self.scene_data.get("objects") or {}
        self.ctx = BuildContext(
            settings=self.settings,
            font_bn=self.settings.get("font_bn", "Noto Sans Bengali"),
        )
        self.alive: set[str] = set()
        self.my_audio_events: list[tuple[float, str]] = []
        self.bms_timing: list[dict] = []
        self._t_offset = 0.0
        self._end = 0.0
        self._dur = 0.0
        self._building: set[str] = set()
        self._skipped: set[str] = set()
        self._cur_beat: str | None = None
        self._cur_object: str | None = None
        self._cur_step: int | None = None
        self._error_kind = "other"

        if self.layout == "split60_40":
            self._add_divider()

        beats = [beat for beat in (self.scene_data.get("beats") or []) if isinstance(beat, dict)]
        total = len(beats)
        narrate_setting = bool(self.settings.get("narrate", True))
        for index, beat in enumerate(beats):
            beat_id = beat.get("id")
            emit_progress(beat_id, index, total)
            if self.mode == "frame":
                if beat_id == self.beat_id:
                    self.next_section("target", skip_animations=False)
                    self._t_offset = self._now()
                    self._run_beat(beat, evaluate_narration=False)
                    break
                else:
                    self.next_section(f"skip_{beat_id}", skip_animations=True)
                    self._run_beat(beat, evaluate_narration=False)
            elif self.mode == "scene":
                self._run_beat(beat, evaluate_narration=narrate_setting)
            elif self.mode == "beat" and beat_id == self.beat_id:
                self.next_section("target", skip_animations=False)
                self._t_offset = self._now()
                self._run_beat(beat, evaluate_narration=narrate_setting)
                break
            else:
                self.next_section(f"skip_{beat_id}", skip_animations=True)
                self._run_beat(beat, evaluate_narration=False)

        self._write_master_track()
        BmsScene.bms_timing = self.bms_timing
        BmsScene.last_timing = self.bms_timing

    def _add_divider(self) -> None:
        import manim

        divider = manim.Line(
            manim.UP * 3.9, manim.DOWN * 3.9, color=manim.GRAY_D, stroke_width=2
        ).move_to(manim.RIGHT * 1.4)
        self.add(divider)

    def _write_master_track(self) -> None:
        if not self.my_audio_events:
            return
        from pydub import AudioSegment

        total_ms = int((self._now() - self._t_offset) * 1000) + 1000
        master = AudioSegment.silent(duration=total_ms)
        for start_time, filepath in self.my_audio_events:
            master = master.overlay(
                AudioSegment.from_file(filepath), position=int(start_time * 1000)
            )
        label = self.beat_id if self.mode != "scene" else "all"
        master_path = self.audio_dir / f"master_{self.scene_id}_{self.mode}_{label}.wav"
        master.export(str(master_path), format="wav")
        file_writer = getattr(self.renderer, "file_writer", None)
        if file_writer is not None:
            file_writer.add_sound(str(master_path), time=0.0, gain=None)

    def say(self, text: str) -> float:
        if not self.narrate:
            self._end = self._now()
            return 0.0
        try:
            path = make_audio(text, self.settings, self.pron, self.audio_dir)
            duration = audio_duration(path)
        except Exception as exc:
            emit_warn("narration", beat=self._cur_beat, reason=str(exc)[:200])
            self._end = self._now()
            return 0.0
        if duration <= 0.1:
            emit_warn("narration", beat=self._cur_beat, reason="blank audio")
            self._end = self._now()
            return 0.0
        self.my_audio_events.append((self._now() - self._t_offset, str(path)))
        self._end = self._now() + duration
        return duration

    def settle(self, pad: float) -> None:
        rest = self._end + pad - self._now()
        if rest > 0.02:
            self.wait(rest)

    def _group_target(self, t0: float, step: dict) -> float:
        at = step.get("at")
        if at is not None:
            return t0 + float(at)
        at_pct = step.get("at_pct")
        if at_pct is not None:
            return t0 + (float(at_pct) / 100.0) * self._dur
        return t0

    def _ensure_built(self, obj_id: str) -> None:
        if obj_id in self.ctx.objs or obj_id in self._building or obj_id in self._skipped:
            return
        spec = self.objects.get(obj_id)
        if not isinstance(spec, dict):
            return
        self._building.add(obj_id)
        try:
            for ref in object_refs(spec):
                self._ensure_built(ref)
            otype = spec.get("type")
            self._error_kind = "object_build" if otype in OBJECT_TYPES else "custom_code"
            self._cur_object = obj_id
            mobj = build_object(obj_id, spec, self.ctx)
            self._error_kind = "object_build"
            place_object(obj_id, mobj, spec, self.layout, self.ctx)
            self.ctx.objs[obj_id] = mobj
        except CustomSkipped as exc:
            self._skipped.add(exc.obj_id)
            emit_warn("custom_skipped", object=exc.obj_id)
        finally:
            self._building.discard(obj_id)
            self._cur_object = None
            self._error_kind = "other"

    def _step_animations(self, step: dict, step_index: int) -> list[Any]:
        self._cur_step = step_index
        for target in step_targets(step):
            self._ensure_built(target)
        self._error_kind = "animation"
        try:
            return make_animations(step, self, self.ctx)
        except CustomStepSkipped as exc:
            emit_warn("custom_skipped", anim=exc.anim)
            return []
        finally:
            self._cur_step = None
            self._error_kind = "other"

    def _run_beat(self, beat: dict, evaluate_narration: bool) -> None:
        beat_id = beat.get("id")
        self._cur_beat = beat_id
        t0 = self._now()
        self.narrate = evaluate_narration and bool(self.settings.get("narrate", True))
        self._end = t0
        self._dur = 0.0
        try:
            narration = beat.get("narration")
            if self.narrate and isinstance(narration, str) and narration.strip():
                self._dur = self.say(narration)
            steps = beat.get("steps") if isinstance(beat.get("steps"), list) else []
            for group in build_groups(beat):
                first = steps[group[0]]
                target_t = self._group_target(t0, first)
                now = self._now()
                if now < target_t:
                    self.wait(target_t - now)
                anims: list[Any] = []
                for index in group:
                    anims.extend(self._step_animations(steps[index], index))
                if anims:
                    self.play(*anims)
                for index in group:
                    update_alive(steps[index], self.alive)
            pad = beat.get("pad")
            if pad is None:
                pad = self.settings.get("pad", 0.25)
            self.settle(float(pad))
            hold = beat.get("hold") or 0.0
            if hold > 0:
                self.wait(float(hold))
            self.bms_timing.append({"id": beat_id, "start": t0, "end": self._now()})
        except CustomSkipped:
            pass
        except Exception as exc:
            emit_error(
                {
                    "kind": self._error_kind,
                    "scene_id": self.scene_id,
                    "beat_id": beat_id,
                    "object_id": self._cur_object,
                    "step_index": self._cur_step,
                    "message": str(exc)[:2000],
                }
            )
            if not self.continue_on_error:
                raise
            self._show_error_frame(beat_id)
        finally:
            self._cur_beat = None

    def _show_error_frame(self, beat_id: Any) -> None:
        import manim

        try:
            self.clear()
        except Exception:
            pass
        self.alive.clear()
        self.ctx.objs.clear()
        self.ctx.cells.clear()
        self._skipped.clear()
        rect = manim.Rectangle(
            width=manim.config.frame_width,
            height=manim.config.frame_height,
            stroke_width=0,
            fill_color=manim.ManimColor("#8B0000"),
            fill_opacity=1.0,
        ).move_to(manim.ORIGIN)
        text = manim.Text(f"Error in beat {beat_id}", color=manim.WHITE)
        self.play(manim.FadeIn(rect), manim.Write(text))
        self.wait(2)
