from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bms import __version__
from bms.engine.audio import make_audio
from bms.project import Project
from bms.schema import format_issue, validate_project


def _cmd_new(args: argparse.Namespace) -> int:
    try:
        project = Project.create(Path(args.dir), args.name)
    except (FileExistsError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 64
    print(f"Created project '{project.settings['name']}' at {project.root}")
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    try:
        project = Project.open(Path(args.project_dir))
        scene_id = project.import_scene(Path(args.scene_json), overwrite=args.overwrite)
    except (FileExistsError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 64
    print(f"Imported scene '{scene_id}' into {project.root}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        project = Project.open(Path(args.project_dir))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 64
    if args.scene is not None and args.scene not in project.scene_ids():
        print(f"error: unknown scene id: {args.scene}", file=sys.stderr)
        return 64
    results = validate_project(project)
    if args.scene is not None:
        results = {args.scene: results.get(args.scene, [])}
    n_errors = 0
    n_warnings = 0
    for issues in results.values():
        for issue in issues:
            print(format_issue(issue))
            if issue.level == "error":
                n_errors += 1
            else:
                n_warnings += 1
    print(f"{n_errors} error(s), {n_warnings} warning(s)")
    return 1 if n_errors else 0


def _cmd_speak(args: argparse.Namespace) -> int:
    try:
        project = Project.open(Path(args.project_dir))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 64
    try:
        wav_path = make_audio(
            args.text,
            project.settings,
            project.pronunciation,
            project.subdir("narration_cache"),
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    print(str(wav_path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bms", description="Bangla Manim Studio")
    parser.add_argument("--version", action="version", version=f"bms {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_new = sub.add_parser("new", help="create a new project")
    p_new.add_argument("dir", help="project directory to create")
    p_new.add_argument("--name", required=True, help="project name")
    p_new.set_defaults(func=_cmd_new)

    p_import = sub.add_parser("import", help="import a scene JSON file")
    p_import.add_argument("project_dir", help="existing project directory")
    p_import.add_argument("scene_json", help="path to a .scene.json file")
    p_import.add_argument("--overwrite", action="store_true", help="replace existing scene")
    p_import.set_defaults(func=_cmd_import)

    p_validate = sub.add_parser("validate", help="validate scenes against the schema")
    p_validate.add_argument("project_dir", help="project directory to validate")
    p_validate.add_argument("--scene", metavar="ID", help="validate only this scene")
    p_validate.set_defaults(func=_cmd_validate)

    p_speak = sub.add_parser("speak", help="synthesize narration audio for text")
    p_speak.add_argument("project_dir", help="existing project directory")
    p_speak.add_argument("--text", required=True, help="text to speak")
    p_speak.set_defaults(func=_cmd_speak)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 0
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
