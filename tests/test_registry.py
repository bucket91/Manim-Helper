from __future__ import annotations

import pytest

from bms.schema.registry import (
    ANIMATIONS,
    FIELD_TYPES,
    ID_RE,
    OBJECT_TYPES,
    REQUIRED,
    AnimSpec,
    ObjectSpec,
    iter_text_fields,
    object_refs,
    set_text_field,
)


def test_id_re_accepts_and_rejects():
    assert ID_RE.fullmatch("eq1")
    assert ID_RE.fullmatch("_x9")
    assert not ID_RE.fullmatch("9eq")
    assert not ID_RE.fullmatch("a-b")
    assert not ID_RE.fullmatch("")
    assert not ID_RE.fullmatch("a b")


def test_registry_tables_are_consistent():
    assert set(FIELD_TYPES) == set(OBJECT_TYPES)
    for name, spec in OBJECT_TYPES.items():
        assert isinstance(spec, ObjectSpec)
        assert spec.name == name
        assert spec.placement in ("center", "origin", "none")
        assert set(spec.required) <= set(FIELD_TYPES[name]) | set(spec.required)
    expected = {
        "Write",
        "Create",
        "FadeIn",
        "FadeOut",
        "Uncreate",
        "Indicate",
        "Circumscribe",
        "ReplacementTransform",
        "move",
        "color_change",
        "scale",
        "pick_option",
        "wait",
        "clear_all",
    }
    assert set(ANIMATIONS) == expected
    for name, spec in ANIMATIONS.items():
        assert isinstance(spec, AnimSpec)
        assert spec.name == name


def test_defaults_match_spec_table():
    assert OBJECT_TYPES["text_bn"].defaults == {"size": 28}
    assert OBJECT_TYPES["mathtex"].defaults == {"size": 40}
    assert OBJECT_TYPES["bn_math_line"].defaults == {"bn_size": 28, "size": 40}
    assert OBJECT_TYPES["line"].defaults == {"stroke": 4}
    assert OBJECT_TYPES["circle"].defaults == {"radius": 1, "fill_opacity": 0}
    assert OBJECT_TYPES["rect"].defaults == {"width": 2, "height": 1, "fill_opacity": 0}
    assert OBJECT_TYPES["polygon"].defaults == {"fill_opacity": 0}
    assert OBJECT_TYPES["dot"].defaults == {"point": [0, 0], "radius": 0.08}
    assert OBJECT_TYPES["highlight_box"].defaults == {"buff": 0.12}
    assert OBJECT_TYPES["brace"].defaults == {"direction": "DOWN"}
    assert OBJECT_TYPES["axes"].defaults == {
        "x_range": [-5, 5, 1],
        "y_range": [-5, 5, 1],
        "x_length": 6,
        "y_length": 4,
        "tips": True,
    }
    assert OBJECT_TYPES["function_graph"].defaults == {"x_range": [-5, 5]}
    assert OBJECT_TYPES["number_line"].defaults == {"x_range": [-5, 5, 1], "length": 8}
    assert OBJECT_TYPES["group"].defaults == {"arrange": "DOWN", "buff": 0.3}
    assert OBJECT_TYPES["question_panel"].defaults == {}


def test_required_fields_match_spec_table():
    assert OBJECT_TYPES["text_bn"].required == ("text",)
    assert OBJECT_TYPES["mathtex"].required == ("tex",)
    assert OBJECT_TYPES["bn_math_line"].required == ("bn", "tex")
    assert OBJECT_TYPES["line"].required == ("start", "end")
    assert OBJECT_TYPES["polygon"].required == ("points",)
    assert OBJECT_TYPES["highlight_box"].required == ("target",)
    assert OBJECT_TYPES["brace"].required == ("target",)
    assert OBJECT_TYPES["function_graph"].required == ("axes", "expr")
    assert OBJECT_TYPES["group"].required == ("children",)
    assert OBJECT_TYPES["question_panel"].required == ("num", "qmath", "qtext", "options")
    assert OBJECT_TYPES["circle"].required == ()


def test_anim_params_and_flags():
    assert ANIMATIONS["Write"].params == {}
    assert ANIMATIONS["FadeIn"].params == {"shift": "none"}
    assert ANIMATIONS["Indicate"].params == {"scale_factor": 1.2}
    assert ANIMATIONS["move"].params == {"by": REQUIRED}
    assert ANIMATIONS["color_change"].params == {"color": REQUIRED}
    assert ANIMATIONS["scale"].params == {"factor": REQUIRED}
    assert ANIMATIONS["pick_option"].params == {"option": REQUIRED}
    rt = ANIMATIONS["ReplacementTransform"]
    assert (rt.min_targets, rt.max_targets) == (2, 2)
    assert rt.adds and rt.removes and rt.needs_alive
    wait = ANIMATIONS["wait"]
    assert (wait.min_targets, wait.max_targets) == (0, 0)
    assert not wait.needs_alive and not wait.adds and not wait.removes
    assert ANIMATIONS["Write"].adds and not ANIMATIONS["Write"].needs_alive
    assert ANIMATIONS["FadeOut"].removes and ANIMATIONS["FadeOut"].needs_alive


def test_iter_text_fields_question_panel_mixed():
    obj = {
        "type": "question_panel",
        "num": 1,
        "qmath": "1+1",
        "qtext": "pick one",
        "options": ["a", {"kind": "bn", "value": "বি"}, "c", {"kind": "en", "value": "d"}],
    }
    assert iter_text_fields(obj) == [
        ("qmath", "1+1"),
        ("qtext", "pick one"),
        ("options[0]", "a"),
        ("options[1].value", "বি"),
        ("options[2]", "c"),
        ("options[3].value", "d"),
    ]


def test_iter_text_fields_simple_and_unknown():
    assert iter_text_fields({"type": "mathtex", "tex": "y=x"}) == [("tex", "y=x")]
    assert iter_text_fields({"type": "text_bn", "text": "হ্যালো"}) == [("text", "হ্যালো")]
    assert iter_text_fields({"type": "sparkle_burst"}) == []
    assert iter_text_fields({"type": 5}) == []
    assert iter_text_fields("nope") == []
    assert iter_text_fields({"type": "mathtex"}) == []


def test_set_text_field_paths():
    obj = {"type": "question_panel", "qmath": "old", "options": ["a", {"kind": "bn", "value": "b"}]}
    set_text_field(obj, "qmath", "new")
    assert obj["qmath"] == "new"
    set_text_field(obj, "options[0]", "A")
    assert obj["options"][0] == "A"
    set_text_field(obj, "options[1].value", "B")
    assert obj["options"][1] == {"kind": "bn", "value": "B"}


def test_set_text_field_errors():
    obj = {"type": "question_panel", "qmath": "x", "options": ["a"]}
    with pytest.raises(ValueError):
        set_text_field(obj, "options[*]", "x")
    with pytest.raises(ValueError):
        set_text_field(obj, "qmath.value", "x")
    with pytest.raises(ValueError):
        set_text_field(obj, "bad path!", "x")
    with pytest.raises(IndexError):
        set_text_field(obj, "options[3]", "x")
    with pytest.raises(KeyError):
        set_text_field({"type": "mathtex", "tex": "a"}, "options[0]", "x")


def test_object_refs_order():
    obj = {"target": "t", "axes": "ax", "children": ["c1", "c2", 3]}
    assert object_refs(obj) == ["t", "ax", "c1", "c2"]
    assert object_refs({}) == []
    assert object_refs({"children": ["only"]}) == ["only"]
    assert object_refs("nope") == []
