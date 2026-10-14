#!/usr/bin/env python3
"""
Step-by-step Batch SVG Generator & Evaluator.
Generates batches 1 through 8 sequentially, rendering and inspecting the canvas
after each batch to determine and refine subsequent batches.
"""

import os
import json
import math
import cv2
import numpy as np
from PIL import Image
from skimage.segmentation import slic
from scripts.svg_utils import (
    REF_PATH,
    OUT_DIR,
    BATCH_DIR,
    rgb_to_hex,
    contour_to_bezier_svg_path,
    render_svg_to_rgb,
)
from scripts.sketch_extractor import extract_anatomical_guidelines


def get_foreground_mask(arr):
    """Extract clean foreground mask including character, signboard, sparks, and floor shadow."""
    H, W, _ = arr.shape
    bg_color = arr[0, 0].astype(np.float32)
    dist_bg = np.linalg.norm(arr.astype(np.float32) - bg_color, axis=2)

    # Include subtle floor shadow at the bottom
    barrier = dist_bg > 10.0
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    b_closed = cv2.morphologyEx(barrier.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    num_labels, labels = cv2.connectedComponents(1 - b_closed)
    corner_labels = {labels[0, 0], labels[0, W - 1], labels[H - 1, 0], labels[H - 1, W - 1]}
    ext_bg = np.isin(labels, list(corner_labels))
    fg_mask = ~ext_bg

    # Also include floor shadow under feet (y: 1290..1385, x: 240..640) where dist_bg > 3.5
    shadow_roi = np.zeros_like(fg_mask)
    shadow_roi[1285:1388, 235:645] = True
    floor_shadow = shadow_roi & (dist_bg > 3.5)
    return fg_mask | floor_shadow


def get_region_weight_map(H, W, fg_mask):
    """
    Create perceptual importance map:
    - Face, eyes, mouth, blush, leaf, ears: highest importance
    - LGTM signboard, hands, bells/ribbons, hair details: high importance
    - Jacket, dress, legs, shoes: medium-high importance
    """
    weights = np.ones((H, W), dtype=np.float32) * 1.0
    # Face & eyes (x: 430..650, y: 150..320)
    weights[150:320, 430:650] = 4.5
    # Eyes specifically
    weights[195:275, 455:635] = 7.0
    # Leaf & Kemonomimi ears & top hair
    weights[15:165, 380:680] = 3.0
    # LGTM Signboard & sparks & right hand
    weights[55:380, 700:1035] = 4.0
    # Left hand peace sign
    weights[220:360, 290:415] = 3.5
    # Chest ribbon & bells & waist bells
    weights[330:450, 490:615] = 3.2
    weights[560:720, 355:690] = 2.5
    # Shoes & bows & bells
    weights[820:1050, 295:450] = 3.0
    weights[1140:1385, 390:575] = 3.0
    return weights * fg_mask.astype(np.float32)


def extract_slic_polygons(arr, mask, n_segments, compactness, epsilon=1.2, dilate_px=1, min_area=12):
    """
    Segment the masked region using SLIC superpixels, extract smoothed Bezier SVG paths
    and accurate mean RGB colors.
    """
    H, W, _ = arr.shape
    if mask.sum() < min_area:
        return []

    segments = slic(
        arr,
        n_segments=n_segments,
        compactness=compactness,
        sigma=0.8,
        start_label=1,
        mask=mask,
        enforce_connectivity=True,
    )

    elements = []
    max_label = segments.max()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1)) if dilate_px > 0 else None

    for lbl in range(1, max_label + 1):
        reg_mask = segments == lbl
        area = int(reg_mask.sum())
        if area < min_area:
            continue

        mean_rgb = arr[reg_mask].mean(axis=0)
        color_hex = rgb_to_hex(mean_rgb)

        m_u8 = reg_mask.astype(np.uint8) * 255
        if kernel is not None:
            m_u8 = cv2.dilate(m_u8, kernel, iterations=1)

        contours, _ = cv2.findContours(m_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            continue
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) < min_area:
            continue

        d = contour_to_bezier_svg_path(c, epsilon=epsilon, closed=True)
        if not d:
            continue

        ys, xs = np.where(reg_mask)
        cx, cy = float(xs.mean()), float(ys.mean())
        luma = 0.299 * mean_rgb[0] + 0.587 * mean_rgb[1] + 0.114 * mean_rgb[2]

        elements.append({
            "tag": "path",
            "attrs": {
                "d": d,
                "fill": color_hex,
            },
            "cx": cx,
            "cy": cy,
            "area": area,
            "luma": float(luma),
            "rgb": mean_rgb.tolist(),
        })

    return elements


def build_svg_document(W, H, bg_hex, active_batches, include_sketch_underlay=False, sketch_opacity_scale=1.0):
    """Assemble an SVG string from a list of element dicts."""
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        f'  <rect id="canvas-bg" width="{W}" height="{H}" fill="{bg_hex}"/>',
    ]
    for b_idx, batch_info in enumerate(active_batches):
        b_id = batch_info["id"]
        b_title = batch_info["title"]
        grp_opacity = batch_info.get("group_opacity", 1.0)
        op_attr = f' opacity="{grp_opacity:.2f}"' if grp_opacity < 0.999 else ""
        lines.append(f'  <g id="{b_id}" data-title="{b_title}"{op_attr}>')
        for el in batch_info["elements"]:
            tag = el["tag"]
            attrs_str = " ".join(f'{k}="{v}"' for k, v in el["attrs"].items())
            lines.append(f"    <{tag} {attrs_str}/>")
        lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines)


def count_drawable_elements(batches):
    """Count total drawable SVG elements across all batches (+1 for canvas background rect)."""
    return 1 + sum(len(b["elements"]) for b in batches)
