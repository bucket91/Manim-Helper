Before any work, read docs/BUILD_PROMPT.md PART A completely and follow it as binding spec.
OpenCode overrides to Part A:
- Ignore "you cannot run code", the "### FILE:" output format, and the "YOU RUN / EXPECTED RESULT" sections. Write files directly into the repo and run things yourself.
- All other rules stay: frozen names, paths, interfaces, CLI flags, error codes, Python 3.11, PySide6 only, no new features, no code generation.
- Python environment: use the existing micromamba env "manim" if it has Python 3.11/3.12, otherwise create one from environment.yml. Never use Python 3.13.
- Do not create a web app, React, Node or Vite files.
- Work on exactly one milestone per session. Do not start the next one.
