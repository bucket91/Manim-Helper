# Bangla Manim Studio (`bms`)

A desktop app for a Bangla math/science video animator. AI-written scene
scripts (JSON) are rendered by [Manim](https://www.manim.community/) with
Bangla [edge-tts](https://github.com/rany2/edge-tts) narration. The human edits
narration text and on-screen text in a GUI, sees exactly what changed versus
the AI's original (as a compact report to paste back to the AI), previews a
frame, a beat or a whole scene, then renders and stitches scenes.

Full specification and build plan: [docs/BUILD_PROMPT.md](docs/BUILD_PROMPT.md).

## Quick start

1. `micromamba env create -f environment.yml && micromamba activate bms`
2. `bms new /tmp/demo --name Demo`
3. `bms import /tmp/demo samples/demo_project/scenes/DemoParabola.scene.json`
4. `bms validate /tmp/demo`
5. `bms render /tmp/demo --scene DemoParabola --quality draft`
6. `bms stitch /tmp/demo --quality draft`
7. `bms gui /tmp/demo`
8. `bms diff /tmp/demo` to list your edits, `bms report /tmp/demo` to export them
9. `bms doctor` to check the environment
10. `pytest -q -m "not manim"` for the test suite

Not every CLI command exists yet; the project is built in milestones M0-M9 as
described in [docs/BUILD_PROMPT.md](docs/BUILD_PROMPT.md).
