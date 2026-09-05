from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


def _http_json(method: str, url: str, payload: dict | None = None, timeout: float = 300) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def generate_cmd(prompt: dict[str, Any], out: Path, cmd: str, seed: int) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(
        {
            "PROMPT": prompt["prompt"],
            "OUT": str(out),
            "SEED": str(seed),
            "WIDTH": str(prompt.get("width") or 1024),
            "HEIGHT": str(prompt.get("height") or 1024),
            "PROMPT_ID": prompt["id"],
            "CATEGORY": prompt.get("category") or "",
        }
    )
    t0 = time.time()
    r = subprocess.run(cmd, shell=True, env=env)
    seconds = round(time.time() - t0, 2)
    if r.returncode != 0:
        raise RuntimeError(f"generator exited {r.returncode} for prompt {prompt['id']}")
    if not out.is_file():
        raise RuntimeError(f"generator did not write {out}")
    return {"gen_seconds": seconds, "image": str(out)}


def generate_openai(
    prompt: dict[str, Any],
    out: Path,
    *,
    base_url: str,
    model: str,
    seed: int,
    api_key: str | None = None,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/images/generations"
    else:
        url = f"{base}/v1/images/generations"
    payload = {
        "model": model,
        "prompt": prompt["prompt"],
        "size": f"{prompt.get('width') or 1024}x{prompt.get('height') or 1024}",
        "n": 1,
        "response_format": "b64_json",
    }
    if seed is not None:
        payload["seed"] = seed
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = api_key or os.environ.get("OPENAI_API_KEY") or "not-needed"
    headers["Authorization"] = f"Bearer {key}"
    t0 = time.time()
    req = request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode())
    except error.HTTPError as e:
        raise RuntimeError(f"openai images HTTP {e.code}: {e.read()[:400]!r}") from e
    seconds = round(time.time() - t0, 2)
    data = (body.get("data") or [None])[0] or {}
    b64 = data.get("b64_json")
    if not b64:
        raise RuntimeError("openai response missing b64_json")
    import base64

    out.write_bytes(base64.b64decode(b64))
    return {"gen_seconds": seconds, "image": str(out)}


def score_openai_vlm(
    prompt: dict[str, Any],
    image_path: Path,
    *,
    base_url: str,
    model: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    import base64

    base = base_url.rstrip("/")
    url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
    mime = "image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    data_url = f"data:{mime};base64,{base64.b64encode(image_path.read_bytes()).decode()}"
    rubric = "\n".join(prompt.get("rubric") or [])
    system = (
        "You score one generated still against a fixed rubric. "
        "Pass only if EVERY rubric item is clearly satisfied. "
        'Reply with compact JSON only: {"pass":true,"score":8,"verdict":"one short sentence"}'
    )
    user = f"Prompt: {prompt['prompt']}\nRubric:\n{rubric}"
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 220,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key or os.environ.get('OPENAI_API_KEY') or 'not-needed'}"}
    req = request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read().decode())
    text = body["choices"][0]["message"]["content"]
    start = text.find("{")
    end = text.rfind("}")
    obj = json.loads(text[start : end + 1]) if start >= 0 and end > start else {}
    return {
        "pass": obj.get("pass") is True,
        "score": obj.get("score"),
        "verdict": str(obj.get("verdict") or "")[:2000],
    }


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def save_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")


def report_summary(result: dict[str, Any]) -> str:
    prompts = result.get("prompts") or []
    rated = [p for p in prompts if p.get("pass") is not None]
    passed = sum(1 for p in rated if p.get("pass") is True)
    failed = sum(1 for p in rated if p.get("pass") is False)
    scores = [p["score"] for p in rated if isinstance(p.get("score"), (int, float))]
    secs = [p["gen_seconds"] for p in prompts if isinstance(p.get("gen_seconds"), (int, float))]
    by_cat: dict[str, list[bool]] = {}
    for p in rated:
        cat = str(p.get("category") or "other")
        by_cat.setdefault(cat, []).append(bool(p.get("pass")))
    lines = [
        f"run {result.get('run_id')} · suite={result.get('suite')} · model={result.get('model', {}).get('id')}",
        f"pass {passed}/{len(rated) or len(prompts)} · fail {failed} · unrated {len(prompts) - len(rated)}",
    ]
    if scores:
        lines.append(f"avg score {sum(scores)/len(scores):.1f}/10")
    if secs:
        secs_s = sorted(secs)
        mid = secs_s[len(secs_s) // 2]
        lines.append(f"median gen {mid:.1f}s ({len(secs)} timed)")
    if by_cat:
        lines.append("by category:")
        for cat, vals in sorted(by_cat.items()):
            lines.append(f"  {cat}: {sum(vals)}/{len(vals)}")
    return "\n".join(lines)
