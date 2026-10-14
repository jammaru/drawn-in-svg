#!/usr/bin/env python3
"""
Generate a clean, pure side-by-side comparison video between the Reference Image (元画像)
and the progressive hand-drawn SVG animation (手描き過程), with no extra UI chrome.
Also generates the pure single-canvas drawing video and animated SVG.
"""

import os
import json
import shutil
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw
import resvg_py
from scripts.svg_utils import REF_PATH, OUT_DIR

BATCHES_JSON = os.path.join(OUT_DIR, "batches_data.json")
FRAMES_DIR = "/tmp/svg_video_frames"
CANVAS_FRAMES_DIR = "/tmp/svg_canvas_frames"


def build_partial_svg(W, H, bg_hex, batches, up_to_batch_idx, up_to_el_idx, sketch_opacity):
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        f'  <rect id="canvas-bg" width="{W}" height="{H}" fill="{bg_hex}"/>',
    ]
    last_centroid = (W * 0.5, H * 0.5)
    for b_idx in range(up_to_batch_idx + 1):
        b = batches[b_idx]
        b_id = b["id"]
        is_sketch = b_id in ("batch-1-rough-atari", "batch-2-rough-lineart")
        op = sketch_opacity if is_sketch else 1.0
        if op <= 0.001 and is_sketch:
            continue
        op_attr = f' opacity="{op:.3f}"' if op < 0.999 else ""
        lines.append(f'  <g id="{b_id}"{op_attr}>')

        els = b["elements"]
        limit = len(els) if b_idx < up_to_batch_idx else up_to_el_idx
        for e_i in range(limit):
            el = els[e_i]
            tag = el["tag"]
            attrs_str = " ".join(f'{k}="{v}"' for k, v in el["attrs"].items())
            lines.append(f"    <{tag} {attrs_str}/>")
            if e_i == limit - 1:
                cx = el.get("cx", W * 0.5)
                cy = el.get("cy", H * 0.5)
                last_centroid = (float(cx), float(cy))
        lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines), last_centroid


def generate_animated_svg(data, out_svg_path):
    """
    Create a self-contained animated SVG (`lgtm_character_animated.svg`) with CSS keyframe animation
    that reveals all 10 batches sequentially and fades the rough sketch layers naturally.
    """
    W, H = data["width"], data["height"]
    bg_hex = data["bg_hex"]
    batches = data["batches"]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        "  <style>",
        "    @keyframes revealStep { from { opacity: 0; } to { opacity: 1; } }",
        "    @keyframes sketchFade {",
        "      0% { opacity: 0; }",
        "      6% { opacity: 0.9; }",
        "      20% { opacity: 0.85; }",
        "      34% { opacity: 0.25; }",
        "      50% { opacity: 0.08; }",
        "      75% { opacity: 0.01; }",
        "      100% { opacity: 0; }",
        "    }",
        "    .el-anim { opacity: 0; animation: revealStep 0.14s ease-out forwards; }",
        "    #batch-1-rough-atari, #batch-2-rough-lineart { animation: sketchFade 24s linear forwards; }",
        "  </style>",
        f'  <rect id="canvas-bg" width="{W}" height="{H}" fill="{bg_hex}"/>',
    ]

    total_els = sum(len(b["elements"]) for b in batches)
    total_duration = 24.0
    global_idx = 0

    for b in batches:
        lines.append(f'  <g id="{b["id"]}" data-title="{b["title"]}">')
        for el in b["elements"]:
            delay = (global_idx / max(1, total_els)) * total_duration
            tag = el["tag"]
            attrs_str = " ".join(f'{k}="{v}"' for k, v in el["attrs"].items())
            lines.append(
                f'    <{tag} class="el-anim" style="animation-delay:{delay:.3f}s" {attrs_str}/>'
            )
            global_idx += 1
        lines.append("  </g>")

    lines.append("</svg>")
    with open(out_svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Animated SVG written to: {out_svg_path}")


def generate_videos():
    shutil.rmtree(FRAMES_DIR, ignore_errors=True)
    shutil.rmtree(CANVAS_FRAMES_DIR, ignore_errors=True)
    os.makedirs(FRAMES_DIR, exist_ok=True)
    os.makedirs(CANVAS_FRAMES_DIR, exist_ok=True)

    with open(BATCHES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    W, H = data["width"], data["height"]
    bg_hex = data["bg_hex"]
    batches = data["batches"]

    # Generate animated SVG
    anim_svg_path = os.path.join(OUT_DIR, "lgtm_character_animated.svg")
    generate_animated_svg(data, anim_svg_path)

    ref_img = Image.open(REF_PATH).convert("RGB")

    # Side-by-side comparison dimensions:
    # Each pane is 768 x 960 (preserving 1122:1402 aspect ratio), total frame = 1536 x 960 (even dimensions for H.264/VP9)
    pane_w, pane_h = 768, 960
    comp_w, comp_h = pane_w * 2, pane_h
    ref_pane = ref_img.resize((pane_w, pane_h), Image.Resampling.LANCZOS)

    # Sketch opacity schedule across the 10 batches
    sketch_opacities = [0.90, 0.85, 0.25, 0.12, 0.06, 0.03, 0.01, 0.005, 0.0, 0.0]
    frames_per_batch = [26, 28, 30, 32, 36, 36, 34, 30, 26, 22]  # 300 active drawing frames

    frame_counter = 0
    print("Rendering pure side-by-side comparison frames (Original vs Hand-Drawn SVG Process)...")

    for b_idx, b in enumerate(batches):
        els = b["elements"]
        n_els = len(els)
        n_frames = frames_per_batch[b_idx]

        prev_op = sketch_opacities[b_idx - 1] if b_idx > 0 else 0.90
        target_op = sketch_opacities[b_idx]

        for f_step in range(1, n_frames + 1):
            frac = f_step / n_frames
            el_limit = max(1, int(round(frac * n_els)))
            cur_op = prev_op + (target_op - prev_op) * frac

            svg_str, (cx, cy) = build_partial_svg(W, H, bg_hex, batches, b_idx, el_limit, cur_op)
            png_bytes = resvg_py.svg_to_bytes(svg_string=svg_str, width=W, height=H)
            arr_u8 = np.frombuffer(png_bytes, dtype=np.uint8)
            bgr = cv2.imdecode(arr_u8, cv2.IMREAD_COLOR)
            canvas_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

            canvas_pil = Image.fromarray(canvas_rgb)
            draw_pane = canvas_pil.resize((pane_w, pane_h), Image.Resampling.LANCZOS)
            draw_c = ImageDraw.Draw(draw_pane)

            # Subtle pen/brush tip indicator on the drawing pane
            sx = int(cx * pane_w / W)
            sy = int(cy * pane_h / H)
            draw_c.ellipse([sx - 7, sy - 7, sx + 7, sy + 7], outline="#ff4757", width=2)

            # Save single-canvas frame
            draw_pane.save(os.path.join(CANVAS_FRAMES_DIR, f"frame_{frame_counter:04d}.png"))

            # Pure Side-by-Side Comparison Frame: Left = Reference Image (元画像), Right = Hand-Drawn SVG (手描き動画)
            side_by_side = Image.new("RGB", (comp_w, comp_h), (252, 251, 248))
            side_by_side.paste(ref_pane, (0, 0))
            side_by_side.paste(draw_pane, (pane_w, 0))

            # Subtle 2px vertical divider line between original and drawing canvas
            s_draw = ImageDraw.Draw(side_by_side)
            s_draw.line([(pane_w, 0), (pane_w, comp_h)], fill=(215, 212, 205), width=2)

            side_by_side.save(os.path.join(FRAMES_DIR, f"frame_{frame_counter:04d}.png"))
            frame_counter += 1

    # Hold final completed state for 40 frames (1.33 seconds) without brush cursor
    final_pil = Image.open(os.path.join(OUT_DIR, "lgtm_character_final.png")).convert("RGB")
    final_pane = final_pil.resize((pane_w, pane_h), Image.Resampling.LANCZOS)

    final_side_by_side = Image.new("RGB", (comp_w, comp_h), (252, 251, 248))
    final_side_by_side.paste(ref_pane, (0, 0))
    final_side_by_side.paste(final_pane, (pane_w, 0))
    s_draw = ImageDraw.Draw(final_side_by_side)
    s_draw.line([(pane_w, 0), (pane_w, comp_h)], fill=(215, 212, 205), width=2)

    for _ in range(40):
        final_pane.save(os.path.join(CANVAS_FRAMES_DIR, f"frame_{frame_counter:04d}.png"))
        final_side_by_side.save(os.path.join(FRAMES_DIR, f"frame_{frame_counter:04d}.png"))
        frame_counter += 1

    print(f"Rendered {frame_counter} total frames. Encoding MP4 and WebM videos with ffmpeg...")

    studio_mp4 = os.path.join(OUT_DIR, "drawing_process_full.mp4")
    studio_webm = os.path.join(OUT_DIR, "drawing_process_full.webm")
    canvas_mp4 = os.path.join(OUT_DIR, "drawing_process_canvas.mp4")

    subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", "30",
            "-i", os.path.join(FRAMES_DIR, "frame_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17",
            studio_mp4,
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", "30",
            "-i", os.path.join(FRAMES_DIR, "frame_%04d.png"),
            "-c:v", "libvpx-vp9", "-b:v", "2.5M", "-crf", "22",
            studio_webm,
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", "30",
            "-i", os.path.join(CANVAS_FRAMES_DIR, "frame_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17",
            canvas_mp4,
        ],
        check=True,
    )
    print(f"Videos successfully generated:\n - {studio_mp4}\n - {studio_webm}\n - {canvas_mp4}")


if __name__ == "__main__":
    generate_videos()
