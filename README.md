# ImageBench

A comprehensive 50-prompt text-to-image benchmark testing real-world generation quality across 12 critical capabilities. Run it on your own GPU with any model or API.

Reference gallery: [app.getzoro.com/imagebench](https://app.getzoro.com/imagebench)

## What ImageBench Tests

ImageBench evaluates the hardest challenges for text-to-image models through **12 categories** that frequently cause failures:

### Core Categories (40 prompts)

1. **Hands** (6 prompts) - Correct finger count, natural poses, proper anatomy
   - *Example: "Open palm facing camera, all five fingers clearly spread apart"*

2. **Text Rendering** (6 prompts) - Readable text, correct spelling, proper placement
   - *Example: "Event poster with bold title 'Summer Festival' at top"*

3. **Counting** (5 prompts) - Exact object counts as specified
   - *Example: "Exactly four red apples arranged to the left of exactly three green apples"*

4. **Spatial Relationships** (5 prompts) - Objects positioned correctly relative to each other
   - *Example: "A woman standing in front of a mirror, both her and reflection visible"*

5. **Physics & Optics** (5 prompts) - Realistic reflections, shadows, refraction
   - *Example: "Glass of water with a straw appearing bent at the water line"*

6. **Style Adherence** (5 prompts) - Matching specific artistic styles and techniques
   - *Example: "Renaissance oil painting in the style of Caravaggio"*

7. **Story Stills** (3 prompts) - Scene composition with narrative clarity
   - *Example: "Pixar-style kids book still of a fox peeking into a bedroom"*

8. **Animal Anatomy** (1 prompt) - Correct animal body structure and proportions
   - *Example: "Horse at a walk, all four legs visible and correctly jointed"*

9. **Fine Detail** (1 prompt) - Extreme close-up texture and micro-detail
   - *Example: "Macro photograph of skin: pores, fine hairs, droplet of sweat"*

10. **Feet** (1 prompt) - Often-neglected extremity anatomy
    - *Example: "Full-body person standing, both shoes fully visible"*

11. **Identity Consistency** (1 prompt) - Same character across multiple panels
    - *Example: "Two-panel image: same fox in both, different poses"*

12. **Negative Prompts** (1 prompt) - Avoiding unwanted elements
    - *Example: "Lighthouse illustration, absolutely no letters, no text of any kind"*

### Adult Suite (10 prompts - optional)

- **Uncensored** (10 prompts) - Tests for censorship bypasses and NSFW handling (18+ only)

Each prompt includes a 3-point rubric for objective pass/fail scoring.

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

## Why These Categories Matter

These aren't cherry-picked edge cases—they're **real user pain points**:

- **Hands & Feet**: The #1 and #2 most common generation failures
- **Text**: Critical for posters, UI mockups, social media, book covers
- **Counting**: "Show me exactly 3 options" shouldn't give you 2 or 4
- **Spatial**: "Behind", "in front of", "between"—basic composition users expect
- **Physics**: Believable lighting and reflections separate good from great
- **Style**: Artists need Caravaggio to look like Caravaggio, not generic oil painting
- **Identity**: Character consistency across panels for comics, storyboards, branding

## Suites

| Suite | Prompts | Categories | Default |
| --- | --- | --- | --- |
| `core` | 40 | 12 capability tests (SFW) | ✓ yes |
| `adult` | 10 | Uncensored (18+ NSFW) | no |
| `all` | 50 | Complete benchmark | `--suite all` |

Each prompt includes a 3-bullet rubric for objective VLM scoring (`pass` + `score` 1–10 + `verdict`).

## Metrics Tracked

- **Pass rate** - Percentage of prompts that meet all rubric criteria
- **Average score** - Quality rating (1-10) across passed prompts
- **Median generation time** - Performance benchmark
- **Peak VRAM/RAM** - Hardware requirements (when your runner reports it)
- **By-category breakdown** - Identify specific model weaknesses

## Submit results

Open a PR with `submissions/<your-name>/<run-id>.json` (scores + hardware; keep PNGs out of git).

## License

Apache-2.0 for the harness and SFW prompts. The adult pack is 18+; do not use it in public demos without an age gate.
