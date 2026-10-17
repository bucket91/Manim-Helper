from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bms.cli import main as cli_main
from bms.project import Project
from bms.schema import (
    compile_expr,
    format_issue,
    validate_project,
    validate_scene,
)
from bms.schema.validate import Issue

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "samples" / "demo_project"


def scene(**kwargs) -> dict:
    data = {
        "format_version": 1,
        "scene_id": "S",
        "layout": "split60_40",
        "objects": {},
        "beats": [],
    }
    data.update(kwargs)
    return data


def codes(sc: dict, settings: dict | None = None) -> list[str]:
    return [i.code for i in validate_scene(sc, settings or {})]


def only(sc: dict, code: str) -> list[Issue]:
    return [i for i in validate_scene(sc, {}) if i.code == code]


# --- E101 / E102 -----------------------------------------------------------


def test_e101_missing_or_wrong_format_version():
    assert "E101" in codes({"scene_id": "S", "objects": {}, "beats": []})
    assert "E101" in codes({"format_version": 2, "scene_id": "S", "objects": {}, "beats": []})
    assert "E101" in codes({"format_version": True, "scene_id": "S", "objects": {}, "beats": []})


def test_e101_non_dict_scene():
    issues = validate_scene([1, 2, 3], {})  # type: ignore[arg-type]
    assert [i.code for i in issues] == ["E101"]


def test_e102_missing_or_invalid_scene_id():
    assert "E102" in codes({"format_version": 1, "objects": {}, "beats": []})
    assert "E102" in codes({"format_version": 1, "scene_id": "bad-id", "objects": {}, "beats": []})
    assert "E102" not in codes(scene())


# --- E103 / E104 -----------------------------------------------------------


def test_e103_duplicate_beat_id():
    sc = scene(beats=[{"id": "a", "steps": []}, {"id": "a", "steps": []}])
    assert "E103" in codes(sc)


def test_e104_bad_object_id():
    sc = scene(objects={"bad-id": {"type": "mathtex", "tex": "x"}, "a__pick": {"type": "dot"}})
    got = only(sc, "E104")
    assert {i.object_id for i in got} == {"bad-id", "a__pick"}


# --- E105 ------------------------------------------------------------------


def test_e105_unknown_targets_with_did_you_mean():
    sc = scene(
        objects={"eq2": {"type": "mathtex", "tex": "a"}, "eq3x": {"type": "mathtex", "tex": "b"}},
        beats=[{"id": "b", "steps": [{"anim": "Write", "targets": ["eq3"]}]}],
    )
    (issue,) = only(sc, "E105")
    assert issue.field == "targets"
    assert issue.step_index == 0
    assert "did you mean 'eq3x'" in issue.message


def test_e105_object_refs_and_children():
    sc = scene(
        objects={
            "hl": {"type": "highlight_box", "target": "missing"},
            "gr": {"type": "function_graph", "axes": "nope", "expr": "x"},
            "g": {"type": "group", "children": ["gone"]},
        }
    )
    fields = {(i.object_id, i.field) for i in only(sc, "E105")}
    assert fields == {("hl", "target"), ("gr", "axes"), ("g", "children")}


# --- E106 / E107 / E118 / W204 ---------------------------------------------


def test_e106_both_at_and_at_pct():
    sc = scene(
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[
            {
                "id": "b",
                "narration": "hello",
                "steps": [{"anim": "Write", "targets": ["t"], "at": 1.0, "at_pct": 50}],
            }
        ],
    )
    assert "E106" in codes(sc)


def test_e107_at_pct_requires_narration():
    sc = scene(
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[
            {
                "id": "b",
                "steps": [{"anim": "Write", "targets": ["t"], "at_pct": 50}],
            }
        ],
    )
    assert "E107" in codes(sc)
    sc["beats"][0]["narration"] = "spoken"
    assert "E107" not in codes(sc)
    sc["beats"][0]["narration"] = "   "
    assert "E107" in codes(sc)


def test_e118_and_w204_narration():
    sc = scene(beats=[{"id": "b", "narration": 42, "steps": []}])
    assert "E118" in codes(sc)
    sc = scene(beats=[{"id": "b", "narration": "", "steps": []}])
    assert "W204" in codes(sc)
    sc = scene(beats=[{"id": "b", "narration": None, "steps": []}])
    assert "W204" not in codes(sc)
    assert "E118" not in codes(sc)


# --- E108 ------------------------------------------------------------------


def test_e108_missing_containers_and_fields():
    assert "E108" in codes({"format_version": 1, "scene_id": "S"})
    assert "E108" in codes({"format_version": 1, "scene_id": "S", "objects": {}, "beats": {}})
    sc = scene(beats=[{"id": "b", "steps": {}}])
    assert "E108" in codes(sc)
    sc = scene(beats=[{"id": "b"}])
    assert "E108" not in codes(sc)
    sc = scene(objects={"t": {"type": "mathtex"}}, beats=[{"id": "b", "steps": [{"anim": "Write", "targets": ["t"]}]}])
    got = [(i.object_id, i.field) for i in only(sc, "E108")]
    assert ("t", "tex") in got


def test_e108_missing_required_step_fields():
    sc = scene(
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[
            {
                "id": "b",
                "steps": [
                    {"targets": ["t"]},
                    {"anim": "move", "targets": ["t"]},
                    {"anim": "color_change", "targets": ["t"]},
                    {"anim": "scale", "targets": ["t"]},
                    {"anim": "pick_option", "targets": ["t"]},
                ],
            }
        ],
    )
    fields = [i.field for i in only(sc, "E108")]
    assert fields == ["anim", "by", "color", "factor", "option"]


def test_e108_null_steps_treated_as_empty():
    sc = scene(beats=[{"id": "b", "steps": None}])
    assert "E108" not in codes(sc)


# --- E109 ------------------------------------------------------------------


def test_e109_unknown_region():
    sc = scene(objects={"t": {"type": "mathtex", "tex": "x", "region": "nowhere"}})
    assert "E109" in codes(sc)


def test_e109_split_regions_require_split_layout():
    sc = scene(
        layout="full",
        objects={
            "a": {"type": "mathtex", "tex": "x", "region": "solution"},
            "b": {"type": "mathtex", "tex": "y", "region": "top"},
        },
    )
    got = [i.object_id for i in only(sc, "E109")]
    assert got == ["a"]
    assert "E109" not in codes(scene(objects={"a": {"type": "mathtex", "tex": "x", "region": "solution"}}))


# --- E110 ------------------------------------------------------------------


def test_e110_option_range_and_target_type():
    sc = scene(
        objects={
            "qp": {
                "type": "question_panel",
                "num": 1,
                "qmath": "q",
                "qtext": "t",
                "options": ["a", "b", "c", "d"],
            },
            "m": {"type": "mathtex", "tex": "x"},
        },
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "Write", "targets": ["qp"]},
                    {"anim": "pick_option", "targets": ["qp"], "option": 9},
                    {"anim": "pick_option", "targets": ["m"], "option": 1, "with_previous": True},
                ],
            }
        ],
    )
    issues = only(sc, "E110")
    assert len(issues) == 2
    assert {i.field for i in issues} == {"option", "targets"}


# --- E111 ------------------------------------------------------------------


def test_e111_invalid_colors():
    sc = scene(objects={"t": {"type": "mathtex", "tex": "x", "color": "NOT_A_COLOR"}})
    assert "E111" in codes(sc)
    sc = scene(objects={"t": {"type": "mathtex", "tex": "x", "color": "#ff00aa"}})
    assert "E111" not in codes(sc)
    sc = scene(
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "Write", "targets": ["t"]},
                    {"anim": "color_change", "targets": ["t"], "color": "nope", "with_previous": True},
                ],
            }
        ],
    )
    assert "E111" in codes(sc)


# --- E112 / compile_expr ---------------------------------------------------


def test_e112_invalid_expr():
    sc = scene(objects={"gr": {"type": "function_graph", "axes": "ax", "expr": "sin(x"}})
    # missing axes object is E105; bad expr is E112
    assert "E112" in codes(sc)
    sc = scene(objects={"gr": {"type": "function_graph", "axes": "missing", "expr": "import os"}})
    assert "E112" in codes(sc)


def test_compile_expr_ok():
    f = compile_expr("x**2 + sin(pi)")
    assert abs(f(3.0) - (9.0 + 0.0)) < 1e-9
    g = compile_expr("sqrt(4) + ln(e) + log(100) + abs(-2) + exp(0)")
    assert abs(g(0.0) - (2.0 + 1.0 + 2.0 + 2.0 + 1.0)) < 1e-9
    h = compile_expr("-x + 2*x")
    assert abs(h(4.0) - 4.0) < 1e-9


def test_compile_expr_spec_examples():
    assert compile_expr("sqrt(8*x)")(2) == 4.0
    with pytest.raises(ValueError):
        compile_expr("__import__('os')")
    f = compile_expr("x**2 + sin(pi*x)")
    assert abs(f(1.0) - 1.0) < 1e-9


def test_compile_expr_pow_exponent_bound():
    assert compile_expr("x**64")(2.0) == pytest.approx(2.0**64)
    assert compile_expr("x**-64")(2.0) == pytest.approx(2.0**-64)
    with pytest.raises(ValueError):
        compile_expr("x**65")
    with pytest.raises(ValueError):
        compile_expr("x**-65")
    with pytest.raises(ValueError):
        compile_expr("2**100")
    # a non-constant exponent is not bounded here
    assert compile_expr("x**x")(1.0) == pytest.approx(1.0)


def test_compile_expr_node_count_bound():
    assert compile_expr(" + ".join(["x"] * 20))(1.0) == pytest.approx(20.0)
    with pytest.raises(ValueError):
        compile_expr(" + ".join(["x"] * 300))


@pytest.mark.parametrize(
    "expr",
    [
        "import os",
        "__import__('os')",
        "x; y",
        "lambda: 1",
        "x if True else 0",
        "open('f')",
        "x.real",
        "[1,2]",
        "{1}",
        "True",
        "'str'",
        "foo(x)",
        "sin(x=1)",
        "sin x",
    ],
)
def test_compile_expr_rejects(expr):
    with pytest.raises(ValueError):
        compile_expr(expr)


# --- E113 / E114 / E115 ----------------------------------------------------


def test_e113_target_counts():
    sc = scene(
        objects={"a": {"type": "mathtex", "tex": "x"}, "b": {"type": "mathtex", "tex": "y"}},
        beats=[
            {
                "id": "b1",
                "steps": [{"anim": "Write", "targets": []}],
            },
            {
                "id": "b2",
                "steps": [{"anim": "wait", "targets": ["a"]}],
            },
            {
                "id": "b3",
                "steps": [{"anim": "Write", "targets": ["a"]}, {"anim": "ReplacementTransform", "targets": ["a"], "with_previous": True}],
            },
        ],
    )
    msgs = [i.message for i in only(sc, "E113")]
    assert len(msgs) == 3
    assert any("at least 1" in m for m in msgs)
    assert any("exactly 0" in m for m in msgs)
    assert any("exactly 2" in m for m in msgs)


def test_e114_negative_and_out_of_range():
    sc = scene(beats=[{"id": "b", "hold": -1, "pad": -0.5, "steps": []}])
    assert [i.field for i in only(sc, "E114")] == ["hold", "pad"]
    sc = scene(
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "Write", "targets": ["t"], "run_time": 0},
                    {"anim": "Write", "targets": ["t"], "run_time": 40, "with_previous": True},
                    {"anim": "Write", "targets": ["t"], "at": -1, "with_previous": True},
                ],
            }
        ],
    )
    assert len(only(sc, "E114")) == 3


def test_e114_negative_project_pad():
    sc = scene()
    assert "E114" in codes(sc, {"pad": -1})
    assert "E114" not in codes(sc, {"pad": 0.25})


def test_e115_at_only_on_group_start():
    sc = scene(
        objects={
            "a": {"type": "mathtex", "tex": "x"},
            "b": {"type": "mathtex", "tex": "y"},
        },
        beats=[
            {
                "id": "b",
                "narration": "n",
                "steps": [
                    {"anim": "Write", "targets": ["a"]},
                    {"anim": "Write", "targets": ["b"], "at": 1.0, "with_previous": True},
                ],
            }
        ],
    )
    (issue,) = only(sc, "E115")
    assert issue.step_index == 1
    sc = scene(
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[{"id": "b", "steps": [{"anim": "wait", "with_previous": True}]}],
    )
    assert "E115" in codes(sc)


def test_at_on_new_group_is_ok():
    sc = scene(
        objects={
            "a": {"type": "mathtex", "tex": "x"},
            "b": {"type": "mathtex", "tex": "y"},
        },
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "Write", "targets": ["a"]},
                    {"anim": "Write", "targets": ["b"], "at": 2.0},
                ],
            }
        ],
    )
    assert "E115" not in codes(sc)


# --- E116 / E117 -----------------------------------------------------------


def test_e116_use_before_shown():
    sc = scene(
        objects={"a": {"type": "mathtex", "tex": "x"}},
        beats=[{"id": "b", "steps": [{"anim": "FadeOut", "targets": ["a"]}]}],
    )
    (issue,) = only(sc, "E116")
    assert issue.object_id == "a"


def test_e116_group_child_needs_group_alive():
    sc = scene(
        objects={
            "a": {"type": "mathtex", "tex": "x"},
            "g": {"type": "group", "children": ["a"]},
        },
        beats=[{"id": "b", "steps": [{"anim": "FadeOut", "targets": ["a"]}]}],
    )
    assert "E116" in codes(sc)
    sc = scene(
        objects={
            "a": {"type": "mathtex", "tex": "x"},
            "g": {"type": "group", "children": ["a"]},
        },
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "Write", "targets": ["g"]},
                    {"anim": "FadeOut", "targets": ["a"], "with_previous": True},
                ],
            }
        ],
    )
    assert "E116" not in codes(sc)


def test_e116_ref_before_shown_at_creation():
    sc = scene(
        objects={
            "ax": {"type": "axes"},
            "gr": {"type": "function_graph", "axes": "ax", "expr": "x"},
        },
        beats=[{"id": "b", "steps": [{"anim": "Create", "targets": ["gr"]}]}],
    )
    (issue,) = only(sc, "E116")
    assert issue.field == "axes"
    sc["beats"][0]["steps"].insert(0, {"anim": "Create", "targets": ["ax"]})
    assert "E116" not in codes(sc)


def test_e117_two_groups_structural():
    sc = scene(
        objects={
            "a": {"type": "mathtex", "tex": "x"},
            "g1": {"type": "group", "children": ["a"]},
            "g2": {"type": "group", "children": ["a"]},
        }
    )
    (issue,) = only(sc, "E117")
    assert issue.object_id == "g2"
    assert "more than one group" in issue.message


def test_e117_direct_target_while_group_alive():
    sc = scene(
        objects={
            "a": {"type": "mathtex", "tex": "x"},
            "g": {"type": "group", "children": ["a"]},
        },
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "Write", "targets": ["g"]},
                    {"anim": "Write", "targets": ["a"], "with_previous": True},
                ],
            }
        ],
    )
    (issue,) = only(sc, "E117")
    assert issue.object_id == "g"
    assert issue.field == "children"


def test_e117_fired_when_group_already_faded():
    sc = scene(
        objects={
            "a": {"type": "mathtex", "tex": "x"},
            "g": {"type": "group", "children": ["a"]},
        },
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "Write", "targets": ["g"]},
                    {"anim": "FadeOut", "targets": ["g"], "with_previous": True},
                    {"anim": "Write", "targets": ["a"], "with_previous": True},
                ],
            }
        ],
    )
    (issue,) = only(sc, "E117")
    assert issue.object_id == "g"
    assert issue.field == "children"
    assert "E116" not in codes(sc)


def test_e117_direct_child_target_regardless_of_order():
    # target child before the group is ever shown
    sc = scene(
        objects={
            "a": {"type": "mathtex", "tex": "x"},
            "g": {"type": "group", "children": ["a"]},
        },
        beats=[{"id": "b", "steps": [{"anim": "Write", "targets": ["a"]}]}],
    )
    (issue,) = only(sc, "E117")
    assert issue.object_id == "g"

    # target child in the same step that would show the group
    sc = scene(
        objects={
            "a": {"type": "mathtex", "tex": "x"},
            "g": {"type": "group", "children": ["a"]},
        },
        beats=[
            {
                "id": "b",
                "steps": [{"anim": "Write", "targets": ["g", "a"]}],
            }
        ],
    )
    (issue,) = only(sc, "E117")
    assert issue.object_id == "g"


def test_replacement_transform_aliveness():
    sc = scene(
        objects={"a": {"type": "mathtex", "tex": "x"}, "b": {"type": "mathtex", "tex": "y"}},
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "Write", "targets": ["a"]},
                    {"anim": "ReplacementTransform", "targets": ["a", "b"], "with_previous": True},
                    {"anim": "FadeOut", "targets": ["b"], "with_previous": True},
                ],
            }
        ],
    )
    assert "E116" not in codes(sc)
    assert "E113" not in codes(sc)


def test_clear_all_resets_alive():
    sc = scene(
        objects={"a": {"type": "mathtex", "tex": "x"}},
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "Write", "targets": ["a"]},
                    {"anim": "clear_all"},
                    {"anim": "FadeOut", "targets": ["a"], "with_previous": True},
                ],
            }
        ],
    )
    assert "E116" in codes(sc)


# --- E119 ------------------------------------------------------------------


def test_e119_wrong_types():
    sc = scene(objects={"t": {"type": "mathtex", "tex": "x", "size": "big", "color": 5}})
    fields = {i.field for i in only(sc, "E119")}
    assert {"size", "color"} <= fields

    sc = scene(
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[{"id": "b", "steps": [{"anim": "Write", "targets": "t"}]}],
    )
    assert "targets" in [i.field for i in only(sc, "E119")]

    sc = scene(beats=[{"id": "b", "steps": "nope"}])
    assert "E119" not in codes(sc) and "E108" in codes(sc)

    sc = scene(beats=["not-a-beat"])
    assert "E119" in codes(sc)

    sc = scene(objects={"t": "not-an-object"})
    assert "E119" in codes(sc)


def test_e119_optional_null_is_wrong_type():
    sc = scene(objects={"t": {"type": "mathtex", "tex": "x", "size": None}})
    assert "E119" in codes(sc)
    sc = scene(objects={"t": {"type": "mathtex", "tex": None}})
    assert "E108" in codes(sc)


def test_e119_shape_checks():
    sc = scene(objects={"poly": {"type": "polygon", "points": [[0, 0], [1, 1]]}})
    assert "E119" in codes(sc)
    sc = scene(objects={"ax": {"type": "axes", "x_range": [1]}})
    assert "E119" in codes(sc)
    sc = scene(
        objects={
            "qp": {
                "type": "question_panel",
                "num": 1,
                "qmath": "q",
                "qtext": "t",
                "options": ["a", "b", "c"],
            }
        }
    )
    assert "E119" in codes(sc)
    sc = scene(objects={"ax": {"type": "axes", "tips": 1}})
    assert "E119" in codes(sc)


# --- W201 / W202 -----------------------------------------------------------


def test_w201_w202_custom_objects():
    sc = scene(objects={"burst": {"type": "sparkle_burst"}})
    assert "W201" in codes(sc)
    assert "W202" not in codes(sc)
    sc = scene(objects={"tag": {"type": "custom_label", "code": "Text('x')"}})
    assert "W202" in codes(sc)
    assert "W201" not in codes(sc)


def test_w201_w202_custom_steps():
    sc = scene(
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[{"id": "b", "steps": [{"anim": "fancy_new", "targets": ["t"]}]}],
    )
    assert "W201" in codes(sc)
    sc["beats"][0]["steps"][0]["code"] = "pass"
    assert "W202" in codes(sc)


def test_custom_step_adds_removes():
    base = {
        "a": {"type": "mathtex", "tex": "x"},
    }
    sc = scene(
        objects=base,
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "show_it", "adds": ["a"]},
                    {"anim": "FadeOut", "targets": ["a"], "with_previous": True},
                ],
            }
        ],
    )
    assert "E116" not in codes(sc)
    sc = scene(
        objects=base,
        beats=[
            {
                "id": "b",
                "steps": [
                    {"anim": "show_it", "adds": ["a"]},
                    {"anim": "hide_it", "removes": ["a"], "with_previous": True},
                    {"anim": "FadeOut", "targets": ["a"], "with_previous": True},
                ],
            }
        ],
    )
    assert "E116" in codes(sc)


# --- W205 ------------------------------------------------------------------


def test_w205_unreferenced_object():
    sc = scene(
        objects={"lonely": {"type": "mathtex", "tex": "x"}},
        beats=[],
    )
    (issue,) = only(sc, "W205")
    assert issue.object_id == "lonely"


def test_w205_not_flagged_when_referenced():
    sc = scene(
        objects={
            "eq": {"type": "mathtex", "tex": "x"},
            "hl": {"type": "highlight_box", "target": "eq"},
            "ax": {"type": "axes"},
            "gr": {"type": "function_graph", "axes": "ax", "expr": "x"},
            "g": {"type": "group", "children": ["eq"]},
        },
        beats=[{"id": "b", "steps": [{"anim": "Create", "targets": ["hl", "gr", "g"]}]}],
    )
    assert "W205" not in codes(sc)


# --- compile_expr / format_issue / purity ----------------------------------


def test_format_issue_full_and_partial():
    issue = Issue(
        "E105",
        "error",
        "DemoParabola",
        "method",
        None,
        2,
        "targets",
        "unknown object id 'eq3' (did you mean 'eq2'?)",
    )
    assert format_issue(issue) == (
        "[E105] scene=DemoParabola beat=method step=2 field=targets: "
        "unknown object id 'eq3' (did you mean 'eq2'?)"
    )
    assert format_issue(Issue("E101", "error", "S", None, None, None, None, "boom")) == "[E101] scene=S: boom"
    assert (
        format_issue(Issue("W205", "warning", "S", None, "o", None, None, "m"))
        == "[W205] scene=S object=o: m"
    )


def test_validate_scene_does_not_mutate():
    sc = scene(
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[{"id": "b", "steps": [{"anim": "Write", "targets": ["t"]}]}],
    )
    snapshot = copy.deepcopy(sc)
    validate_scene(sc, {})
    assert sc == snapshot


def test_validate_scene_never_raises_on_garbage():
    garbage = [
        {},
        {"format_version": 1, "scene_id": "S", "objects": [], "beats": [None]},
        {"format_version": 1, "scene_id": "S", "objects": {"a": None}, "beats": [{"steps": [1]}]},
        {"format_version": 1, "scene_id": "S", "objects": {"a": {"type": "group", "children": "x"}}, "beats": [{"steps": [{"anim": 5}]}]},
        {"format_version": 1, "scene_id": "S", "objects": {"a": {"type": "polygon", "points": "x"}}, "beats": [{"steps": [{"anim": "pick_option", "targets": ["a"], "option": "x"}]}]},
        {"format_version": 1, "scene_id": "S", "objects": {"a": {"type": "dot", "point": [0]}}, "beats": [{"steps": [{"anim": "move", "targets": ["a"], "by": None}]}]},
    ]
    for sc in garbage:
        validate_scene(sc, {})


def test_unknown_type_scene_round_trips():
    sc = scene(
        objects={
            "burst": {
                "type": "sparkle_burst",
                "region": "solution",
                "dx": 2,
                "comment": "custom entry without code",
            }
        },
        beats=[{"id": "b", "steps": [{"anim": "Create", "targets": ["burst"]}]}],
    )
    got = codes(sc)
    assert got == ["W201"]


def test_fields_with_defaults_are_not_required():
    sc = scene(
        objects={
            "t": {"type": "text_bn", "text": "হ্যালো"},
            "ax": {"type": "axes"},
            "c": {"type": "circle"},
        },
        beats=[
            {
                "id": "b",
                "steps": [{"anim": "Write", "targets": ["t", "ax", "c"]}],
            }
        ],
    )
    assert "E108" not in codes(sc)


# --- sample project --------------------------------------------------------


def test_iter_text_fields_on_sample_q1():
    from bms.schema import iter_text_fields

    project = Project.open(SAMPLE)
    scene_data = project.load_scene("DemoParabola")
    fields = iter_text_fields(scene_data["objects"]["q1"])
    assert fields[0] == ("qmath", "y^2 = 8x")
    assert fields[1] == ("qtext", "উপকেন্দ্রিক লম্বের দৈর্ঘ্য কত?")
    assert fields[2] == ("options[0]", "2")
    assert fields[3] == ("options[1]", "4")
    assert fields[4] == ("options[2]", "8")
    assert fields[5] == ("options[3]", "16")


def test_sample_scene_validates_clean():
    project = Project.open(SAMPLE)
    results = validate_project(project)
    issues = results["DemoParabola"]
    assert [i.code for i in issues] == ["W201", "W202"]
    assert issues[0].object_id == "burst"
    assert issues[1].object_id == "tag"
    assert all(i.level == "warning" for i in issues)


# --- validate_project ------------------------------------------------------


def test_validate_project_empty_and_mismatch(tmp_path):
    root = tmp_path / "p"
    Project.create(root, "X")
    assert validate_project(Project.open(root)) == {}

    (root / "scenes" / "Alpha.scene.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "scene_id": "Beta",
                "objects": {},
                "beats": [],
            }
        ),
        encoding="utf-8",
    )
    results = validate_project(Project.open(root))
    assert [i.code for i in results["Alpha"]] == ["E102"]


def test_validate_project_unreadable_scene(tmp_path):
    root = tmp_path / "p"
    project = Project.create(root, "X")
    path = root / "scenes" / "Broken.scene.json"
    path.write_text("{not json", encoding="utf-8")
    results = validate_project(Project.open(root))
    assert [i.code for i in results["Broken"]] == ["E101"]


def test_validate_project_unknown_type_scene(tmp_path):
    root = tmp_path / "p"
    Project.create(root, "X")
    sc = scene(
        objects={"tag": {"type": "custom_label", "code": "Text('x')"}},
        beats=[{"id": "b", "steps": [{"anim": "Write", "targets": ["tag"]}]}],
    )
    (root / "scenes" / "S.scene.json").write_text(json.dumps(sc), encoding="utf-8")
    results = validate_project(Project.open(root))
    assert [i.code for i in results["S"]] == ["W202"]


# --- CLI -------------------------------------------------------------------


def test_cli_validate_sample_ok(capsys):
    rc = cli_main(["validate", str(SAMPLE)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.splitlines()[-1] == "0 error(s), 2 warning(s)"
    assert "[W201]" in out and "burst" in out
    assert "[W202]" in out and "tag" in out


def test_cli_validate_scene_filter(capsys):
    rc = cli_main(["validate", str(SAMPLE), "--scene", "DemoParabola"])
    assert rc == 0
    assert capsys.readouterr().out.count("[W20") == 2
    rc = cli_main(["validate", str(SAMPLE), "--scene", "Nope"])
    assert rc == 64
    assert "unknown scene id: Nope" in capsys.readouterr().err


def test_cli_validate_bad_project(capsys):
    rc = cli_main(["validate", "/nonexistent/project"])
    assert rc == 64
    assert capsys.readouterr().err.startswith("error:")


def test_cli_validate_reports_errors(tmp_path, capsys):
    root = tmp_path / "p"
    Project.create(root, "X")
    sc = scene(
        scene_id="Bad",
        objects={"t": {"type": "mathtex", "tex": "x"}},
        beats=[{"id": "b", "steps": [{"anim": "FadeOut", "targets": ["t"]}]}],
    )
    (root / "scenes" / "Bad.scene.json").write_text(json.dumps(sc), encoding="utf-8")
    rc = cli_main(["validate", str(root)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[E116]" in out
    assert out.splitlines()[-1] == "1 error(s), 0 warning(s)"


def test_cli_new_and_import_errors(tmp_path, capsys):
    target = tmp_path / "p"
    assert cli_main(["new", str(target), "--name", "X"]) == 0
    capsys.readouterr()
    assert cli_main(["new", str(target), "--name", "X"]) == 64
    assert "error:" in capsys.readouterr().err

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"scene_id": "bad-id"}), encoding="utf-8")
    assert cli_main(["import", str(target), str(bad)]) == 64
    assert "invalid scene_id" in capsys.readouterr().err

    assert cli_main(["import", str(target), str(SAMPLE / "scenes" / "DemoParabola.scene.json")]) == 0
    capsys.readouterr()
    assert cli_main(["import", str(target), str(SAMPLE / "scenes" / "DemoParabola.scene.json")]) == 64
    assert "error:" in capsys.readouterr().err
