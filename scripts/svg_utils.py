#!/usr/bin/env python3
"""
High-precision anatomical & compositional analysis of the reference image,
and iterative batch SVG builder that checks the rendered canvas after each batch.
"""
import os
import json
import math
import cv2
import numpy as np
from PIL import Image
import resvg_py

REF_PATH = "/workspace/assets/2ffb4fb4-ac8d-4e15-8a84-e4aba8404c20.png"
OUT_DIR = "/workspace/output"
BATCH_DIR = "/workspace/output/batches"

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(BATCH_DIR, exist_ok=True)


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(
        int(np.clip(rgb[0], 0, 255)),
        int(np.clip(rgb[1], 0, 255)),
        int(np.clip(rgb[2], 0, 255)),
    )


def contour_to_bezier_svg_path(contour, epsilon=1.2, closed=True):
    """
    Convert an OpenCV contour (N, 1, 2) into a smooth SVG path using
    Catmull-Rom to cubic Bezier conversion or midpoint quadratic/cubic smoothing
    for organic anime illustration edges.
    """
    pts = contour.reshape(-1, 2).astype(np.float32)
    if len(pts) < 3:
        return ""
    if epsilon > 0:
        approx = cv2.approxPolyDP(pts, epsilon, closed)
        pts = approx.reshape(-1, 2).astype(np.float32)
    n = len(pts)
    if n < 3:
        return ""

    if n <= 4:
        d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
        for p in pts[1:]:
            d.append(f"L{p[0]:.1f},{p[1]:.1f}")
        if closed:
            d.append("Z")
        return "".join(d)

    # Smooth Catmull-Rom / B-spline midpoint quadratic Bezier path
    # Using midpoint Q curves produces compact, smooth, artifact-free vector paths
    d = []
    if closed:
        mid0 = (pts[-1] + pts[0]) * 0.5
        d.append(f"M{mid0[0]:.1f},{mid0[1]:.1f}")
        for i in range(n):
            p_curr = pts[i]
            p_next = pts[(i + 1) % n]
            mid = (p_curr + p_next) * 0.5
            d.append(f"Q{p_curr[0]:.1f},{p_curr[1]:.1f} {mid[0]:.1f},{mid[1]:.1f}")
        d.append("Z")
    else:
        d.append(f"M{pts[0][0]:.1f},{pts[0][1]:.1f}")
        for i in range(1, n - 1):
            p_curr = pts[i]
            p_next = pts[i + 1]
            mid = (p_curr + p_next) * 0.5
            d.append(f"Q{p_curr[0]:.1f},{p_curr[1]:.1f} {mid[0]:.1f},{mid[1]:.1f}")
        d.append(f"L{pts[-1][0]:.1f},{pts[-1][1]:.1f}")
    return "".join(d)


def render_svg_to_rgb(svg_str, width, height):
    png_bytes = resvg_py.svg_to_bytes(svg_string=svg_str, width=width, height=height)
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


if __name__ == "__main__":
    img = Image.open(REF_PATH).convert("RGB")
    arr = np.array(img)
    H, W, _ = arr.shape
    print(f"Loaded reference image: {W}x{H}")
