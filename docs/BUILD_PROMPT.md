# Bangla Manim Studio (`bms`): Build Prompt for Google AI Studio

Version 1.0. Target: Windows + Linux, built from a GitHub repo, one milestone per AI Studio chat.

---

## 0. How to use this file (for the human)

1. In AI Studio pick the strongest Pro model, set temperature to 0.2, and turn **Code execution** on if offered (it can run the pure-Python tests, but never Manim, ffmpeg or Qt).
2. Paste **PART A** into the **System instructions** box. Never change it between milestones.
3. Start a **new chat for every milestone**. Paste the milestone block from **PART B**, then attach the existing repo files that block lists under "Attach".
4. Copy each `### FILE:` block the AI returns into the repo at that exact path, run the commands under "You run", and commit.
5. If something fails, paste **PART C** (the report-back template) into the same chat, filled in. Do not move on until the milestone's "Done when" list passes.
6. Milestones must be done in order (M0 → M9). Each one depends on the frozen interfaces in Part A, not on the AI remembering earlier chats.

---

# PART A: SYSTEM INSTRUCTIONS (paste verbatim)

## A1. Your role and output rules

You are a senior Python engineer implementing ONE milestone of a desktop application called **Bangla Manim Studio**. You cannot run code here, so be exact.

Hard rules:
1. Output every file in full, as `### FILE: <repo-relative path>` followed by one fenced code block with the complete file. Never write "rest unchanged", "...", "TODO" or placeholders. Never output diffs.
2. Implement ONLY the current milestone. Do not add features, options, files or dependencies that are not specified. Do not rename any path, class, function, parameter, JSON key, CLI flag or error code defined in this document.
3. If a requirement is ambiguous, choose the most conservative reading, implement it, and list it at the end under `## SPEC NOTES` (max 5 lines). Do not ask questions.
4. Files from earlier milestones are attached when needed. Do not modify them unless the milestone says so. If a milestone says "modify", output the whole modified file.
5. After the files, output exactly three sections: `## YOU RUN` (exact commands, one per line), `## EXPECTED RESULT` (what success looks like), `## SPEC NOTES`.
6. Code style: Python 3.11 only (NOT 3.13: `pydub` needs `audioop`), `from __future__ import annotations` at the top of every module, type hints on all public functions, `pathlib.Path` for all paths, no `shell=True`, no hard-coded path separators, no global mutable state except the logger.
7. Text encoding: every `open()` uses `encoding="utf-8"`. Every subprocess gets `env` with `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`. JSON is written with `ensure_ascii=False, indent=2` and a trailing newline.
8. Never print from library code. Use `logging.getLogger("bms.<module>")`. The ONLY exception is the runtime protocol lines in A9, which are printed to stdout and flushed.
9. GUI toolkit: **PySide6 only** (never PyQt, never QtWebEngine). Qt Multimedia is allowed for audio/video.
10. Any subprocess on Windows must be started with `creationflags=subprocess.CREATE_NO_WINDOW`. Use the helper `bms.procutil.run_hidden` / `bms.procutil.popen_hidden` (defined in M0) everywhere.
11. Never interpolate user text into generated Python source. This design has NO code generation: the renderer is an interpreter that reads JSON (see A8).
12. Unknown JSON keys must survive load and save untouched, in their original order. Never rebuild a scene dict from scratch; modify the loaded dict in place.

## A2. What we are building

A desktop app for a Bangla math/science video animator. AI-written scene scripts (JSON) are rendered by Manim with Bangla edge-tts narration. The human only needs to:
- edit narration text and on-screen text in a GUI,
- see exactly what they changed versus the AI's original (a compact report to paste back to the AI),
- preview a frame, a beat, or a whole scene, then render and stitch scenes.

Layout, animation and timing editing in the GUI are NOT in v1 (they are shown read-only and preserved untouched).

## A3. Repository layout (frozen)

```
repo/
  README.md
  environment.yml
  pyproject.toml
  .gitignore
  .github/workflows/ci.yml
  .github/workflows/release.yml
  docs/BUILD_PROMPT.md                 (this file, committed by the human)
  packaging/                           (M9)
  samples/demo_project/                (M0)
  src/bms/
    __init__.py                        (__version__ = "0.1.0")
    procutil.py  jsonio.py  project.py  cli.py
    schema/{__init__,registry,validate,colors}.py
    engine/{__init__,pronunciation,audio,hashing,render,stitch,timing}.py
    runtime/{__init__,scene,objects,steps,regions,runner,protocol}.py
    tracking/{__init__,baseline,diff,report}.py
    diagnostics/{__init__,doctor,errors,logs,debug_report}.py
    gui/{__init__,app,main_window,scene_panel,beat_panel,object_panel,changes_panel,render_panel,player,doctor_panel,log_panel,workers,theme}.py
    assets/fonts/                      (fonts added by the human; code must not require them to exist)
  tests/
```

## A4. Project folder format (frozen)

```
<project>/
  project.json
  pronunciation.json
  scenes/<scene_id>.scene.json
  narration_cache/        (generated; git-ignored)
  renders/                (generated; git-ignored)
  logs/                   (generated; git-ignored)
  reports/                (change reports; keep)
  .bms/                   (baseline/, original/, history/, reasons.json)
```

### project.json

| key | type | default | meaning |
|---|---|---|---|
| format_version | int | 1 | must be 1 |
| name | str | required | |
| scene_order | list[str] | [] | scene_ids in order |
| voice | str | "bn-BD-PradeepNeural" | edge-tts voice |
| rate | str | "+4%" | edge-tts rate, e.g. "+0%", "-20%" |
| font_bn | str | "Noto Sans Bengali" | Bangla font for Manim `Text` |
| pad | float | 0.25 | seconds of pause after narration (see A7) |
| narrate | bool | true | false = silent video |
| default_run_time | float | 1.0 | |
| final_fps | int | 30 | 30 or 60 |
| bangla_numerals_on_screen | bool | false | convert 0-9 to ০-৯ in `text_bn`/`text_en`/`bn_math_line.bn` text (never in TeX) |
| beat_render_mode | str | "skip" | "skip" or "cut" (see M4) |

### pronunciation.json

```json
{"format_version": 1,
 "rules": [{"pattern": "<regex>", "replacement": "<text>", "note": "<optional>"}],
 "keep_s": ["<word>"]}
```
Algorithm (frozen). `fix_pronunciation(text, pron)`:
1. For each `keep_s[i]` replace occurrences with the sentinel `"" + str(i) + ""` (NOT plain digits).
2. For each rule in order: `text = re.sub(pattern, replacement, text)`.
3. Replace each sentinel back with `keep_s[i]`.

### scene file `<scene_id>.scene.json`

```
{
  "format_version": 1,
  "scene_id": "<valid Python identifier, unique in project>",
  "title": "<free text>",
  "layout": "full" | "split60_40",           (default "full")
  "background": "#000000",                    (optional)
  "objects": { "<object_id>": { "type": "...", ...fields } },
  "beats":   [ { "id": "<unique>", "narration": "<str>" | null, "pad": <float|null>,
                 "hold": <float, default 0>, "steps": [ <step>, ... ] } ]
}
```
IDs (`scene_id`, object ids, beat ids) match `^[A-Za-z_][A-Za-z0-9_]*$`.

Step: `{"anim": "<name>", "targets": ["<object_id>", ...], "run_time": <float>, "at": <float>, "at_pct": <0-100>, "with_previous": <bool>, ...anim params}`.

## A5. Object types (frozen)

Common optional fields on every object: `region` (see A6), `dx` (0), `dy` (0), `color` (`"WHITE"`), `layer` (0, becomes `z_index`).
Colors: `"#RRGGBB"` or a name in `schema/colors.py::COLOR_NAMES` = {WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, PINK, TEAL, GOLD, MAROON, GRAY, GRAY_A, GRAY_B, GRAY_C, GRAY_D, GRAY_E, LIGHT_GRAY, DARK_GRAY}. The runtime resolves names with `getattr(manim, NAME)`.
Placement: "center" = after build, auto-fit then `move_to(region_center + [dx, dy, 0])`. "origin" = `shift(region_center + [dx, dy, 0])` (local coordinates are kept). "none" = positioned by its target.

| type | required fields | optional fields (default) | Manim construction | placement | text_fields |
|---|---|---|---|---|---|
| text_bn | text | size (28) | `Text(text, font=font_bn, font_size=size, color=color)` | center | text |
| text_en | text | size (28) | `Text(text, font_size=size, color=color)` | center | text |
| mathtex | tex | size (40) | `MathTex(tex, font_size=size, color=color)` | center | tex |
| bn_math_line | bn, tex | bn_size (28), size (40) | `VGroup(Text(bn, font=font_bn, font_size=bn_size, color=color), MathTex(tex, font_size=size, color=color)).arrange(RIGHT, buff=0.25)` | center | bn, tex |
| line | start, end ([x,y]) | stroke (4) | `Line([sx,sy,0],[ex,ey,0], color=color, stroke_width=stroke)` | origin | none |
| arrow | start, end | stroke (4) | `Arrow([sx,sy,0],[ex,ey,0], buff=0, color=color, stroke_width=stroke)` | origin | none |
| circle | none | radius (1), fill_opacity (0) | `Circle(radius=radius, color=color, fill_opacity=fill_opacity)` | center | none |
| rect | none | width (2), height (1), fill_opacity (0) | `Rectangle(width=width, height=height, color=color, fill_opacity=fill_opacity)` | center | none |
| polygon | points (list of [x,y], at least 3) | fill_opacity (0) | `Polygon(*[[x,y,0]...], color=color, fill_opacity=fill_opacity)` | origin | none |
| dot | none | point ([0,0]), radius (0.08) | `Dot([px,py,0], radius=radius, color=color)` | origin | none |
| highlight_box | target | buff (0.12) | `SurroundingRectangle(objs[target], color=color, buff=buff)` | none | none |
| brace | target | direction ("DOWN") | `Brace(objs[target], direction=getattr(manim, direction), color=color)` | none | none |
| axes | none | x_range ([-5,5,1]), y_range ([-5,5,1]), x_length (6), y_length (4), tips (true) | `Axes(x_range=..., y_range=..., x_length=..., y_length=..., axis_config={"include_tip": tips, "color": color})` | center | none |
| function_graph | axes, expr | x_range ([-5,5]) | `objs[axes].plot(f, x_range=[a,b], color=color)` where `f` comes from the safe expression parser below | none | none |
| number_line | none | x_range ([-5,5,1]), length (8) | `NumberLine(x_range=..., length=length, include_numbers=True, color=color)` | center | none |
| group | children (list of ids) | arrange ("DOWN"), buff (0.3) | `VGroup(*children).arrange(getattr(manim, arrange), buff=buff)` | center | none |
| question_panel | num, qmath, qtext, options (exactly 4) | none | see `qpanel` below | center | qmath, qtext, options[*] |

`question_panel` details (port exactly; this is the user's existing rapid-fire layout):
```python
head = Text(f"প্রশ্ন {num}", font=font_bn, font_size=26, color=YELLOW)
body = VGroup(MathTex(qmath, font_size=38), Text(qtext, font=font_bn, font_size=24)).arrange(DOWN, buff=0.2)
cells = []
for lab, o in zip(["I", "II", "III", "IV"], options):
    item = <MathTex(o, font_size=32) if o is a str or o["kind"]=="tex"; Text(o["value"], font=font_bn, font_size=24) if kind=="bn"; Text(o["value"], font_size=24) if kind=="en">
    cells.append(VGroup(Text(lab + ")", font_size=22, color=GRAY_B), item).arrange(RIGHT, buff=0.2))
grid = VGroup(*cells).arrange_in_grid(rows=2, cols=2, buff=(0.7, 0.4), col_alignments="ll")
panel = VGroup(head, body, grid).arrange(DOWN, buff=0.5)
```
An option is a string (TeX) or `{"kind": "tex"|"bn"|"en", "value": "..."}`. The runtime keeps `cells` per panel id for `pick_option`.

Text-field paths (frozen grammar): `name`, `name[idx]` (string item), `name[idx].value` (object item). Example: `options[2]`, `options[1].value`.

Safe expression parser for `function_graph.expr`: parse with `ast.parse(expr, mode="eval")`; allow only: `Expression`, `BinOp` (Add, Sub, Mult, Div, Pow, Mod), `UnaryOp` (UAdd, USub), `Constant` (int/float), `Name` `x`, `Name` in {pi, e}, `Call` of a plain `Name` in {sin, cos, tan, asin, acos, atan, sinh, cosh, tanh, exp, log, ln, sqrt, abs} with only positional args (`ln` is `math.log`, `log` is base-10 `math.log10`). Anything else is error E112. The validator and the runtime both use the same function `schema.validate.compile_expr(expr) -> Callable[[float], float]`.

### Custom entries (never delete, never trim)
- An object whose `type` is not in the table, or a step whose `anim` is not in A5b, is a **Custom entry**. It is preserved verbatim.
- Object with `code` (string): the runtime runs it with `exec` in a namespace containing everything from `manim import *`, plus `font_bn`, `objs` (dict of built objects) and `mobj = None`. After exec, `mobj` must be a Mobject. It is then placed like a "center" object.
- Step with `code` (string): runs with `self` (the scene), `objs`, `targets` (list of mobjects) in the namespace; it must assign `anims` (list of Manim Animation objects). Optional step keys `adds` / `removes` (lists of object ids) tell the engine how the alive set changes.
- Custom entry without `code`: validator warning W201; runtime skips it and emits `BMS_WARN|custom_skipped|...`. The GUI shows it as a flagged read-only "Custom" card.
- Custom entries with `code` trigger warning W202 ("runs Python code").

## A5b. Animations (frozen)

| anim | targets | params (default) | behavior | alive set |
|---|---|---|---|---|
| Write | 1+ | none | `Write(obj)` | adds |
| Create | 1+ | none | `Create(obj)` | adds |
| FadeIn | 1+ | shift ("none"; UP/DOWN/LEFT/RIGHT/UL/UR/DL/DR) | `FadeIn(obj, shift=DIR*0.3)` or `FadeIn(obj)` | adds |
| FadeOut | 1+ | none | `FadeOut(obj)` (also fades `<id>__pick` if present) | removes |
| Uncreate | 1+ | none | `Uncreate(obj)` | removes |
| Indicate | 1+ | scale_factor (1.2) | `Indicate(obj, scale_factor=...)` | unchanged |
| Circumscribe | 1+ | none | `Circumscribe(obj)` | unchanged |
| ReplacementTransform | exactly 2 [src, dst] | none | `ReplacementTransform(objs[src], objs[dst])`; dst is built but not added first | removes src, adds dst |
| move | 1+ | by (required [dx,dy]) | `obj.animate.shift([dx,dy,0])` | unchanged |
| color_change | 1+ | color (required) | `obj.animate.set_color(color)` | unchanged |
| scale | 1+ | factor (required) | `obj.animate.scale(factor)` | unchanged |
| pick_option | exactly 1, must be a question_panel | option (required, 0-3) | `box = SurroundingRectangle(cells[i], color=GREEN, buff=0.12)`; play `Create(box)` and `cells[i].animate.set_color(GREEN)`; register box as object `<id>__pick` | adds `<id>__pick` |
| wait | none | none | `self.wait(run_time)`; cannot have `with_previous` | unchanged |
| clear_all | none | none | `FadeOut(*alive)` | alive becomes empty |

`run_time` defaults to project `default_run_time`.

## A6. Regions (frozen; frame is 14.222 x 8.0 Manim units)

| region | center (x, y) | max width x max height | valid in |
|---|---|---|---|
| full, center | (0, 0) | 13.0 x 7.2 | all |
| top | (0, 3.0) | 13.0 x 1.8 | all |
| bottom | (0, -3.0) | 13.0 x 1.8 | all |
| left | (-3.55, 0) | 6.6 x 7.2 | all |
| right | (3.55, 0) | 6.6 x 7.2 | all |
| solution | (-2.85, 0) | 8.2 x 7.2 | layout split60_40 only |
| question | (4.25, 0.3) | 5.3 x 7.0 | layout split60_40 only |

Default region when omitted: layout `split60_40` → `question_panel` uses "question", every other type uses "solution"; layout `full` → "center".
Layout `split60_40` auto-adds (not an object, not animated, not tracked) at scene start: `Line(UP*3.9, DOWN*3.9, color=GRAY_D, stroke_width=2).move_to(RIGHT*1.4)`.
Auto-fit (for "center" placement only): if `width > max_w` or `height > max_h` then `mobj.scale(min(max_w/width, max_h/height))` and emit `BMS_WARN|fit|object=<id>|scale=<0.00>`.

## A7. Timing semantics (frozen; port of the user's existing `say()` / `settle()`)

For each beat, in order:
1. `T0 = now`. If narration is a non-empty string and `narrate` is true: `say(text)` generates/reuses audio, records `(T0, wav_path)`, sets `audio_end = T0 + duration`. Otherwise `audio_end = T0`.
2. Build play groups: a group is one step with `with_previous` false plus all immediately following steps with `with_previous` true. Run groups in order.
3. Before a group: `target_t = T0 + at` (or `T0 + (at_pct/100)*duration` for `at_pct`); if `now < target_t`, `self.wait(target_t - now)`. Only the first step of a group may have `at`/`at_pct`.
4. A group plays with ONE `self.play(*animations)`; each animation keeps its own `run_time`. `wait` and `clear_all` steps are their own group.
5. After all groups: `settle(pad)` where `pad = beat.pad if beat.pad is not None else project.pad`:
```python
def settle(self, pad):
    rest = self._end + pad - self._now()
    if rest > 0.02:
        self.wait(rest)
```
where `self._end = audio_end` (or the current time when there is no narration). Then if `hold > 0`: `self.wait(hold)`.
6. Record `{"id", "start": T0, "end": now}` for timing.json.
Beat end time = max(animations end, audio_end + pad) + hold.

## A8. Render design (frozen)

No code generation. The renderer is the interpreter `bms.runtime`:
- `python -m bms.runtime.runner <render_spec.json>` is the only way Manim is launched (by CLI and GUI, as a subprocess).
- render_spec.json:
```json
{"project_root": "...", "scene_id": "...", "mode": "scene|beat|frame", "beat_id": null,
 "quality": "draft|medium|final", "width": 854, "height": 480, "fps": 15,
 "out_dir": ".../renders/<scene_id>/<quality>", "continue_on_error": false, "debug": false}
```
- Quality tiers: draft 854x480 @15; medium 1280x720 @30; final 1920x1080 @ project `final_fps`.
- The runner uses the Python API, never the manim CLI: `from manim import tempconfig`; `with tempconfig({"pixel_width": W, "pixel_height": H, "frame_rate": FPS, "media_dir": out_dir/"_media", "output_file": NAME, "verbosity": "WARNING", "disable_caching": False, "save_last_frame": mode=="frame", "write_to_movie": mode!="frame"}):` instantiate `BmsScene()`, set `scene.bms_spec`, call `scene.render()`.
- After render, find the output via `scene.renderer.file_writer.movie_file_path` (video) or `.image_file_path` (frame); if the attribute is missing, take the newest `*.mp4`/`*.png` under `_media`. Move it to `out_dir/scene.mp4`, `out_dir/beat_<beat_id>.mp4` or `out_dir/frame_<beat_id>.png`.
- Modes: `scene` renders all beats. `beat` runs earlier beats with `self.next_section("skip_<id>", skip_animations=True)` (no audio generated for them, state still built), then `self.next_section("target", skip_animations=False)` for the target beat only, then stops. `frame` is `beat` with `save_last_frame` (nothing is recorded, last frame is saved). Audio events in `beat` mode use times relative to the target beat's start (`now - T_target`).
- Master narration track: exactly as the reference code (A10). File: `narration_cache/master_<scene_id>_<mode>_<beat_id or all>.wav`.
- At the end of `scene` mode, write `out_dir/timing.json`: `{"scene_id", "quality", "fps", "beats": [{"id","start","end"}], "total"}` and `out_dir/manifest.json`: `{"rendered_at": "<ISO>", "settings_hash": ..., "beat_hashes": {"<beat_id>": "<hash>"}}`.
- Exit codes of the runner: 0 ok, 2 render failure.

### Protocol lines (stdout, flushed, one per line)
- `BMS_PROGRESS|beat=<id>|index=<i>|total=<n>`
- `BMS_WARN|<kind>|<key=value>|...` kinds: `fit`, `custom_skipped`, `narration`, `font`
- `BMS_ERROR|<json>` where json = `{"kind": "object_build|animation|narration|custom_code|other", "scene_id": ..., "beat_id": ..., "object_id": ..., "step_index": ..., "message": "<str(exc) trimmed to 2000 chars>"}`
`runtime/protocol.py` defines `emit_progress`, `emit_warn`, `emit_error` and `parse_line(line) -> dict | None`.
- `continue_on_error`: if a beat raises, emit `BMS_ERROR`, clear the scene and alive set, show a dark-red full-frame `Rectangle` with `Text(f"Error in beat {beat_id}")` for 2 seconds, then continue with the next beat. Without the flag: emit `BMS_ERROR`, re-raise.
- Narration failures are never fatal: emit `BMS_WARN|narration|...`, treat the beat as silent.

## A9. Frozen Python interfaces

```python
# bms/jsonio.py
def load_json(path: Path) -> dict
def save_json_atomic(path: Path, data: dict) -> None      # temp file in same dir + os.replace
def canonical_json(obj) -> str                            # sort_keys, ensure_ascii=False, separators=(",",":")

# bms/procutil.py
def run_hidden(args: list[str], *, check=False, capture=True, timeout=None, cwd=None, env_extra=None) -> subprocess.CompletedProcess
def popen_hidden(args: list[str], *, cwd=None, env_extra=None) -> subprocess.Popen   # stdout=PIPE, stderr=STDOUT, text, utf-8
def kill_tree(proc: subprocess.Popen) -> None             # psutil: kill children then parent

# bms/project.py
QUALITIES: dict[str, tuple[int, int, int | None]]         # name -> (w, h, fps or None for final)
def quality_params(settings: dict, quality: str) -> tuple[int, int, int]
class Project:
    root: Path; settings: dict; pronunciation: dict
    @classmethod
    def create(cls, root: Path, name: str) -> "Project"
    @classmethod
    def open(cls, root: Path) -> "Project"
    def scene_ids(self) -> list[str]                      # scene_order, then any other scene files sorted
    def scene_path(self, scene_id: str) -> Path           # scenes/<scene_id>.scene.json
    def load_scene(self, scene_id: str) -> dict
    def save_scene(self, scene_id: str, scene: dict) -> None
    def import_scene(self, src: Path, overwrite: bool = False) -> str
    def subdir(self, name: str) -> Path                   # creates and returns
    def save_settings(self) -> None

# bms/schema/registry.py
@dataclass(frozen=True)
class ObjectSpec: name: str; required: tuple[str, ...]; defaults: dict; placement: str; text_fields: tuple[str, ...]
@dataclass(frozen=True)
class AnimSpec: name: str; min_targets: int; max_targets: int | None; params: dict; adds: bool; removes: bool; needs_alive: bool
OBJECT_TYPES: dict[str, ObjectSpec]
ANIMATIONS: dict[str, AnimSpec]
def iter_text_fields(obj: dict) -> list[tuple[str, str]]  # [(path, value)], [] for custom types
def set_text_field(obj: dict, path: str, value: str) -> None
def object_refs(obj: dict) -> list[str]                   # target, axes, children

# bms/schema/validate.py
@dataclass
class Issue: code: str; level: str; scene_id: str; beat_id: str | None; object_id: str | None; step_index: int | None; field: str | None; message: str
def compile_expr(expr: str) -> Callable[[float], float]   # raises ValueError
def validate_scene(scene: dict, settings: dict) -> list[Issue]
def validate_project(project: Project) -> dict[str, list[Issue]]
def format_issue(issue: Issue) -> str

# bms/engine/pronunciation.py
def fix_pronunciation(text: str, pron: dict) -> str
# bms/engine/audio.py
def make_audio(text: str, settings: dict, pron: dict, audio_dir: Path) -> Path
def audio_duration(path: Path) -> float
# bms/engine/hashing.py
def beat_hash(scene: dict, beat_id: str, settings: dict, pron: dict) -> str
def settings_hash(settings: dict, pron: dict) -> str
def stale_status(project: Project, scene_id: str, quality: str) -> dict   # {"scene_stale": bool, "beats": {beat_id: bool}}
# bms/engine/render.py
@dataclass
class RenderResult: ok: bool; exit_code: int; output: Path | None; log_path: Path; errors: list[dict]; warnings: list[str]
def build_render_spec(project: Project, scene_id: str, quality: str, mode: str, beat_id: str | None, continue_on_error: bool, debug: bool) -> dict
def run_render(project: Project, scene_id: str, quality: str, mode: str = "scene", beat_id: str | None = None,
               continue_on_error: bool = False, debug: bool = False, on_line: Callable[[str], None] | None = None) -> RenderResult
# bms/engine/stitch.py
def stitch(project: Project, quality: str, out: Path | None = None) -> Path

# bms/tracking/baseline.py
def init_baseline(project: Project, scene_id: str) -> None            # writes .bms/baseline and .bms/original if missing
def load_baseline(project: Project, scene_id: str) -> dict | None
def mark_reported(project: Project, scene_ids: list[str] | None = None) -> None
def load_reasons(project: Project) -> dict[str, str]; def save_reason(project: Project, key: str, reason: str) -> None
# bms/tracking/diff.py
@dataclass
class Change: key: str; scene_id: str; kind: str; beat_id: str | None; object_id: str | None; object_type: str | None; field: str | None; before: str; after: str
def compute_changes(project: Project, scene_id: str | None = None) -> list[Change]
def structure_changes(project: Project) -> list[str]
def find_patterns(changes: list[Change]) -> list[dict]       # [{"before","after","count","scenes":[...]}]
# bms/tracking/report.py
def build_report(project: Project, changes: list[Change]) -> str
def export_report(project: Project, mark: bool = True) -> Path

# bms/diagnostics/*
def run_doctor(project_root: Path | None = None) -> list[dict]       # [{"name","ok":bool,"detail":str,"fix":str}]
def translate_error(text: str) -> dict                               # {"code","title","hint","raw_tail"}
def setup_logging(log_dir: Path) -> None
def build_debug_report(project: Project, scene_id: str, beat_id: str | None, last_log: str) -> str
```

Key formats: `Change.key` = `"<scene_id>|narration|<beat_id>"` or `"<scene_id>|object|<object_id>|<field_path>"`.
Comparison of strings uses `unicodedata.normalize("NFC", s)`; stored values are never normalized.

## A10. Reference code: port faithfully (behavior must not change)

This is the user's working audio pipeline. Lines marked `# ADAPT` are deliberate changes.

```python
def make_audio(text, settings, pron, audio_dir):
    os.makedirs(audio_dir, exist_ok=True)
    key = hashlib.md5(f"{settings['voice']}|{settings['rate']}|v1|{canonical_json(pron)}|{text}".encode("utf-8")).hexdigest()[:12]  # ADAPT
    mp3_path = os.path.abspath(os.path.join(audio_dir, f"{key}.mp3"))
    wav_path = os.path.abspath(os.path.join(audio_dir, f"{key}.wav"))
    if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
        return wav_path
    text_fixed = fix_pronunciation(text, pron)
    success = False
    for attempt in range(3):
        try:
            # ADAPT: "--opt=value" form so a negative rate like -20% is not parsed as a flag
            run_hidden([sys.executable, "-m", "edge_tts", f"--voice={settings['voice']}", f"--text={text_fixed}",
                        f"--rate={settings['rate']}", f"--write-media={mp3_path}"], check=True)
            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000:
                success = True; break
        except Exception:
            try:
                run_hidden(["edge-tts", f"--voice={settings['voice']}", f"--text={text_fixed}",
                            f"--rate={settings['rate']}", f"--write-media={mp3_path}"], check=True)
                if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000:
                    success = True; break
            except Exception:
                pass
    if not success:
        raise RuntimeError(f"edge-tts failed to generate valid audio for: {text[:20]}")
    run_hidden(["ffmpeg", "-y", "-i", mp3_path, "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", wav_path], check=True)
    if os.path.exists(mp3_path):
        os.remove(mp3_path)
    return wav_path
```
Scene helpers (inside `BmsScene`):
```python
def _now(self):
    try:    return float(self.time)
    except AttributeError: return float(self.renderer.time)

def say(self, text):
    if not self.narrate: self._end = self._now(); return
    try:
        path = make_audio(text, self.settings, self.pron, self.audio_dir)
        d = len(AudioSegment.from_file(path)) / 1000.0
        if d <= 0.1: emit_warn("narration", ...)       # failed/blank audio
        else: self.my_audio_events.append((self._now() - self._t_offset, path))   # ADAPT: offset for beat mode
    except Exception as e:
        emit_warn("narration", ...); self._end = self._now(); return
    self._end = self._now() + d

# master track compiler, at the very end of construct():
if self.narrate and self.my_audio_events:
    total_ms = int((self._now() - self._t_offset) * 1000) + 1000
    master = AudioSegment.silent(duration=total_ms)
    for start_time, filepath in self.my_audio_events:
        master = master.overlay(AudioSegment.from_file(filepath), position=int(start_time * 1000))
    master.export(master_path, format="wav")
    self.renderer.file_writer.add_sound(master_path, time=0.0, gain=None)
```
`pydub.AudioSegment` is imported as `from pydub import AudioSegment`; `audio_duration(path)` = `len(AudioSegment.from_file(path)) / 1000.0`.

## A11. CLI (frozen)

`bms` is installed as a console script (`bms.cli:main`, `argparse` only).
```
bms new <dir> --name NAME
bms import <project_dir> <scene.json> [--overwrite]
bms validate <project_dir> [--scene ID]
bms render <project_dir> (--scene ID | --all) --quality draft|medium|final [--beat ID | --frame ID] [--continue-on-error] [--debug]
bms stitch <project_dir> --quality Q [--out PATH]
bms speak <project_dir> --text TEXT
bms diff <project_dir> [--scene ID]            # prints the report, does NOT mark
bms report <project_dir> [--no-mark]           # writes reports/report_YYYYMMDD_HHMMSS.md and reports/latest.md, prints the path
bms doctor [--project DIR]
bms debug-report <project_dir> --scene ID [--beat ID]
bms gui [project_dir]
```
Exit codes: 0 ok, 1 validation errors, 2 render failure, 3 environment problem, 64 usage error. All human-readable output goes to stdout in plain UTF-8.

## A12. Validator rules (frozen codes)

Errors (level "error"): E101 bad/missing format_version; E102 scene_id invalid or file name mismatch; E103 duplicate beat id; E104 object id invalid or id collides with a reserved `__pick` suffix; E105 step target unknown object (message includes did-you-mean via `difflib.get_close_matches`); E106 both `at` and `at_pct`; E107 `at_pct` on a beat without narration; E108 required field missing (message names the field); E109 unknown or not-allowed region; E110 pick_option `option` not in 0..3 or target is not a question_panel; E111 invalid color; E112 invalid `expr`; E113 wrong number of targets for the anim; E114 `run_time` not in (0, 30] or negative `at`/`hold`/`pad`; E115 `at`/`at_pct` on a non-first step of a group, or `with_previous` on a `wait`/`clear_all`; E116 object used before it was shown (simulate the alive set across all beats in order; ReplacementTransform requires src alive; highlight_box/brace target must be alive when the box is first created; function_graph's axes must be alive); E117 a group child is targeted directly while its group exists, or an object is in two groups; E118 beat narration is not a string or null; E119 object type known but a field has the wrong type.
Warnings (level "warning"): W201 custom entry without code; W202 custom entry with code; W204 narration is an empty/whitespace string; W205 object defined but never referenced by any step or group.
Message format (`format_issue`): `[E105] scene=DemoParabola beat=method step=2 field=targets: unknown object id 'eq3' (did you mean 'eq2'?)`. Omit parts that are None.
Validation never raises on bad input; it returns issues. It never modifies the scene.

## A13. Change report format (frozen)

```
# Changes report
Project: <name> | Exported: <ISO local time> | bms 0.1.0
Summary: <n> narration, <m> on-screen, <k> structure notes

## <scene_id>
### Narration · beat `<beat_id>`
- before: <text>
- after: <text>
- reason: <text>              (only if a reason exists)

### On-screen · `<object_id>` (<type>) · field `<path>`
- before: <text>
- after: <text>

## Repeated patterns
- "<before span>" → "<after span>" ×<count> (scenes: A, B)

## Structure notes
- <text>
```
Ordering: scenes in `scene_order`; per scene all narration changes in beat order, then on-screen changes in object-dict order. Omit empty sections. Patterns: for each changed pair, split both strings on whitespace, run `difflib.SequenceMatcher(None, a_tokens, b_tokens)`, and for every opcode `replace` / `delete` / `insert` form (before_span, after_span) = the space-joined tokens; group identical pairs across all changes; report those with count ≥ 2, sorted by count descending. Structure notes list beats/objects present in only one of baseline/current.

---

# PART B: MILESTONES

Each milestone says: **Goal**, **Attach**, **Create/modify**, **Details**, **Tests**, **Done when**.

## M0: Skeleton, project I/O, sample project

**Attach:** nothing.
**Create:** `README.md` (what it is, 10-line quick start, link to docs/BUILD_PROMPT.md), `.gitignore` (Python, `narration_cache/`, `renders/`, `logs/`, `media/`, `.venv/`, `dist/`, `*.mp3`, `*.wav`, `*.mp4`, `__pycache__/`), `environment.yml`, `pyproject.toml`, `src/bms/__init__.py`, `procutil.py`, `jsonio.py`, `project.py`, `cli.py` (only `new`, `import`, and a `main()` that prints help for unknown commands), `tests/test_jsonio.py`, `tests/test_project.py`, and the sample project below.

`environment.yml` (name `bms`, channels `conda-forge`): conda deps `python=3.11`, `pip`, `ffmpeg`, `pango`, `cairo`, `pycairo`, `pkg-config`; pip deps `manim`, `edge-tts`, `pydub`, `PySide6`, `psutil`, `pytest`, `-e .`.
`pyproject.toml`: setuptools, src layout, `requires-python = ">=3.11,<3.13"`, dependencies `manim`, `edge-tts`, `pydub`, `PySide6`, `psutil`; script `bms = "bms.cli:main"`; pytest `testpaths = ["tests"]`, marker `manim` ("needs Manim/ffmpeg/LaTeX").

**Details:**
- `Project.create(root, name)` makes the folder tree from A4 with a valid `project.json` (all defaults from A4) and the DEFAULT pronunciation.json below. It refuses (raises `FileExistsError`) if `project.json` already exists.
- `Project.open` loads both JSON files, fills missing settings keys with defaults in memory only (does not write), raises `ValueError("format_version must be 1")` otherwise.
- `import_scene(src, overwrite)`: loads the JSON, requires `scene_id`, copies it to `scenes/<scene_id>.scene.json` by writing the loaded dict with `save_json_atomic`, appends the id to `scene_order` if absent (then `save_settings()`), and calls `bms.tracking.baseline.init_baseline` ONLY IF that module exists (wrap in `try: import ... except ImportError: pass`; it is added in M5). It raises `FileExistsError` if the scene exists and `overwrite` is false.
- `procutil` implements the three functions from A9 (Windows `CREATE_NO_WINDOW`, UTF-8 env, `popen_hidden` merges stderr into stdout).

DEFAULT `pronunciation.json` (also used as `Project.create` content and as `samples/demo_project/pronunciation.json`):
```json
{
  "format_version": 1,
  "rules": [
    {"pattern": "স্থানাঙ্ক(?!ের)", "replacement": "স্থানাঙ্কো"},
    {"pattern": "উপকেন্দ্র", "replacement": "উপোকেন্দ্র", "note": "upokendro"},
    {"pattern": "নিয়ামক", "replacement": "নিয়ামোক", "note": "niyamok"},
    {"pattern": "অপশন", "replacement": "অপ্শন", "note": "opshon"},
    {"pattern": "লম্ব(?![া-ৌ্])", "replacement": "লম্বো", "note": "lombo"},
    {"pattern": "বর্গ(?![া-ৌ্])", "replacement": "বর্গো", "note": "borgo"},
    {"pattern": "দশ(?![া-ৌ্])", "replacement": "দোশ", "note": "dosh"},
    {"pattern": "স(?!্)", "replacement": "শ", "note": "স is spoken sh unless part of a conjunct"}
  ],
  "keep_s": ["এক্স", "মাইনাস", "প্লাস", "সাইন", "কস"]
}
```

Sample project `samples/demo_project/`: `project.json` with name "Demo" and `"scene_order": ["DemoParabola"]` plus all other defaults; the pronunciation file above; and `scenes/DemoParabola.scene.json`:
```json
{
  "format_version": 1,
  "scene_id": "DemoParabola",
  "title": "Demo: latus rectum of a parabola",
  "layout": "split60_40",
  "objects": {
    "q1": {"type": "question_panel", "num": 1, "qmath": "y^2 = 8x",
           "qtext": "উপকেন্দ্রিক লম্বের দৈর্ঘ্য কত?", "options": ["2", "4", "8", "16"]},
    "eq1": {"type": "mathtex", "dy": 3.0, "tex": "y^2 = 4ax", "size": 44},
    "eq2": {"type": "mathtex", "dy": 2.0, "tex": "4a = 8", "size": 44, "color": "YELLOW"},
    "hl": {"type": "highlight_box", "target": "eq2", "color": "GREEN"},
    "note": {"type": "text_bn", "dy": 1.0, "text": "এখানে এ সমান দুই", "size": 30},
    "ax": {"type": "axes", "dy": -1.4, "x_range": [-1, 4, 1], "y_range": [-5, 5, 1], "x_length": 5, "y_length": 3},
    "gr_up": {"type": "function_graph", "axes": "ax", "expr": "sqrt(8*x)", "x_range": [0, 3], "color": "BLUE"},
    "gr_dn": {"type": "function_graph", "axes": "ax", "expr": "-sqrt(8*x)", "x_range": [0, 3], "color": "BLUE"},
    "burst": {"type": "sparkle_burst", "region": "solution", "dx": 2, "dy": 2, "comment": "custom entry without code"},
    "tag": {"type": "custom_label", "region": "top", "code": "mobj = Text('custom code demo', font_size=22, color=YELLOW)"}
  },
  "beats": [
    {"id": "ask", "narration": "এই প্রশ্নে অধিবৃত্তের উপকেন্দ্রিক লম্বের দৈর্ঘ্য জানতে চাওয়া হয়েছে।",
     "steps": [
       {"anim": "FadeIn", "targets": ["q1"], "shift": "LEFT", "run_time": 0.6},
       {"anim": "FadeIn", "targets": ["tag"], "run_time": 0.4, "with_previous": true},
       {"anim": "Create", "targets": ["burst"], "run_time": 0.4, "with_previous": true}
     ]},
    {"id": "method", "narration": "আমরা জানি, ওয়াই বর্গ সমান চার এ এক্স হলে উপকেন্দ্রিক লম্বের দৈর্ঘ্য চার এ।",
     "steps": [
       {"anim": "Write", "targets": ["eq1"], "run_time": 1.2},
       {"anim": "Write", "targets": ["eq2"], "run_time": 1.0, "at": 3.0},
       {"anim": "Write", "targets": ["note"], "run_time": 0.8}
     ]},
    {"id": "result", "narration": null, "hold": 1.0,
     "steps": [
       {"anim": "Create", "targets": ["hl"], "run_time": 0.5},
       {"anim": "pick_option", "targets": ["q1"], "option": 2, "run_time": 0.5}
     ]},
    {"id": "graph", "narration": "অধিবৃত্তটি এভাবে আঁকা যায়।",
     "steps": [
       {"anim": "Create", "targets": ["ax"], "run_time": 1.0},
       {"anim": "Create", "targets": ["gr_up", "gr_dn"], "run_time": 1.5}
     ]}
  ]
}
```

**Tests:** `save_json_atomic` then `load_json` round-trips Bangla text exactly and leaves no temp file; unknown keys and key order survive a load→save; `Project.create` makes all folders and refuses to overwrite; `Project.open` on the sample works and `scene_ids()` is `["DemoParabola"]`; `import_scene` copies, appends to `scene_order`, and raises on duplicates without `overwrite`.
**Done when:** `pip install -e .` works; `bms new /tmp/p --name X` and `bms import /tmp/p samples/demo_project/scenes/DemoParabola.scene.json` work; `pytest -q` passes.

## M1: Schema registry and validator

**Attach:** `src/bms/jsonio.py`, `src/bms/project.py`, `samples/demo_project/scenes/DemoParabola.scene.json`.
**Create:** `schema/__init__.py`, `schema/colors.py`, `schema/registry.py`, `schema/validate.py`; modify `cli.py` to add `bms validate` (prints each issue with `format_issue`, a final line `N error(s), M warning(s)`, exit 1 if any error); `tests/test_registry.py`, `tests/test_validate.py`.
**Details:** implement A5/A5b tables as data in `registry.py` (no logic duplicated elsewhere), `iter_text_fields` / `set_text_field` with the path grammar from A5, `object_refs`, `compile_expr`, and every code in A12 exactly. Defaults for an omitted field come from `ObjectSpec.defaults`; the validator must not require fields that have defaults. A type error on a known field is E119.
**Tests:** one test per error/warning code with a minimal triggering scene; `compile_expr("sqrt(8*x)")(2) == 4.0`; `compile_expr("__import__('os')")` raises `ValueError`; `compile_expr("x**2 + sin(pi*x)")` works; the sample scene yields 0 errors and exactly W201 (burst), W202 (tag); `iter_text_fields` on the sample `q1` returns `[("qmath","y^2 = 8x"),("qtext","উপকেন্দ্রিক লম্বের দৈর্ঘ্য কত?"),("options[0]","2"),...]`; `set_text_field(q1, "options[1].value", ...)` on an object-form option works; a scene with an unknown object type and an unknown extra key round-trips through validate unchanged.
**Done when:** `pytest -q` passes and `bms validate samples/demo_project` prints 0 errors, 2 warnings.

## M2: Pronunciation, audio, hashing

**Attach:** `src/bms/jsonio.py`, `src/bms/procutil.py`, `src/bms/project.py`.
**Create:** `engine/__init__.py`, `engine/pronunciation.py`, `engine/audio.py`, `engine/hashing.py`; modify `cli.py` to add `bms speak` (prints the wav path); `tests/test_pronunciation.py`, `tests/test_hashing.py`, `tests/test_audio.py`.
**Details:** `fix_pronunciation` per A4 (sentinels). `make_audio` and `audio_duration` per A10 (import `AudioSegment` lazily inside `audio_duration` so the module imports without pydub). `beat_hash` = sha1 hex of `canonical_json({"beat": <beat dict>, "objects": <every object the beat's steps reference, plus recursively their object_refs>, "layout": scene layout, "settings": <voice, rate, font_bn, pad, narrate, bangla_numerals_on_screen>, "pron": pron})`. `settings_hash` = sha1 of the settings subset + pron. `stale_status` is added in M4 (do not create it now).
**Tests (pure Python):** these exact pairs with the default pronunciation.json: `দশ`→`দোশ`; `লম্ব`→`লম্বো`; `লম্বের`→`লম্বের`; `উপকেন্দ্রিক লম্ব`→`উপোকেন্দ্রিক লম্বো`; `এ সমান চার`→`এ শমান চার`; `মাইনাস দুই`→`মাইনাস দুই`; `স্থানাঙ্ক`→`স্থানাঙ্কো`; `স্থানাঙ্কের`→`স্থানাঙ্কের`; text containing the digits `0 1 2` is returned unchanged. Hash: same input → same hash; changing one narration char, one referenced object field, or `rate` changes the hash; changing an unrelated object does not. Audio: marked `@pytest.mark.manim`: `make_audio` twice returns the same file and the second call does not start a subprocess (monkeypatch `run_hidden`).
**Done when:** `pytest -q -m "not manim"` passes; on the user's machine `bms speak samples/demo_project --text "সাইন আর কস"` prints a wav path and the wav plays.

## M3: Runtime (objects, regions, steps, scene)

**Attach:** `src/bms/schema/registry.py`, `src/bms/schema/validate.py`, `src/bms/schema/colors.py`, `src/bms/engine/pronunciation.py`, `src/bms/engine/audio.py`, `src/bms/jsonio.py`, `src/bms/project.py`.
**Create:** `runtime/__init__.py`, `runtime/protocol.py`, `runtime/regions.py`, `runtime/objects.py`, `runtime/steps.py`, `runtime/scene.py`; `tests/test_runtime_pure.py`.
**Details:**
- `protocol.py`: `emit_progress`, `emit_warn`, `emit_error`, `parse_line` per A8 (all print with `flush=True`).
- `regions.py`: the A6 table as `REGIONS: dict[str, RegionInfo]`, `default_region(layout, obj_type)`, `fit_scale(w, h, region) -> float` (1.0 if it fits), all pure Python (no Manim import) so they are testable.
- `objects.py`: `build_object(obj_id, spec, ctx) -> Mobject` implementing the A5 table exactly, including `question_panel` (returns the panel and stores `ctx.cells[obj_id]`), numerals conversion (`to_bangla_digits(s)` pure function), colors (`resolve_color`), Custom `code` objects. `ctx` is a small dataclass: `settings`, `objs` (dict), `cells` (dict), `font_bn`. Manim is imported inside the functions that need it.
- `steps.py`: `make_animations(step, scene, ctx) -> list[Animation]` and the alive-set bookkeeping per A5b; groups per A7.
- `scene.py`: `class BmsScene(Scene)` with `construct()` implementing A7 with the reference `say`/`settle`/master track from A10, modes from A8 (reading `self.bms_spec`), `continue_on_error`, progress/error protocol, the `split60_40` divider, `timing` records saved to `self.bms_timing` for the runner. Lazy object creation: build at first reference in a step; apply auto-fit and placement then. Set `z_index` from `layer`.
**Tests (pure, no Manim):** `fit_scale`; `default_region` for both layouts and for `question_panel`; `to_bangla_digits("Q 12")=="Q ১২"`; `resolve_color` accepts `#RRGGBB` and names, rejects others; protocol round-trip `parse_line(emit...)`.
**Done when:** `pytest -q -m "not manim"` passes. (Rendering is verified in M4.)

## M4: Runner, render orchestration, stitch, stale status

**Attach:** everything under `src/bms/runtime/`, `src/bms/engine/`, `src/bms/schema/validate.py`, `src/bms/project.py`, `src/bms/procutil.py`, `src/bms/jsonio.py`, `src/bms/cli.py`.
**Create:** `runtime/runner.py`, `engine/render.py`, `engine/stitch.py`, `engine/timing.py`; modify `engine/hashing.py` (add `stale_status`) and `cli.py` (add `render`, `stitch`); `tests/test_render_spec.py`, `tests/test_stitch.py`, `tests/test_render_manim.py`.
**Details:**
- `runner.py`: per A8. `python -m bms.runtime.runner spec.json`. It validates the scene first (errors → print them as `BMS_ERROR` with kind `other` and exit 2), runs the render, moves outputs, writes `timing.json` and `manifest.json` (scene mode only), always prints a final line `BMS_DONE|ok=<0|1>`.
- `render.py`: `build_render_spec` (quality via `quality_params`), `run_render` writes the spec to `renders/<scene>/<quality>/render_spec.json`, starts the runner with `popen_hidden([sys.executable, "-m", "bms.runtime.runner", spec_path])`, streams every line to `on_line` and to `logs/render_<scene>_<YYYYmmdd_HHMMSS>.log`, parses protocol lines into `errors` / `warnings`, and returns `RenderResult`. One render at a time is enforced by the caller (GUI), not here. `mode="beat"` with project `beat_render_mode == "cut"`: instead render the full scene at the same quality (reuse an existing up-to-date scene render if `stale_status` says it is fresh), then cut `[start, end]` from `timing.json` with `ffmpeg -ss <start> -to <end> -i scene.mp4 -c:v libx264 -c:a aac out` into `beat_<id>.mp4`.
- `stitch.py`: videos for all scenes in `scene_order` at the given quality, written to a temp list file with `file '<abs path>'` lines (single quotes escaped as `'\''`), then `ffmpeg -y -f concat -safe 0 -i list.txt -c copy <out>`; default output `renders/_project/<quality>/project.mp4`. Missing or stale scene renders → raise `RuntimeError` listing the scene ids.
- `stale_status`: scene is stale if `manifest.json` or `scene.mp4` is missing, `settings_hash` differs, or the beat id list differs; a beat is stale if its stored hash differs from `beat_hash` now.
- `cli.py`: `bms render` exit codes per A11; prints each `BMS_ERROR` as a translated line if `bms.diagnostics.errors` is importable (try/except ImportError), otherwise the raw JSON.
**Tests (pure):** `build_render_spec` values for all three tiers and both `final_fps`; `stale_status` with a hand-written manifest; stitch list-file generation (monkeypatch `run_hidden`) including a path with a single quote. `@pytest.mark.manim`: render the sample scene at draft in all three modes (beat `result`, frame `method`, full scene) and assert the files and `timing.json` exist and `timing.json` has 4 beats.
**Done when (user's machine):** `bms render samples/demo_project --scene DemoParabola --quality draft` produces `scene.mp4` with narration; `--frame method` produces a PNG in seconds; `--beat result` produces a short MP4; second identical render is much faster (narration cache).

## M5: Change tracking and reports

**Attach:** `src/bms/jsonio.py`, `src/bms/project.py`, `src/bms/schema/registry.py`, `src/bms/cli.py`.
**Create:** `tracking/__init__.py`, `tracking/baseline.py`, `tracking/diff.py`, `tracking/report.py`; modify `cli.py` (add `diff`, `report`); `tests/test_tracking.py`.
**Details:** per A9/A13.
- Baseline: `.bms/baseline/<scene>.json` is the "last reported" snapshot, `.bms/original/<scene>.json` is the immutable first import (written once, never overwritten, even with `import --overwrite`; with overwrite the BASELINE is reset to the new import and a new original is written only if none exists). `Project.import_scene` already calls `init_baseline` (M0).
- `compute_changes`: for each scene with a baseline: narration per beat id present in both; every `iter_text_fields` path per object id present in both with the same type. Only changed (NFC-different) values are returned. Custom objects and non-text fields are never tracked.
- `reasons.json` maps change keys to reasons; `save_reason` writes it atomically. A reason whose key no longer has a change is dropped on the next report.
- `export_report(project, mark=True)`: builds the report, writes `reports/report_<YYYYmmdd_HHMMSS>.md` and `reports/latest.md`, returns the timestamped path; if there are no changes it writes nothing, returns the path of `latest.md` if it exists else raises `ValueError("no changes")`. When `mark` is true and the files were written, call `mark_reported` for the scenes that had changes (baseline := current scene, reasons for them cleared). Marking happens only after both files were written successfully.
**Tests:** edit narration → 1 change with the right key; edit `options[2]` and `qmath` → 2 on-screen changes; unchanged scene → 0; NFC vs NFD forms of the same text → not a change; the same `সরালে`→`সরল করলে` replacement in 4 beats → one pattern with count 4; report text for a fixed fixture equals an expected string (fixture in the test, timestamp injected via a `now` parameter on `build_report(..., now=None)`); export with `mark=True` makes the next `compute_changes` empty and keeps `.bms/original` untouched; a failed write (monkeypatch to raise) leaves the baseline unmarked.
**Done when:** `pytest -q` passes; editing one narration line in the sample project and running `bms diff` prints a correct block; `bms report` then `bms diff` prints "No changes."

## M6: Diagnostics (doctor, error translation, logs, debug report)

**Attach:** `src/bms/project.py`, `src/bms/procutil.py`, `src/bms/schema/validate.py`, `src/bms/runtime/protocol.py`, `src/bms/engine/render.py`, `src/bms/tracking/diff.py`, `src/bms/cli.py`.
**Create:** `diagnostics/__init__.py`, `doctor.py`, `errors.py`, `logs.py`, `debug_report.py`; modify `cli.py` (add `doctor`, `debug-report`; make `render` use `translate_error`); `tests/test_errors.py`, `tests/test_doctor.py`, `tests/test_debug_report.py`.
**Details:**
- `run_doctor` returns one dict per check, in this order, each never raising: Python version (3.11 or 3.12); `manim` importable and version; `edge_tts` importable; `pydub` importable; `PySide6` importable; `ffmpeg` and `ffprobe` (`-version`); `latex` and `dvisvgm` (`--version`); LaTeX packages via `kpsewhich` for `amsmath.sty`, `mhchem.sty`, `physics.sty`, `siunitx.sty`, `cancel.sty` (one check each; skip with ok=false detail "latex not found" if kpsewhich is missing); Bangla font "Noto Sans Bengali" present (use `PySide6.QtGui.QFontDatabase` only if a `QGuiApplication` exists, else check `manimpango.list_fonts()` in try/except; otherwise ok=false with fix text); network: `socket.create_connection(("speech.platform.bing.com", 443), timeout=5)`; project checks when `project_root` is given: `project.json` loads, every scene validates with 0 errors. Each dict has a plain-language `fix` string.
- `translate_error(text)`: first look for a `BMS_ERROR|` line and use its fields; else match the first applicable rule in this order: LaTeX (`(?i)latex|dvisvgm|\.tex` together with `(?i)error|failed|converting`), ffmpeg missing (`(?i)ffmpeg` with `not found|not recognized|No such file|FileNotFoundError`), narration/network (`(?i)edge_tts|NoAudioReceived|ClientConnector|Cannot connect|getaddrinfo`), missing module (`ModuleNotFoundError: No module named '(\w+)'`), font (`(?i)font.*(not found|missing)`), disk/memory (`(?i)MemoryError|No space left`), else code `other` with the last 15 lines as `raw_tail`. Every result has `code`, `title`, `hint`, `raw_tail` (last 15 lines). Hints name the beat/object when known and, for LaTeX, mention doubled backslashes in JSON and `bms doctor`.
- `setup_logging(log_dir)`: `RotatingFileHandler` (2 MB, 5 backups) at `app.log` plus console at WARNING; also deletes `render_*.log` files older than 30 days.
- `build_debug_report` returns Markdown, exactly this shape:
```
# Debug report
bms <version> | manim <version> | python <version> | <OS>
Scene: <scene_id> | Beat: <beat_id or all> | Quality: <last used or n/a>
## Problem
<title>: <hint>
## Validation issues
<format_issue lines, or "none">
## Script snippet
<the beat JSON, plus the JSON of every object it references>
## Last log (tail 40 lines)
<text>
## Unreported changes
<number> pending (run `bms diff` for details)
```
**Tests:** one `translate_error` case per rule; doctor returns the full check list with monkeypatched `run_hidden` (all ok, and one failing); debug report contains every heading; `setup_logging` rotation config.
**Done when:** `pytest -q` passes; `bms doctor` on the user's machine prints a green/red list; a deliberately broken `tex` (`"\\frac{1"`) in the sample prints a LaTeX hint naming the object.

## M7: GUI part 1 (editing and change tracking)

**Attach:** `src/bms/project.py`, `src/bms/jsonio.py`, `src/bms/schema/registry.py`, `src/bms/schema/validate.py`, `src/bms/tracking/*.py`, `src/bms/diagnostics/logs.py`, `src/bms/cli.py`.
**Create:** `gui/__init__.py`, `gui/app.py`, `gui/theme.py`, `gui/main_window.py`, `gui/scene_panel.py`, `gui/beat_panel.py`, `gui/object_panel.py`, `gui/changes_panel.py`, `gui/workers.py`; modify `cli.py` (`bms gui [project_dir]` calls `bms.gui.app.run(project_dir)`); `tests/test_gui_smoke.py` (env `QT_QPA_PLATFORM=offscreen`, skipped if PySide6 missing).
**Details (PySide6 widgets, exact behavior):**
- `app.run`: creates `QApplication`, calls `setup_logging`, registers fonts from `assets/fonts/*.ttf|otf` with `QFontDatabase.addApplicationFont` (ignore if folder empty) and, in try/except, `manimpango.register_font`. Sets the app default font family to "Noto Sans Bengali" if available. Remembers the last project path in `~/.bms/settings.json`. Opens the last project or shows an Open/New dialog.
- Main window: left dock **Scenes** (list in `scene_order`; buttons New Project, Open Project, Import Scene); center a `QTabWidget` with tabs **Edit**, **Changes**; right dock **Preview** (placeholder label, filled in M8); bottom dock **Log** (placeholder, M8).
- **Edit tab**: a vertical splitter. Top: beat table (columns: `#`, beat id, narration preview, status). Bottom: for the selected beat, a multi-line `QPlainTextEdit` for narration (labelled; disabled with the text "silent beat" when narration is null; editing to empty string is allowed and stores `""`), then the **On-screen text** panel listing every object whose FIRST reference is in this beat (steps `targets` order, plus group children), each as a card: header `<object_id> · <type>`, one `QPlainTextEdit`/`QLineEdit` per `iter_text_fields` entry. Custom entries and objects without text fields show as read-only cards with a "Custom" or "No text" badge (Custom cards show their `code` read-only). A collapsed "All steps (read-only)" section prints each step as one line of text.
- Edited fields get a yellow left border; a changed-vs-baseline marker (via `compute_changes`) refreshes after each save.
- **Autosave**: 800 ms debounce after the last keystroke, writes through `Project.save_scene` (atomic) by changing the loaded dict in place (`set_text_field` or `beat["narration"] = ...`). Before the first edit of a session and on window close, write a snapshot to `.bms/history/<scene_id>/<YYYYmmdd_HHMMSS>.json`, keeping the newest 20.
- **Changes tab**: table of `compute_changes` (columns: Scene, Where, Type "Narration"/"On-screen", Before, After, Reason). Reason cell is editable and saved with `save_reason`. Buttons: **Refresh**, **Export report** (calls `export_report(project, mark=True)`, copies the text to the clipboard, shows a status message `Report saved to <path> and copied. Baseline updated.`), **Re-copy last report** (copies `reports/latest.md`; disabled if absent), **View vs original** (toggle that compares against `.bms/original` instead of baseline, read-only, export disabled while on). A labelled count of pending changes appears in the tab title: `Changes (3)`.
- Workers: `workers.py` provides a generic `Worker(QRunnable)` + signals for background tasks (used in M8).
- Validation: on scene load and after every save, run `validate_scene`; show errors as a red banner at the top of the Edit tab with a "Show" button listing `format_issue` lines. Editing stays enabled.
**Tests (offscreen smoke):** open the sample project, select the first scene and beat, change the narration text, wait 1 s of event loop, assert the file on disk changed and `compute_changes` returns 1 change; change an option text, assert the change key is `DemoParabola|object|q1|options[2]`.
**Done when:** on the user's machine `bms gui samples/demo_project` shows Bangla text correctly, edits autosave, Changes tab lists them, Export report writes the file, copies it, and the count drops to 0.

## M8: GUI part 2 (render, player, doctor, log)

**Attach:** `src/bms/gui/*.py`, `src/bms/engine/render.py`, `src/bms/engine/stitch.py`, `src/bms/engine/hashing.py`, `src/bms/engine/audio.py`, `src/bms/diagnostics/*.py`, `src/bms/runtime/protocol.py`, `src/bms/project.py`.
**Create:** `gui/render_panel.py`, `gui/player.py`, `gui/doctor_panel.py`, `gui/log_panel.py`; modify `gui/main_window.py`, `gui/beat_panel.py`, `gui/workers.py`; `tests/test_gui_render_smoke.py`.
**Details:**
- **Toolbar / buttons** (Edit tab, above the beat table): Re-speak line, Frame preview, Render beat, Render scene, Render all, Stitch all, Cancel; a quality combo (Draft, Medium, Final; default Draft).
- **One render at a time**: a single `RenderController` owns a `Popen` from `popen_hidden`; buttons other than Cancel are disabled while it runs; Cancel calls `kill_tree`. A progress bar uses `BMS_PROGRESS` lines. Every output line goes to the Log dock.
- **Re-speak line**: a `Worker` calls `make_audio(current narration text)` and plays the wav with `QMediaPlayer` + `QAudioOutput`; status text shows "generating…" then "playing"; failure shows a translated error.
- **Frame preview**: runs `mode="frame"` for the selected beat at the chosen quality, shows the PNG scaled in the Preview dock (`QLabel` + `QPixmap`).
- **Render beat / scene / all**: modes `beat` / `scene` / scene loop. Render all uses `continue_on_error=True` and ends with a summary dialog listing failed beats (translated errors). Stitch all calls `stitch` in a `Worker`.
- **Player** (`player.py`): `QMediaPlayer` + `QVideoWidget` with play/pause, seek slider, loop toggle, step ±1 frame (`setPosition(pos ± round(1000/fps))` while paused), speed 0.5x/1x/2x, and an **Open in system player** button using `QDesktopServices.openUrl` (also shown automatically if the media player reports an error). Clicking a beat row seeks to its `start` from the scene's `timing.json` if a scene video is loaded.
- **Stale badges**: the beat table status column shows `Edited` (from changes), `Stale` (from `stale_status` for the selected quality), `Rendered`; refresh after every save and render.
- **Doctor tab/panel**: runs `run_doctor` in a `Worker`; shows green/red rows with `fix` text; auto-runs once on first launch (flag in `~/.bms/settings.json`). **Copy debug report** button on the Log dock calls `build_debug_report` for the current scene/beat and copies it.
- **Log dock**: read-only text, newest at bottom, level filter (All/Warnings/Errors), a **Open log folder** button, and translated errors shown as bold lines with the hint.
**Tests (offscreen smoke):** build the window with the sample project, assert buttons exist and are enabled; monkeypatch `run_render` to a fake, click Render scene, assert buttons disable then re-enable and the Log dock received lines; assert Cancel calls `kill_tree` on a fake process.
**Done when (user's machine):** all buttons work on the sample project; a beat re-render after editing one line is quick; stale badges update; Doctor and Copy debug report work.

## M9: Packaging and GitHub Actions (best effort; mark as UNVERIFIED until tested on both OSes)

**Attach:** `environment.yml`, `pyproject.toml`, `README.md`, `.gitignore`, `src/bms/diagnostics/doctor.py`, `src/bms/gui/app.py`.
**Create:** `packaging/build_portable.py`, `packaging/launchers/bms.sh`, `packaging/launchers/bms.bat`, `packaging/tex-packages.txt`, `packaging/THIRD_PARTY_NOTICES.md`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`; modify `README.md` (add Install, Dev, Release sections and an UNVERIFIED notice for packaging).
**Details:**
- Portable folder layout (zipped per OS): `bms-<version>-<os>/{env/, tools/tinytex/, app/ (not needed: package is installed into env), launchers, THIRD_PARTY_NOTICES.md, README.txt}`.
- `build_portable.py` (pure Python, run in CI; takes `--os windows|linux --version X --out DIR`): (1) create the conda env from `environment.yml` using `micromamba` (already on PATH in CI) into `build/env`, but with `pip install .` instead of `-e .`; (2) `conda-pack -p build/env -o build/env.tar.gz`, extract into the portable `env/`; (3) install TinyTeX with the official script (Linux: `https://yihui.org/tinytex/install-bin-unix.sh`; Windows: `https://yihui.org/tinytex/install-bin-windows.bat`), then `tlmgr install` every package listed in `packaging/tex-packages.txt`, and copy the resulting TinyTeX folder to `tools/tinytex/`; (4) copy fonts from `src/bms/assets/fonts` if present; (5) zip (Windows) or tar.gz (Linux).
- `tex-packages.txt` (one per line): `amsmath mhchem physics siunitx cancel standalone preview doublestroke relsize fundus-calligra wasysym rsfs wasy babel-english gnu-freefont mathastext cm-super dvisvgm xcolor setspace ms`. Add a header comment: if a render logs a missing `.sty` file, append its package here and rebuild.
- Launchers: set `PATH` to include `env`, `env/bin` (Linux) or `env`, `env\Scripts`, `env\Library\bin` (Windows) and `tools/tinytex/bin/<platform dir>`; on the first run execute `conda-unpack` (`env/bin/conda-unpack` or `env\Scripts\conda-unpack.exe`) once and create a `.unpacked` marker; then `exec python -m bms.cli gui "$@"`. The `.bat` uses `%~dp0` and `"%HERE%env\python.exe"`.
- `ci.yml`: on push and pull request, matrix `ubuntu-22.04` and `windows-2022`, Python 3.11, `pip install -e .[...]` is NOT used; instead `pip install pytest pydub edge-tts PySide6 psutil` and `pip install -e . --no-deps`, run `pytest -q -m "not manim"` with `QT_QPA_PLATFORM=offscreen`.
- `release.yml`: on tags `v*`, same matrix; uses `mamba-org/setup-micromamba` to get micromamba, `pip install conda-pack` into the base env, runs `build_portable.py`, uploads the archive as a release asset with `softprops/action-gh-release`. Pin each action to a major version tag (`@v4`, `@v2`, etc.).
- `THIRD_PARTY_NOTICES.md`: a table listing Manim (MIT), edge-tts, pydub (MIT), PySide6/Qt (LGPLv3), FFmpeg (note: LGPL or GPL depending on the build; the release must say which build was bundled), TinyTeX/TeX Live (various), Noto Sans Bengali (OFL), with "check licence before redistributing" as an explicit note for FFmpeg and any other bundled binary.
**Tests:** none beyond CI; `build_portable.py` must have a `--dry-run` that prints each planned step without running anything (this is what the human can test first).
**Done when:** `python packaging/build_portable.py --os linux --version 0.1.0 --out dist --dry-run` prints the full plan; CI runs green; the human tests the produced archives on Windows and Linux and reports back using Part C.

---

# PART C: REPORT-BACK TEMPLATE (paste into the same AI Studio chat when something fails)

```
MILESTONE: M<n>
OS: <Windows 11 | Ubuntu 24.04 | ...>
STEP THAT FAILED: <the command from "YOU RUN">
OUTPUT / TRACEBACK (full, unedited):
<paste>
`bms doctor` OUTPUT (if M6 is done):
<paste>
DEBUG REPORT (if M6 is done and a render failed):
<paste from `bms debug-report` or the GUI button>
WHAT I EXPECTED: <one line>
FILES I CHANGED BY HAND (if any): <list>
```
Instruction to the AI for this situation (append below the template): "Fix only the failing behavior. Output the complete corrected versions of only the files that need to change, with the same `### FILE:` format. Do not change any frozen name or interface from the system instructions. If the cause is in a frozen interface or in the spec itself, say so under `## SPEC NOTES` and propose the smallest change."
