from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from bms import jsonio
from bms.engine.pronunciation import fix_pronunciation
from bms.procutil import run_hidden

_MIN_AUDIO_BYTES = 1000


def make_audio(text: str, settings: dict, pron: dict, audio_dir: Path) -> Path:
    audio_dir = Path(audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(
        f"{settings['voice']}|{settings['rate']}|v1|{jsonio.canonical_json(pron)}|{text}".encode(
            "utf-8"
        )
    ).hexdigest()[:12]
    mp3_path = Path(os.path.abspath(audio_dir / f"{key}.mp3"))
    wav_path = Path(os.path.abspath(audio_dir / f"{key}.wav"))
    if wav_path.exists() and wav_path.stat().st_size > _MIN_AUDIO_BYTES:
        return wav_path
    text_fixed = fix_pronunciation(text, pron)
    success = False
    for _attempt in range(3):
        try:
            run_hidden(
                [
                    sys.executable,
                    "-m",
                    "edge_tts",
                    f"--voice={settings['voice']}",
                    f"--text={text_fixed}",
                    f"--rate={settings['rate']}",
                    f"--write-media={mp3_path}",
                ],
                check=True,
            )
            if mp3_path.exists() and mp3_path.stat().st_size > _MIN_AUDIO_BYTES:
                success = True
                break
        except Exception:
            try:
                run_hidden(
                    [
                        "edge-tts",
                        f"--voice={settings['voice']}",
                        f"--text={text_fixed}",
                        f"--rate={settings['rate']}",
                        f"--write-media={mp3_path}",
                    ],
                    check=True,
                )
                if mp3_path.exists() and mp3_path.stat().st_size > _MIN_AUDIO_BYTES:
                    success = True
                    break
            except Exception:
                pass
    if not success:
        raise RuntimeError(f"edge-tts failed to generate valid audio for: {text[:20]}")
    run_hidden(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp3_path),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ],
        check=True,
    )
    if mp3_path.exists():
        mp3_path.unlink()
    return wav_path


def audio_duration(path: Path) -> float:
    from pydub import AudioSegment

    return len(AudioSegment.from_file(str(path))) / 1000.0
