from __future__ import annotations

import argparse
from pathlib import Path

from bms import __version__
from bms.project import Project


def _cmd_new(args: argparse.Namespace) -> int:
    project = Project.create(Path(args.dir), args.name)
    print(f"Created project '{project.settings['name']}' at {project.root}")
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    project = Project.open(Path(args.project_dir))
    scene_id = project.import_scene(Path(args.scene_json), overwrite=args.overwrite)
    print(f"Imported scene '{scene_id}' into {project.root}")
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
