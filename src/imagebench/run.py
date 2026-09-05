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
    # Validate URL scheme
    if not url.startswith(('http://', 'https://')):
        raise ValueError(f"Invalid URL scheme, must be http:// or https://: {url}")
    
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            # Limit response size to prevent memory exhaustion
            content = resp.read(50 * 1024 * 1024)  # 50MB max
            return json.loads(content.decode())
    except error.HTTPError as e:
        error_body = e.read()[:1000].decode('utf-8', errors='replace')
        raise RuntimeError(f"HTTP {e.code} error: {error_body}") from e
    except error.URLError as e:
        raise RuntimeError(f"URL error: {e}") from e


def generate_cmd(prompt: dict[str, Any], out: Path, cmd: str, seed: int) -> dict[str, Any]:
    # Validate output path to prevent path traversal
    try:
        out_resolved = out.resolve()
        if not str(out_resolved).startswith(str(Path.cwd())):
            raise ValueError(f"Output path {out} is outside working directory")
    except (ValueError, OSError) as e:
        raise RuntimeError(f"Invalid output path: {e}") from e
    
    # Sanitize environment variable values
    def sanitize_env_value(value: str) -> str:
        # Remove null bytes and limit length to prevent abuse
        return str(value).replace('\x00', '')[:10000]
    
    env = os.environ.copy()
    env.update(
        {
            "PROMPT": sanitize_env_value(prompt.get("prompt", "")),
            "OUT": str(out_resolved),
            "SEED": str(seed),
            "WIDTH": str(int(prompt.get("width") or 1024)),
            "HEIGHT": str(int(prompt.get("height") or 1024)),
            "PROMPT_ID": sanitize_env_value(prompt.get("id", "")),
            "CATEGORY": sanitize_env_value(prompt.get("category") or ""),
        }
    )
    t0 = time.time()
    # Use shell=True but with explicit shell and capture output for better error reporting
    # Users should ensure their --cmd is trusted. For production, consider using shlex.split
    # and shell=False with a wrapper script approach instead.
    r = subprocess.run(
        cmd,
        shell=True,
        env=env,
        capture_output=True,
        text=True,
        timeout=600  # 10 minute timeout to prevent hanging
    )
    seconds = round(time.time() - t0, 2)
    if r.returncode != 0:
        stderr_preview = r.stderr[:500] if r.stderr else "no stderr"
        raise RuntimeError(
            f"generator exited {r.returncode} for prompt {prompt['id']}: {stderr_preview}"
        )
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
    # Validate URL
    if not base_url.startswith(('http://', 'https://')):
        raise ValueError(f"Invalid base_url scheme: {base_url}")
    
    # Validate output path
    try:
        out_resolved = out.resolve()
    except (ValueError, OSError) as e:
        raise RuntimeError(f"Invalid output path: {e}") from e
    
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/images/generations"
    else:
        url = f"{base}/v1/images/generations"
    
    # Validate dimensions
    width = int(prompt.get('width') or 1024)
    height = int(prompt.get('height') or 1024)
    if not (64 <= width <= 4096 and 64 <= height <= 4096):
        raise ValueError(f"Invalid dimensions: {width}x{height} (must be 64-4096)")
    
    payload = {
        "model": model,
        "prompt": str(prompt.get("prompt", ""))[:10000],  # Limit prompt length
        "size": f"{width}x{height}",
        "n": 1,
        "response_format": "b64_json",
    }
    if seed is not None:
        payload["seed"] = int(seed)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = api_key or os.environ.get("OPENAI_API_KEY") or "not-needed"
    headers["Authorization"] = f"Bearer {key}"
    t0 = time.time()
    req = request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=600) as resp:
            # Limit response size to 100MB
            content = resp.read(100 * 1024 * 1024)
            body = json.loads(content.decode())
    except error.HTTPError as e:
        error_body = e.read()[:400].decode('utf-8', errors='replace')
        raise RuntimeError(f"openai images HTTP {e.code}: {error_body}") from e
    except error.URLError as e:
        raise RuntimeError(f"URL error: {e}") from e
    seconds = round(time.time() - t0, 2)
    data = (body.get("data") or [None])[0] or {}
    b64 = data.get("b64_json")
    if not b64:
        raise RuntimeError("openai response missing b64_json")
    import base64

    try:
        image_data = base64.b64decode(b64)
        # Validate decoded size (max 50MB)
        if len(image_data) > 50 * 1024 * 1024:
            raise ValueError(f"Decoded image too large: {len(image_data)} bytes")
        out_resolved.write_bytes(image_data)
    except Exception as e:
        raise RuntimeError(f"Failed to decode/write image: {e}") from e
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

    # Validate image file exists and is not too large (20MB limit)
    if not image_path.is_file():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    file_size = image_path.stat().st_size
    if file_size > 20 * 1024 * 1024:  # 20MB
        raise ValueError(f"Image file too large: {file_size} bytes (max 20MB)")
    
    if file_size == 0:
        raise ValueError(f"Image file is empty: {image_path}")

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
    try:
        with request.urlopen(req, timeout=180) as resp:
            # Limit response size
            content = resp.read(1024 * 1024)  # 1MB max for VLM response
            body = json.loads(content.decode())
    except error.HTTPError as e:
        error_body = e.read()[:400].decode('utf-8', errors='replace')
        raise RuntimeError(f"VLM scoring HTTP {e.code}: {error_body}") from e
    except error.URLError as e:
        raise RuntimeError(f"VLM scoring URL error: {e}") from e
    
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected VLM response format: {body}") from e
    
    start = text.find("{")
    end = text.rfind("}")
    obj = {}
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            # If JSON parsing fails, return empty result
            pass
    
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
