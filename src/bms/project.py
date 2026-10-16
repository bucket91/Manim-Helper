from __future__ import annotations

import copy
import re
from pathlib import Path

from bms import jsonio

_SCENE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

DEFAULT_SETTINGS: dict = {
    "format_version": 1,
    "name": "",
    "scene_order": [],
    "voice": "bn-BD-PradeepNeural",
    "rate": "+4%",
    "font_bn": "Noto Sans Bengali",
    "pad": 0.25,
    "narrate": True,
    "default_run_time": 1.0,
    "final_fps": 30,
    "bangla_numerals_on_screen": False,
    "beat_render_mode": "skip",
}

DEFAULT_PRONUNCIATION: dict = {
    "format_version": 1,
    "rules": [
        {"pattern": "স্থানাঙ্ক(?!ের)", "replacement": "স্থানাঙ্কো"},
        {"pattern": "উপকেন্দ্র", "replacement": "উপোকেন্দ্র", "note": "upokendro"},
        {"pattern": "নিয়ামক", "replacement": "নিয়ামোক", "note": "niyamok"},
        {"pattern": "অপশন", "replacement": "অপ্শন", "note": "opshon"},
        {"pattern": "লম্ব(?![া-ৌ্])", "replacement": "লম্বো", "note": "lombo"},
        {"pattern": "বর্গ(?![া-ৌ্])", "replacement": "বর্গো", "note": "borgo"},
        {"pattern": "দশ(?![া-ৌ্])", "replacement": "দোশ", "note": "dosh"},
        {
            "pattern": "স(?!্)",
            "replacement": "শ",
            "note": "স is spoken sh unless part of a conjunct",
        },
    ],
    "keep_s": ["এক্স", "মাইনাস", "প্লাস", "সাইন", "কস"],
}

QUALITIES: dict[str, tuple[int, int, int | None]] = {
    "draft": (854, 480, 15),
    "medium": (1280, 720, 30),
    "final": (1920, 1080, None),
}

_PROJECT_SUBDIRS: tuple[str, ...] = (
    "scenes",
    "narration_cache",
    "renders",
    "logs",
    "reports",
    ".bms",
    ".bms/baseline",
    ".bms/original",
    ".bms/history",
)


def quality_params(settings: dict, quality: str) -> tuple[int, int, int]:
    if quality not in QUALITIES:
        raise ValueError(f"unknown quality: {quality!r}")
    width, height, fps = QUALITIES[quality]
    if fps is None:
        fps = int(settings.get("final_fps", DEFAULT_SETTINGS["final_fps"]))
    return width, height, fps


class Project:
    def __init__(self, root: Path, settings: dict, pronunciation: dict) -> None:
        self.root = Path(root)
        self.settings = settings
        self.pronunciation = pronunciation

    @classmethod
    def create(cls, root: Path, name: str) -> "Project":
        root = Path(root)
        if (root / "project.json").exists():
            raise FileExistsError(f"project already exists: {root / 'project.json'}")
        root.mkdir(parents=True, exist_ok=True)
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        settings["name"] = name
        pronunciation = copy.deepcopy(DEFAULT_PRONUNCIATION)
        project = cls(root, settings, pronunciation)
        for sub in _PROJECT_SUBDIRS:
            (root / sub).mkdir(parents=True, exist_ok=True)
        jsonio.save_json_atomic(root / "project.json", settings)
        jsonio.save_json_atomic(root / "pronunciation.json", pronunciation)
        jsonio.save_json_atomic(root / ".bms" / "reasons.json", {})
        return project

    @classmethod
    def open(cls, root: Path) -> "Project":
        root = Path(root)
        settings = jsonio.load_json(root / "project.json")
        for key, value in DEFAULT_SETTINGS.items():
            settings.setdefault(key, copy.deepcopy(value))
        if settings.get("format_version") != 1:
            raise ValueError("format_version must be 1")
        pron_path = root / "pronunciation.json"
        if pron_path.exists():
            pronunciation = jsonio.load_json(pron_path)
            if pronunciation.get("format_version") != 1:
                raise ValueError("format_version must be 1")
        else:
            pronunciation = copy.deepcopy(DEFAULT_PRONUNCIATION)
        return cls(root, settings, pronunciation)

    def scene_ids(self) -> list[str]:
        ids = list(self.settings.get("scene_order") or [])
        seen = set(ids)
        extra: list[str] = []
        scenes_dir = self.root / "scenes"
        if scenes_dir.is_dir():
            suffix = ".scene.json"
            for path in sorted(scenes_dir.glob(f"*{suffix}")):
                scene_id = path.name[: -len(suffix)]
                if scene_id not in seen:
                    seen.add(scene_id)
                    extra.append(scene_id)
        return ids + extra

    def scene_path(self, scene_id: str) -> Path:
        return self.root / "scenes" / f"{scene_id}.scene.json"

    def load_scene(self, scene_id: str) -> dict:
        return jsonio.load_json(self.scene_path(scene_id))

    def save_scene(self, scene_id: str, scene: dict) -> None:
        jsonio.save_json_atomic(self.scene_path(scene_id), scene)

    def import_scene(self, src: Path, overwrite: bool = False) -> str:
        src = Path(src)
        data = jsonio.load_json(src)
        scene_id = data.get("scene_id")
        if not isinstance(scene_id, str) or not _SCENE_ID_RE.fullmatch(scene_id):
            raise ValueError("invalid scene_id")
        dest = self.scene_path(scene_id)
        if dest.exists() and not overwrite:
            raise FileExistsError(f"scene already exists: {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        jsonio.save_json_atomic(dest, data)
        order = self.settings.setdefault("scene_order", [])
        if scene_id not in order:
            order.append(scene_id)
            self.save_settings()
        try:
            from bms.tracking.baseline import init_baseline
        except ImportError:
            pass
        else:
            init_baseline(self, scene_id)
        return scene_id

    def subdir(self, name: str) -> Path:
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_settings(self) -> None:
        jsonio.save_json_atomic(self.root / "project.json", self.settings)
