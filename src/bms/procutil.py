from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping


def _base_env(env_extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    return env


def _creationflags() -> int:
    if os.name == "nt":
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return 0


def run_hidden(
    args: list[str],
    *,
    check: bool = False,
    capture: bool = True,
    timeout: float | None = None,
    cwd: str | Path | None = None,
    env_extra: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess:
    kwargs: dict = {
        "check": check,
        "timeout": timeout,
        "cwd": str(cwd) if cwd is not None else None,
        "env": _base_env(env_extra),
        "creationflags": _creationflags(),
    }
    if capture:
        kwargs.update(
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    else:
        kwargs.update(stdout=None, stderr=None)
    return subprocess.run(args, **kwargs)


def popen_hidden(
    args: list[str],
    *,
    cwd: str | Path | None = None,
    env_extra: Mapping[str, str] | None = None,
) -> subprocess.Popen:
    return subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd is not None else None,
        env=_base_env(env_extra),
        creationflags=_creationflags(),
    )


def kill_tree(proc: subprocess.Popen) -> None:
    try:
        import psutil
    except ImportError:
        try:
            proc.kill()
        except Exception:
            pass
        return
    try:
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        try:
            parent.kill()
        except Exception:
            pass
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
