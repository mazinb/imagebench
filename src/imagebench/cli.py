from __future__ import annotations

import argparse
import json
import platform
import shutil
from pathlib import Path

from . import __version__
from .prompts import load_prompts, write_prompts
from .run import (
    generate_cmd,
    generate_openai,
    new_run_id,
    report_summary,
    save_result,
    score_openai_vlm,
)


def _hw() -> dict:
    return {
        "gpu": "",
        "vram_gib": None,
        "ram_gib": None,
        "unified_memory": False,
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
    }


def cmd_prompts(args: argparse.Namespace) -> int:
    dest = Path(args.out or ".")
    written = write_prompts(dest / "prompts" if dest.name != "prompts" else dest, suite=args.suite)
    for p in written:
        print(p)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    suite = args.suite
    prompts = load_prompts(suite)
    run_id = args.run_id or new_run_id()
    out_root = Path(args.out or "results") / run_id
    img_dir = out_root / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    model_id = args.model or "custom"
    rows = []
    print(f"[imagebench] suite={suite} prompts={len(prompts)} → {out_root}")
    for i, prompt in enumerate(prompts, 1):
        dest = img_dir / f"{prompt['id']}.png"
        print(f"[{i}/{len(prompts)}] {prompt['id']} {prompt.get('category')}", flush=True)
        if args.adapter == "openai":
            meta = generate_openai(
                prompt,
                dest,
                base_url=args.base_url,
                model=args.model,
                seed=args.seed,
            )
        else:
            if not args.cmd:
                raise SystemExit("--cmd required for adapter=cmd")
            meta = generate_cmd(prompt, dest, args.cmd, args.seed)
        rows.append(
            {
                "id": prompt["id"],
                "category": prompt.get("category"),
                "pass": None,
                "score": None,
                "verdict": None,
                "gen_seconds": meta.get("gen_seconds"),
                "image": str(Path("images") / dest.name),
            }
        )
    result = {
        "schema": "imagebench/v1",
        "run_id": run_id,
        "suite": suite,
        "model": {
            "id": model_id,
            "backend": args.adapter,
            "seed": args.seed,
            "steps": None,
            "cfg": None,
        },
        "hardware": _hw(),
        "prompts": rows,
    }
    save_result(out_root / "results.json", result)
    print(report_summary(result))
    print(f"wrote {out_root / 'results.json'}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    root = Path(args.run)
    path = root / "results.json" if root.is_dir() else root
    result = json.loads(path.read_text())
    by_id = {p["id"]: p for p in load_prompts(result.get("suite") or "all")}
    img_root = path.parent
    for row in result["prompts"]:
        if row.get("pass") is not None and not args.force:
            continue
        prompt = by_id.get(row["id"])
        if not prompt:
            continue
        image = img_root / row.get("image", f"images/{row['id']}.png")
        if not image.is_file():
            print(f"skip {row['id']}: missing {image}")
            continue
        print(f"score {row['id']}", flush=True)
        scored = score_openai_vlm(
            prompt,
            image,
            base_url=args.base_url,
            model=args.judge_model,
        )
        row.update(scored)
        save_result(path, result)
    print(report_summary(result))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    root = Path(args.run)
    path = root / "results.json" if root.is_dir() else root
    result = json.loads(path.read_text())
    print(report_summary(result))
    return 0


def cmd_can_i_run(args: argparse.Namespace) -> int:
    need = args.vram
    print(f"fits badge target: {need} GiB VRAM (or unified RAM)")
    print("Pass if your measured peak_vram_gib (or peak_ram on unified) ≤ this.")
    print("ImageBench itself is only prompts + scoring — your generator sets the footprint.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="imagebench", description="On-device T2I pass/fail bench")
    ap.add_argument("--version", action="version", version=f"imagebench {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prompts", help="copy prompt JSONL into a directory")
    p.add_argument("--suite", default="all", choices=["core", "adult", "all"])
    p.add_argument("--out", default=".")
    p.set_defaults(func=cmd_prompts)

    r = sub.add_parser("run", help="generate stills for a suite")
    r.add_argument("--suite", default="core", choices=["core", "adult", "all"])
    r.add_argument("--adapter", default="cmd", choices=["cmd", "openai"])
    r.add_argument("--cmd", default="", help='shell command; uses $PROMPT $OUT $SEED $WIDTH $HEIGHT')
    r.add_argument("--base-url", default="http://127.0.0.1:8001/v1")
    r.add_argument("--model", default="local")
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--out", default="results")
    r.add_argument("--run-id", default="")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("score", help="score a run with an OpenAI-compatible VLM")
    s.add_argument("run", help="results dir or results.json")
    s.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    s.add_argument("--judge-model", default="local")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_score)

    t = sub.add_parser("report", help="print pass/fail summary")
    t.add_argument("run")
    t.set_defaults(func=cmd_report)

    c = sub.add_parser("can-i-run", help="print fits guidance")
    c.add_argument("--vram", type=float, default=12.0)
    c.add_argument("--ram", type=float, default=32.0)
    c.set_defaults(func=cmd_can_i_run)

    args = ap.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
