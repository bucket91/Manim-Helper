from __future__ import annotations

import re

_SENTINEL_START = "\ue000"
_SENTINEL_END = "\ue001"


def _sentinel(index: int) -> str:
    return f"{_SENTINEL_START}{index}{_SENTINEL_END}"


def fix_pronunciation(text: str, pron: dict) -> str:
    if not isinstance(text, str):
        text = str(text)
    rules = pron.get("rules") if isinstance(pron, dict) else None
    keep_s = pron.get("keep_s") if isinstance(pron, dict) else None
    if not isinstance(rules, list):
        rules = []
    if not isinstance(keep_s, list):
        keep_s = []
    for index, word in enumerate(keep_s):
        if isinstance(word, str) and word:
            text = text.replace(word, _sentinel(index))
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        pattern = rule.get("pattern")
        replacement = rule.get("replacement")
        if not isinstance(pattern, str) or not isinstance(replacement, str):
            continue
        text = re.sub(pattern, replacement, text)
    for index, word in enumerate(keep_s):
        if isinstance(word, str) and word:
            text = text.replace(_sentinel(index), word)
    return text
