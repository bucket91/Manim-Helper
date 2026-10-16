from __future__ import annotations

from bms.schema.colors import COLOR_NAMES
from bms.schema.registry import (
    OBJECT_TYPES,
    ANIMATIONS,
    AnimSpec,
    ObjectSpec,
    iter_text_fields,
    object_refs,
    set_text_field,
)
from bms.schema.validate import (
    Issue,
    compile_expr,
    format_issue,
    validate_project,
    validate_scene,
)

__all__ = [
    "COLOR_NAMES",
    "OBJECT_TYPES",
    "ANIMATIONS",
    "AnimSpec",
    "ObjectSpec",
    "iter_text_fields",
    "object_refs",
    "set_text_field",
    "Issue",
    "compile_expr",
    "format_issue",
    "validate_project",
    "validate_scene",
]
