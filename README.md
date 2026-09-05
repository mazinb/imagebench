# ImageBench

50-prompt text-to-image pass/fail bench you run on your own GPU.

Reference gallery: [app.getzoro.com/imagebench](https://app.getzoro.com/imagebench)

## Quick start

```bash
git clone https://github.com/mazinb/imagebench.git
cd imagebench
pip install -e .

# Your generator: write a PNG to $OUT from $PROMPT
cat > gen.sh <<'EOF'
#!/usr/bin/env bash
# set -euo pipefail
# call your Comfy / Forge / API here
# env: PROMPT OUT SEED WIDTH HEIGHT
EOF
chmod +x gen.sh

imagebench run --cmd './gen.sh'              # core 40 (SFW)
imagebench run --suite all --cmd './gen.sh'  # all 50
imagebench score --base-url http://127.0.0.1:8000/v1
imagebench report ./results/<run-id>
```

OpenAI-compatible images API:

```bash
imagebench run --adapter openai \
  --base-url http://127.0.0.1:8001/v1 --model my-model
```

## Suites

| Suite | Prompts | Default |
| --- | --- | --- |
| `core` | 40 SFW | yes |
| `adult` | 10 optional NSFW | no |
| `all` | 50 | `imagebench run --suite all` |

Each prompt has a 3-bullet rubric. Score with any OpenAI-compatible VLM (`pass` + `score` 1–10 + `verdict`).

## What we track

Pass rate · avg score · median gen time · peak VRAM/RAM (when your runner reports it).

## Submit results

Open a PR with `submissions/<your-name>/<run-id>.json` (scores + hardware; keep PNGs out of git).

## License

Apache-2.0 for the harness and SFW prompts. The adult pack is 18+; do not use it in public demos without an age gate.
