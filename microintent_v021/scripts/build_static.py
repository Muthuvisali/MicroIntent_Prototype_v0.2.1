"""Build the static (Pyodide) demo into dist/ for a Hugging Face static Space.

Usage: python scripts/build_static.py
The output is self-contained: index.html, the shim, the Python package and the catalog.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PYODIDE_INDEX = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/"

SPACE_README = """---
title: MicroIntent
emoji: 🔎
colorFrom: purple
colorTo: yellow
sdk: static
app_file: index.html
pinned: false
short_description: Micro-intent sponsored matching for AI search
---

# MicroIntent — public demo

Independent portfolio prototype exploring whether conversational AI can match a small number of
clearly labeled sponsored recommendations to the exact sub-intent where they are useful.
Not affiliated with Google; synthetic merchant data; transparent simulated ranking.

This Space runs the prototype's Python pipeline **in your browser** with
[Pyodide](https://pyodide.org) — there is no server. It uses the deterministic extractor
(no LLM calls). Source code, tests and the Gemini extraction mode:
https://github.com/Muthuvisali/MicroIntent_Prototype_v0.2.1
"""


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    py_files = []
    for src in sorted((ROOT / "app").rglob("*.py")):
        rel = src.relative_to(ROOT).as_posix()
        if rel == "app/main.py":  # FastAPI server entry point; not used in the browser
            continue
        (DIST / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, DIST / rel)
        py_files.append(rel)
    shutil.copy2(ROOT / "static_demo" / "demo_api.py", DIST / "demo_api.py")
    py_files.append("demo_api.py")
    (DIST / "data").mkdir()
    shutil.copy2(ROOT / "data" / "products.json", DIST / "data" / "products.json")
    py_files.append("data/products.json")

    shim = (ROOT / "static_demo" / "shim.js").read_text(encoding="utf-8")
    config = f"const PYODIDE_INDEX = {json.dumps(PYODIDE_INDEX)};\nconst PY_FILES = {json.dumps(py_files)};\n"
    (DIST / "shim.js").write_text(config + shim, encoding="utf-8")

    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    loader = (
        f'<script src="{PYODIDE_INDEX}pyodide.js"></script>\n'
        '<script src="shim.js"></script>\n<script>'
    )
    assert html.count("<script>") == 1
    html = html.replace("<script>", loader, 1)
    html = html.replace(
        "Public demo: runs the transparent rule-based extractor, with no LLM calls.",
        "Public demo: the Python pipeline runs in your browser (Pyodide) with the transparent rule-based extractor, with no LLM calls.",
    )
    (DIST / "index.html").write_text(html, encoding="utf-8")
    (DIST / "README.md").write_text(SPACE_README, encoding="utf-8")
    print(f"Built {DIST} with {len(py_files)} runtime files")


if __name__ == "__main__":
    main()
