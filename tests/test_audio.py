from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from bms.engine import audio as audio_mod
from bms.project import DEFAULT_PRONUNCIATION, DEFAULT_SETTINGS


def test_module_imports_without_pydub():
    script = (
        "import sys\n"
        "sys.modules['pydub'] = None\n"
        "import bms.engine.audio\n"
        "print('ok')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


@pytest.mark.manim
def test_make_audio_caches_without_second_subprocess(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run_hidden(args, **kwargs):
        calls.append(list(args))
        if args[0] == "ffmpeg":
            Path(args[-1]).write_bytes(b"RIFF" + b"\x00" * 4000)
        else:
            media = next(
                arg for arg in args if str(arg).startswith("--write-media=")
            )
            Path(str(media).split("=", 1)[1]).write_bytes(b"\x00" * 4000)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(audio_mod, "run_hidden", fake_run_hidden)

    settings = dict(DEFAULT_SETTINGS)
    first = audio_mod.make_audio("সাইন আর কস", settings, DEFAULT_PRONUNCIATION, tmp_path)
    assert first.exists()
    assert first.stat().st_size > 0

    calls_after_first = len(calls)
    assert calls_after_first > 0

    second = audio_mod.make_audio("সাইন আর কস", settings, DEFAULT_PRONUNCIATION, tmp_path)
    assert second == first
    assert len(calls) == calls_after_first


@pytest.mark.manim
def test_make_audio_different_text_different_file(tmp_path, monkeypatch):
    def fake_run_hidden(args, **kwargs):
        if args[0] == "ffmpeg":
            Path(args[-1]).write_bytes(b"RIFF" + b"\x00" * 4000)
        else:
            media = next(
                arg for arg in args if str(arg).startswith("--write-media=")
            )
            Path(str(media).split("=", 1)[1]).write_bytes(b"\x00" * 4000)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(audio_mod, "run_hidden", fake_run_hidden)
    settings = dict(DEFAULT_SETTINGS)
    a = audio_mod.make_audio("এক", settings, DEFAULT_PRONUNCIATION, tmp_path)
    b = audio_mod.make_audio("দুই", settings, DEFAULT_PRONUNCIATION, tmp_path)
    assert a != b
