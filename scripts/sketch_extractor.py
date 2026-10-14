#!/usr/bin/env python3
"""
Iterative Batch SVG Builder:
Builds the high-precision SVG (1,500 - 1,700 elements) in 8 sequential batches across 4 human drawing phases:
Phase 1: ラフスケッチを描き、構図や比率を決める (Rough Sketch & Proportions)
  - Batch 1: アタリ線・頭部十字線・骨格ガイド・LGTM看板とポーズの構図スケッチ (72 elements)
  - Batch 2: キャラクター輪郭・髪房・衣装・手指・看板のラフペン入れ線画 (98 elements)
Phase 2: 大きな色面を配置し、明暗関係を構築する (Large Color Flats & Value Structure)
  - Batch 3: ベースシルエット・接地影・肌・髪・パーカー・ワンピース・タイツ・靴・看板の大色面配置 (190 elements)
  - Batch 4: 光源設定と大局的な明暗（1影・大きな立体グラデーション面）の構築 (250 elements)
Phase 3: 構造、陰影、細部を段階的に描き込む (Progressive Structure, Shading & Details)
  - Batch 5: 髪房の立体構造・パーカーのシワと袖のボリューム・スカートのフリル・脚の陰影 (330 elements)
  - Batch 6: 顔パーツ（瞳の琥珀グラデ・ハイライト・まつ毛・八重歯・頬の赤み）・ケモ耳・頭の葉っぱ・LGTM看板・鈴とリボンの細部描き込み (340 elements)
Phase 4: 全体を確認し、修正・仕上げを行う (Global Review, Refinement & Final Polish)
  - Batch 7: レンダリング誤差解析に基づくエッジ精密化・2影/反射光・微細ディテール補正 (220 elements)
  - Batch 8: 主線の色トレス仕上げ・天使の輪ハイライト・瞳の輝き・効果線など最終仕上げ (120 elements)

After each batch, renders the current SVG state, computes pixel error against the reference image,
saves the intermediate image & inspection metrics, and uses the current state to guide the next batch.
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


def extract_anatomical_guidelines(arr, fg_mask):
    """
    Create Phase 1 (Batch 1 & Batch 2) human-like rough sketch elements:
    - Batch 1: Construction guidelines (head circle, crosshairs, spine/pelvis/limb gesture curves,
      hand & peace sign guide, LGTM board perspective box, foot grounding ellipse).
    - Batch 2: Refined pencil/ink sketch lines traced along key anatomical edges of the illustration
      (hair silhouette, face contour, eyes, ears, leaf, hoodie folds, dress, legs, shoes, signboard).
    """
    H, W, _ = arr.shape
    batch1_elements = []
    batch2_elements = []

    # --- BATCH 1: Rough Construction & Gesture Lines (アタリ・構図・比率スケッチ) ---
    sketch_blue = "#5b9bd5"
    sketch_cyan = "#4a89dc"
    sketch_red = "#e06666"

    # 1. Ground plane & center of balance vertical plumb line
    batch1_elements.append({
        "tag": "ellipse",
        "attrs": {
            "cx": "455.0", "cy": "1338.0", "rx": "165.0", "ry": "24.0",
            "fill": "none", "stroke": sketch_blue, "stroke-width": "1.8",
            "stroke-dasharray": "8,6", "opacity": "0.55"
        },
        "region": "ground_guide"
    })
    batch1_elements.append({
        "tag": "line",
        "attrs": {
            "x1": "518.0", "y1": "25.0", "x2": "478.0", "y2": "1360.0",
            "stroke": sketch_blue, "stroke-width": "1.5",
            "stroke-dasharray": "10,8", "opacity": "0.45"
        },
        "region": "plumb_line"
    })

    # 2. Head construction sphere & tilted crosshairs (head is slightly tilted right-down)
    batch1_elements.append({
        "tag": "circle",
        "attrs": {
            "cx": "542.0", "cy": "205.0", "r": "108.0",
            "fill": "none", "stroke": sketch_blue, "stroke-width": "2.2", "opacity": "0.65"
        },
        "region": "head_atari"
    })
    # Jawline / chin guide
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M446.0,210.0 Q462.0,305.0 548.0,312.0 Q625.0,295.0 638.0,195.0",
            "fill": "none", "stroke": sketch_blue, "stroke-width": "2.0", "opacity": "0.60"
        },
        "region": "head_atari"
    })
    # Face centerline & eye level guidelines
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M526.0,98.0 Q542.0,212.0 548.0,312.0",
            "fill": "none", "stroke": sketch_red, "stroke-width": "1.8", "opacity": "0.60"
        },
        "region": "face_crosshair"
    })
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M442.0,236.0 Q542.0,232.0 640.0,208.0",
            "fill": "none", "stroke": sketch_red, "stroke-width": "1.8", "opacity": "0.60"
        },
        "region": "face_crosshair"
    })
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M448.0,206.0 Q540.0,200.0 634.0,178.0",
            "fill": "none", "stroke": sketch_red, "stroke-width": "1.4",
            "stroke-dasharray": "5,5", "opacity": "0.50"
        },
        "region": "face_crosshair"
    })

    # 3. Kemonomimi ears & top leaf rough placement
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M395.0,130.0 Q382.0,48.0 452.0,68.0",
            "fill": "none", "stroke": sketch_blue, "stroke-width": "2.0", "opacity": "0.60"
        },
        "region": "ear_left_atari"
    })
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M588.0,62.0 Q658.0,32.0 662.0,115.0",
            "fill": "none", "stroke": sketch_blue, "stroke-width": "2.0", "opacity": "0.60"
        },
        "region": "ear_right_atari"
    })
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M452.0,152.0 Q448.0,65.0 542.0,28.0 Q545.0,105.0 452.0,152.0",
            "fill": "none", "stroke": "#5aa864", "stroke-width": "2.0", "opacity": "0.65"
        },
        "region": "leaf_atari"
    })

    # 4. Torso, ribcage, pelvis & S-curve spine line of action
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M545.0,312.0 Q535.0,460.0 518.0,645.0 Q495.0,880.0 482.0,1260.0",
            "fill": "none", "stroke": sketch_red, "stroke-width": "2.4", "opacity": "0.60"
        },
        "region": "line_of_action"
    })
    # Ribcage & puffy dress volume ellipses
    batch1_elements.append({
        "tag": "ellipse",
        "attrs": {
            "cx": "548.0", "cy": "445.0", "rx": "95.0", "ry": "82.0",
            "transform": "rotate(-6 548 445)",
            "fill": "none", "stroke": sketch_blue, "stroke-width": "1.9", "opacity": "0.55"
        },
        "region": "torso_atari"
    })
    batch1_elements.append({
        "tag": "ellipse",
        "attrs": {
            "cx": "520.0", "cy": "635.0", "rx": "155.0", "ry": "115.0",
            "transform": "rotate(8 520 635)",
            "fill": "none", "stroke": sketch_blue, "stroke-width": "2.0", "opacity": "0.55"
        },
        "region": "hip_dress_atari"
    })

    # 5. Arms, shoulders, joints, hands, and LGTM signboard construction
    # Left arm (viewer's left - doing peace sign)
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M445.0,368.0 Q320.0,455.0 345.0,360.0 Q360.0,305.0 355.0,255.0",
            "fill": "none", "stroke": sketch_cyan, "stroke-width": "2.2", "opacity": "0.60"
        },
        "region": "left_arm_atari"
    })
    # Right arm (viewer's right - holding LGTM sign)
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M635.0,375.0 Q735.0,455.0 875.0,420.0 Q905.0,365.0 895.0,302.0",
            "fill": "none", "stroke": sketch_cyan, "stroke-width": "2.2", "opacity": "0.60"
        },
        "region": "right_arm_atari"
    })
    # Joint circles (shoulders, elbows, wrists, knees, ankles)
    joints = [
        (445, 368, 18), (635, 375, 18), (318, 435, 22), (765, 445, 22),
        (362, 298, 16), (892, 315, 16), (552, 875, 24), (558, 925, 22),
        (385, 925, 20), (482, 1185, 18)
    ]
    for jx, jy, jr in joints:
        batch1_elements.append({
            "tag": "circle",
            "attrs": {
                "cx": f"{jx:.1f}", "cy": f"{jy:.1f}", "r": f"{jr:.1f}",
                "fill": "none", "stroke": sketch_red, "stroke-width": "1.6", "opacity": "0.55"
            },
            "region": "joint_atari"
        })

    # LGTM signboard perspective box & handle axis
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M742.0,136.0 L982.0,62.0 L1024.0,188.0 L784.0,262.0 Z",
            "fill": "none", "stroke": sketch_blue, "stroke-width": "2.2", "opacity": "0.65"
        },
        "region": "signboard_atari"
    })
    batch1_elements.append({
        "tag": "line",
        "attrs": {
            "x1": "862.0", "y1": "99.0", "x2": "915.0", "y2": "372.0",
            "stroke": sketch_red, "stroke-width": "2.0", "stroke-dasharray": "6,4", "opacity": "0.60"
        },
        "region": "signboard_handle_atari"
    })

    # Legs & shoes construction lines (one leg raised to left, one standing leg)
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M478.0,705.0 Q548.0,815.0 552.0,878.0 Q455.0,865.0 385.0,915.0",
            "fill": "none", "stroke": sketch_cyan, "stroke-width": "2.4", "opacity": "0.65"
        },
        "region": "left_leg_atari"
    })
    batch1_elements.append({
        "tag": "path",
        "attrs": {
            "d": "M555.0,735.0 Q568.0,855.0 558.0,935.0 Q522.0,1075.0 482.0,1225.0",
            "fill": "none", "stroke": sketch_cyan, "stroke-width": "2.4", "opacity": "0.65"
        },
        "region": "right_leg_atari"
    })

    # Add anatomical edge-guided rough sketch strokes (completing Batch 1 & Batch 2)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)
    edges = cv2.Canny(blur, 35, 110)
    edges = edges & (fg_mask.astype(np.uint8) * 255)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    # Sort contours by length and y-position (top-to-bottom human drawing order)
    valid_contours = [c for c in contours if cv2.arcLength(c, False) >= 42]
    valid_contours.sort(key=lambda c: -cv2.arcLength(c, False))

    # Top 46 major structural contours go into Batch 1 (as blue/graphite rough construction lines)
    for c in valid_contours[:46]:
        d = contour_to_bezier_svg_path(c, epsilon=2.8, closed=False)
        if not d:
            continue
        pts = c.reshape(-1, 2)
        cy = float(pts[:, 1].mean())
        batch1_elements.append({
            "tag": "path",
            "attrs": {
                "d": d,
                "fill": "none",
                "stroke": "#6d8fb8" if cy < 600 else "#7695ba",
                "stroke-width": "1.6",
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
                "opacity": "0.52"
            },
            "region": "rough_contour",
            "cy": cy
        })

    # Next 98 detailed line contours go into Batch 2 (warm brown/sepia anime rough lineart)
    line_contours = valid_contours[46:144]
    line_contours.sort(key=lambda c: float(c.reshape(-1, 2)[:, 1].mean()))
    for c in line_contours:
        d = contour_to_bezier_svg_path(c, epsilon=1.8, closed=False)
        if not d:
            continue
        pts = c.reshape(-1, 2)
        cy = float(pts[:, 1].mean())
        batch2_elements.append({
            "tag": "path",
            "attrs": {
                "d": d,
                "fill": "none",
                "stroke": "#7a4b47",
                "stroke-width": "1.7",
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
                "opacity": "0.65"
            },
            "region": "rough_lineart",
            "cy": cy
        })

    return batch1_elements, batch2_elements
