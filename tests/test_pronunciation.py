from __future__ import annotations

from pathlib import Path

from bms import jsonio
from bms.engine.pronunciation import fix_pronunciation

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRON = REPO_ROOT / "samples" / "demo_project" / "pronunciation.json"


def _pron() -> dict:
    return jsonio.load_json(DEFAULT_PRON)


def test_default_pairs():
    pron = _pron()
    assert fix_pronunciation("দশ", pron) == "দোশ"
    assert fix_pronunciation("লম্ব", pron) == "লম্বো"
    assert fix_pronunciation("লম্বের", pron) == "লম্বের"
    assert fix_pronunciation("উপকেন্দ্রিক লম্ব", pron) == "উপোকেন্দ্রিক লম্বো"
    assert fix_pronunciation("এ সমান চার", pron) == "এ শমান চার"
    assert fix_pronunciation("মাইনাস দুই", pron) == "মাইনাস দুই"
    assert fix_pronunciation("স্থানাঙ্ক", pron) == "স্থানাঙ্কো"
    assert fix_pronunciation("স্থানাঙ্কের", pron) == "স্থানাঙ্কের"


def test_digits_untouched():
    pron = _pron()
    assert fix_pronunciation("0 1 2", pron) == "0 1 2"


def test_keep_s_survives_pattern_that_would_match():
    # "সাইন" is kept, so the স→শ rule must not touch it.
    pron = _pron()
    assert fix_pronunciation("সাইন", pron) == "সাইন"


def test_empty_pron_returns_input():
    text = "মাইনাস দুই দশ"
    assert fix_pronunciation(text, {}) == text


def test_keep_s_index_not_digits():
    # When there are ten or more keep words the sentinel uses the raw index;
    # ensure single-digit and multi-digit sentinels do not collide.
    pron = {
        "rules": [{"pattern": "X", "replacement": "Y"}],
        "keep_s": [f"k{n}" for n in range(12)],
    }
    text = " ".join(f"k{n}" for n in range(12))
    assert fix_pronunciation(text, pron) == text
