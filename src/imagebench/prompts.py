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
        if not path.is_file():
            raise FileNotFoundError(f"Prompts file not found: {path}")
        # Validate file size (max 10MB)
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError(f"Prompts file too large: {path}")
        with path.open(encoding='utf-8') as f:
            line_num = 0
            for line in f:
                line_num += 1
                line = line.strip()
                if line:
                    try:
                        prompt_obj = json.loads(line)
                        # Validate required fields
                        if not isinstance(prompt_obj.get("id"), str):
                            raise ValueError("Missing or invalid 'id' field")
                        if not isinstance(prompt_obj.get("prompt"), str):
                            raise ValueError("Missing or invalid 'prompt' field")
                        rows.append(prompt_obj)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON at line {line_num} in {name}: {e}") from e
                    except ValueError as e:
                        raise ValueError(f"Invalid prompt at line {line_num} in {name}: {e}") from e
    rows.sort(key=lambda r: r.get("id", ""))
    return rows


def write_prompts(dest: Path, suite: str = "all") -> list[Path]:
    # Validate suite parameter
    if suite not in {"core", "adult", "all"}:
        raise ValueError("suite must be core|adult|all")
    
    # Validate destination path
    try:
        dest_resolved = dest.resolve()
    except (ValueError, OSError) as e:
        raise ValueError(f"Invalid destination path: {e}") from e
    
    dest_resolved.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in ("core.jsonl", "adult.jsonl"):
        if suite == "core" and name != "core.jsonl":
            continue
        if suite == "adult" and name != "adult.jsonl":
            continue
        # Validate filename to prevent path traversal
        if "/" in name or "\\" in name or ".." in name:
            raise ValueError(f"Invalid filename: {name}")
        src = prompts_dir() / name
        if not src.is_file():
            raise FileNotFoundError(f"Source file not found: {src}")
        out = dest_resolved / name
        # Ensure output path is under destination directory
        try:
            out_resolved = out.resolve()
            if not str(out_resolved).startswith(str(dest_resolved)):
                raise ValueError(f"Output path escapes destination: {out}")
        except (ValueError, OSError) as e:
            raise ValueError(f"Invalid output path: {e}") from e
        out_resolved.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
        written.append(out_resolved)
    return written
