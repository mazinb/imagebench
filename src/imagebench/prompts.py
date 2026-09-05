from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any, Iterable


def package_root() -> Path:
    """Repo root when editable; otherwise the installed package dir."""
    here = Path(__file__).resolve().parent
    # Editable checkout: .../imagebench/src/imagebench → repo root
    cand = here.parents[1]
    if (cand / "prompts" / "core.jsonl").is_file():
        return cand
    return here


def prompts_dir() -> Path:
    root = package_root()
    for cand in (root / "prompts", root / "data", Path(__file__).resolve().parent / "data"):
        if (cand / "core.jsonl").is_file():
            return cand
    raise FileNotFoundError("prompts/core.jsonl not found")


def load_prompts(suite: str = "core") -> list[dict[str, Any]]:
    suite = suite.lower().strip()
    if suite not in {"core", "adult", "all"}:
        raise ValueError("suite must be core|adult|all")
    rows: list[dict[str, Any]] = []
    files: Iterable[str]
    if suite == "core":
        files = ("core.jsonl",)
    elif suite == "adult":
        files = ("adult.jsonl",)
    else:
        files = ("core.jsonl", "adult.jsonl")
    for name in files:
        path = prompts_dir() / name
        with path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    rows.sort(key=lambda r: r["id"])
    return rows


def write_prompts(dest: Path, suite: str = "all") -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in ("core.jsonl", "adult.jsonl"):
        if suite == "core" and name != "core.jsonl":
            continue
        if suite == "adult" and name != "adult.jsonl":
            continue
        src = prompts_dir() / name
        out = dest / name
        out.write_text(src.read_text())
        written.append(out)
    return written
