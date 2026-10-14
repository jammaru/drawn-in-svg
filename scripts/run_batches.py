#!/usr/bin/env python3
"""
Ultra-Detailed Progressive Batch Execution Pipeline:
- Greatly increases SVG element count (~7,500 - 8,500 elements) for ultra-delicate,
  near-lossless fidelity to the reference illustration.
- Follows the 4 natural human drawing stages across 10 sequential batches:
  Phase 1: ラフスケッチを描き、構図や比率を決める
    - Batch 1: アタリ・構図・頭身比率の決定 (~75 elements)
    - Batch 2: ラフスケッチ・キャラクター輪郭と衣装の描き起こし (~110 elements)
  Phase 2: 大きな色面を配置し、明暗関係を構築する
    - Batch 3: 大きな色面の配置（下塗り・固有色のブロッキング） (~320 elements)
    - Batch 4: 明暗関係の構築（光源設定・1影と立体グラデーション） (~650 elements)
  Phase 3: 構造、陰影、細部を段階的に描き込む
    - Batch 5: 髪房の立体構造・パーカーのシワ・衣装陰影の描き込み (~1,150 elements)
    - Batch 6: 顔・瞳・ケモ耳・葉っぱ・LGTM看板・鈴とリボンの細部描き込み (~1,450 elements)
    - Batch 7: 髪の毛先の繊細な束感・フリル・装飾・グラデーションの緻密化 (~1,500 elements)
  Phase 4: 全体を確認し、修正・仕上げを行う
    - Batch 8: 全体確認・輪郭エッジと2影・反射光の精密補正 (~1,250 elements)
    - Batch 9: 主線の色トレス・まつ毛・瞳の虹彩・文字エッジの極細描き込み (~950 elements)
    - Batch 10: 最終仕上げ・瞳のハイライト・髪のツヤ・微細ディテール完成 (~650 elements)
- After every batch, renders the current SVG canvas via resvg_py and inspects error distribution
  against the reference image to decide the next batch's elements.
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
from scripts.batch_builder import (
    get_foreground_mask,
    get_region_weight_map,
    extract_slic_polygons,
    build_svg_document,
    count_drawable_elements,
)


def extract_constructive_elements(
    ref_arr,
    current_render,
    region_mask,
    weights,
    n_segments,
    compactness,
    max_elements,
    epsilon=0.65,
    dilate_px=1,
    min_area=4,
    max_area=30000,
    min_gain_threshold=0.8,
):
    """
    Segment `region_mask` into `n_segments` superpixels on `ref_arr`.
    For each superpixel, compute exact error reduction over `current_render`.
    Selects elements that genuinely improve the current canvas state.
    """
    H, W, _ = ref_arr.shape
    if region_mask.sum() < min_area:
        return []

    segments = slic(
        ref_arr,
        n_segments=n_segments,
        compactness=compactness,
        sigma=0.35,
        start_label=1,
        mask=region_mask,
        enforce_connectivity=True,
    )

    ref_f = ref_arr.astype(np.float32)
    cur_f = current_render.astype(np.float32)
    cur_err = np.linalg.norm(ref_f - cur_f, axis=2)

    kernel = (
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1))
        if dilate_px > 0
        else None
    )

    candidates = []
    max_lbl = segments.max()
    for lbl in range(1, max_lbl + 1):
        rmask = segments == lbl
        area = int(rmask.sum())
        if area < min_area or area > max_area:
            continue

        mean_rgb = ref_f[rmask].mean(axis=0)
        new_err = np.linalg.norm(ref_f[rmask] - mean_rgb[None, :], axis=1)
        old_err = cur_err[rmask]
        w_vals = weights[rmask]

        mean_improvement = float((old_err - new_err).mean())
        if mean_improvement < min_gain_threshold:
            continue

        total_weighted_gain = float(((old_err - new_err) * w_vals).sum()) / (area ** 0.30)

        m_u8 = rmask.astype(np.uint8) * 255
        if kernel is not None:
            m_u8 = cv2.dilate(m_u8, kernel, iterations=1)
        contours, _ = cv2.findContours(m_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            continue
        c = max(contours, key=cv2.contourArea)
        d = contour_to_bezier_svg_path(c, epsilon=epsilon, closed=True)
        if not d:
            continue

        ys, xs = np.where(rmask)
        cx, cy = float(xs.mean()), float(ys.mean())
        color_hex = rgb_to_hex(mean_rgb)

        candidates.append({
            "gain": total_weighted_gain,
            "el": {
                "tag": "path",
                "attrs": {"d": d, "fill": color_hex},
                "cx": round(cx, 1),
                "cy": round(cy, 1),
                "area": area,
            },
        })

    candidates.sort(key=lambda x: -x["gain"])
    selected = [x["el"] for x in candidates[:max_elements]]
    # Sort larger shapes before smaller ones, and top-to-bottom within similar sizes
    selected.sort(key=lambda el: (-el["area"] // 120, el["cy"] // 120))
    return selected


def extract_fine_spot_refinements(
    ref_arr,
    current_render,
    fg_mask,
    weights,
    max_elements,
    diff_thresh=10.0,
    min_area=2,
    max_area=600,
    epsilon=0.42,
    dilate_px=0,
):
    """
    Extract delicate high-contrast features (eyelashes, iris gradients, eye catchlights,
    fang, blush, bell highlights, fine hair strands, LGTM text edges, color-tinted lineart)
    where `current_render` still differs from `ref_arr`.
    """
    ref_f = ref_arr.astype(np.float32)
    cur_f = current_render.astype(np.float32)
    diff = np.linalg.norm(ref_f - cur_f, axis=2)

    spot_mask = (diff > diff_thresh) & fg_mask
    num_l, labels, stats, centroids = cv2.connectedComponentsWithStats(spot_mask.astype(np.uint8))

    kernel = (
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1))
        if dilate_px > 0
        else None
    )

    candidates = []
    for lbl in range(1, num_l):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        rmask = labels == lbl

        # If a connected component is large (> max_area), sub-partition it with SLIC so it doesn't average across edges
        if area > max_area and area < 6000:
            n_sub = max(2, min(25, area // 90))
            sub_segs = slic(
                ref_arr,
                n_segments=n_sub,
                compactness=4.5,
                sigma=0.3,
                start_label=1,
                mask=rmask,
                enforce_connectivity=True,
            )
            sub_masks = [sub_segs == s_i for s_i in range(1, sub_segs.max() + 1)]
        elif area <= max_area:
            sub_masks = [rmask]
        else:
            continue

        for smask in sub_masks:
            s_area = int(smask.sum())
            if s_area < min_area:
                continue
            mean_rgb = ref_f[smask].mean(axis=0)
            new_err = np.linalg.norm(ref_f[smask] - mean_rgb[None, :], axis=1)
            old_err = diff[smask]
            improvement = float((old_err - new_err).mean())
            if improvement < 2.2:
                continue

            w_score = float(((old_err - new_err) * weights[smask]).sum()) / (s_area ** 0.25)
            m_u8 = smask.astype(np.uint8) * 255
            if kernel is not None:
                m_u8 = cv2.dilate(m_u8, kernel, iterations=1)
            contours, _ = cv2.findContours(m_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not contours:
                continue
            c = max(contours, key=cv2.contourArea)
            d = contour_to_bezier_svg_path(c, epsilon=epsilon, closed=True)
            if not d:
                continue

            ys, xs = np.where(smask)
            cx, cy = float(xs.mean()), float(ys.mean())
            candidates.append({
                "score": w_score,
                "el": {
                    "tag": "path",
                    "attrs": {"d": d, "fill": rgb_to_hex(mean_rgb)},
                    "cx": round(cx, 1),
                    "cy": round(cy, 1),
                    "area": s_area,
                },
            })

    candidates.sort(key=lambda x: -x["score"])
    selected = [x["el"] for x in candidates[:max_elements]]
    selected.sort(key=lambda el: (-el["area"] // 40, el["cy"] // 120))
    return selected


def run_progressive_pipeline():
    img = Image.open(REF_PATH).convert("RGB")
    ref_arr = np.array(img)
    H, W, _ = ref_arr.shape
    bg_hex = rgb_to_hex(ref_arr[0, 0])

    fg_mask = get_foreground_mask(ref_arr)
    weights = get_region_weight_map(H, W, fg_mask)

    # Clear old batch files
    for fname in os.listdir(BATCH_DIR):
        if fname.startswith("batch_"):
            os.remove(os.path.join(BATCH_DIR, fname))

    batches = []
    batch_metrics = []

    def evaluate_and_save_batch(batch_num, total_batches, phase_num, phase_name, batch_title, description, sketch_fade=1.0):
        for b in batches:
            if b["id"] in ("batch-1-rough-atari", "batch-2-rough-lineart"):
                b["group_opacity"] = sketch_fade

        svg_str = build_svg_document(W, H, bg_hex, batches)
        rendered = render_svg_to_rgb(svg_str, W, H)

        svg_path = os.path.join(BATCH_DIR, f"batch_{batch_num:02d}.svg")
        png_path = os.path.join(BATCH_DIR, f"batch_{batch_num:02d}.png")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_str)
        Image.fromarray(rendered).save(png_path)

        diff = np.abs(ref_arr.astype(np.float32) - rendered.astype(np.float32))
        mae_all = float(diff.mean())
        mae_fg = float(diff[fg_mask].mean())
        mse_all = float((diff ** 2).mean())
        psnr = 10.0 * math.log10((255.0 ** 2) / max(mse_all, 1e-6))
        total_els = count_drawable_elements(batches)
        batch_els = len(batches[-1]["elements"])

        info = {
            "batch": batch_num,
            "phase": phase_num,
            "phase_name": phase_name,
            "title": batch_title,
            "description": description,
            "batch_elements": batch_els,
            "cumulative_elements": total_els,
            "mae_all": round(mae_all, 2),
            "mae_fg": round(mae_fg, 2),
            "psnr_db": round(psnr, 2),
            "svg_path": svg_path,
            "png_path": png_path,
        }
        batch_metrics.append(info)
        print(
            f"[Batch {batch_num}/{total_batches} | Phase {phase_num}] {batch_title}: "
            f"+{batch_els} els (total {total_els}) | FG MAE={mae_fg:.2f} | PSNR={psnr:.2f} dB"
        )
        return rendered

    total_batches = 10

    # =========================================================================
    # PHASE 1: ラフスケッチを描き、構図や比率を決める
    # =========================================================================
    b1_els, b2_els = extract_anatomical_guidelines(ref_arr, fg_mask)

    batches.append({
        "id": "batch-1-rough-atari",
        "phase": 1,
        "title": "1-1. アタリ・構図・頭身比率の決定",
        "elements": b1_els,
        "group_opacity": 0.90,
    })
    render_b1 = evaluate_and_save_batch(
        1, total_batches, 1,
        "1. ラフスケッチを描き、構図や比率を決める",
        "1-1. アタリ・構図・頭身比率の決定",
        "頭部の球体と十字線、S字の重心ライン、関節位置、ピースサインの左手とLGTM看板のパース枠を描き、全身のバランスを決めます。",
        sketch_fade=0.90,
    )

    batches.append({
        "id": "batch-2-rough-lineart",
        "phase": 1,
        "title": "1-2. ラフスケッチ・キャラクター輪郭と衣装の描き起こし",
        "elements": b2_els,
        "group_opacity": 0.85,
    })
    render_b2 = evaluate_and_save_batch(
        2, total_batches, 1,
        "1. ラフスケッチを描き、構図や比率を決める",
        "1-2. ラフスケッチ・キャラクター輪郭と衣装の描き起こし",
        "アタリの上に、ケモ耳や葉っぱ、ツイン風の後れ毛、ゆったりした赤パーカー、バルーン裾の白ワンピース、ニーソックスとブーツのラフ線画を描き起こします。",
        sketch_fade=0.85,
    )

    # =========================================================================
    # PHASE 2: 大きな色面を配置し、明暗関係を構築する
    # =========================================================================
    # Batch 3: Large Base Color Flats (大色面・ベースカラーの配置)
    b3_raw = extract_slic_polygons(
        ref_arr, fg_mask, n_segments=320, compactness=7.0, epsilon=1.2, dilate_px=2, min_area=30
    )
    fg_u8 = fg_mask.astype(np.uint8) * 255
    contours_sil, _ = cv2.findContours(fg_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    sil_els = []
    for c in sorted(contours_sil, key=cv2.contourArea, reverse=True)[:8]:
        if cv2.contourArea(c) < 90:
            continue
        d = contour_to_bezier_svg_path(c, epsilon=1.1, closed=True)
        if d:
            mask_c = np.zeros((H, W), dtype=np.uint8)
            cv2.drawContours(mask_c, [c], -1, 1, thickness=-1)
            mean_c = ref_arr[mask_c == 1].mean(axis=0)
            sil_els.append({
                "tag": "path",
                "attrs": {"d": d, "fill": rgb_to_hex(mean_c)},
                "cx": 550.0, "cy": 700.0, "area": int(cv2.contourArea(c))
            })

    b3_raw_sorted = sorted(b3_raw, key=lambda el: (el["cy"] // 200, -el["area"]))
    b3_els = sil_els + b3_raw_sorted[:300]
    batches.append({
        "id": "batch-3-base-color-flats",
        "phase": 2,
        "title": "2-1. 大きな色面の配置（下塗り・固有色のブロッキング）",
        "elements": b3_els,
        "group_opacity": 1.0,
    })
    render_b3 = evaluate_and_save_batch(
        3, total_batches, 2,
        "2. 大きな色面を配置し、明暗関係を構築する",
        "2-1. 大きな色面の配置（下塗り・固有色のブロッキング）",
        "ラフ線画の透明度を下げ、コーラルピンクの髪、明るい肌、朱赤のパーカー、クリーム白のワンピース、グリーンの葉っぱとLGTM看板の大きな固有色面を配置します。",
        sketch_fade=0.25,
    )

    # Batch 4: Value Structure & Primary Light/Shadow Planes (明暗関係の構築・1影と大局的立体感)
    b4_els = extract_constructive_elements(
        ref_arr, render_b3, fg_mask, weights,
        n_segments=950, compactness=6.0, max_elements=650,
        epsilon=0.95, dilate_px=1, min_area=14, min_gain_threshold=1.0
    )
    batches.append({
        "id": "batch-4-value-structure",
        "phase": 2,
        "title": "2-2. 明暗関係の構築（光源設定・1影と立体グラデーション）",
        "elements": b4_els,
        "group_opacity": 1.0,
    })
    render_b4 = evaluate_and_save_batch(
        4, total_batches, 2,
        "2. 大きな色面を配置し、明暗関係を構築する",
        "2-2. 明暗関係の構築（光源設定・1影と立体グラデーション）",
        "左上からの主光源に基づき、後頭部や首元の落ち影、パーカーの大きな膨らみと陰影、ワンピース裾の丸み、脚の立体感を決める明暗面を構築します。",
        sketch_fade=0.12,
    )

    # =========================================================================
    # PHASE 3: 構造、陰影、細部を段階的に描き込む
    # =========================================================================
    # Batch 5: Hair Strands, Sleeve Folds & Clothing Shading (髪房の立体構造・パーカーのシワ・衣装陰影)
    b5_els = extract_constructive_elements(
        ref_arr, render_b4, fg_mask, weights,
        n_segments=2400, compactness=5.2, max_elements=1150,
        epsilon=0.75, dilate_px=1, min_area=8, min_gain_threshold=0.9
    )
    batches.append({
        "id": "batch-5-structure-and-shading",
        "phase": 3,
        "title": "3-1. 髪房の立体構造・パーカーのシワ・衣装陰影の描き込み",
        "elements": b5_els,
        "group_opacity": 1.0,
    })
    render_b5 = evaluate_and_save_batch(
        5, total_batches, 3,
        "3. 構造、陰影、細部を段階的に描き込む",
        "3-1. 髪房の立体構造・パーカーのシワ・衣装陰影の描き込み",
        "前髪・サイドの髪房の重なり、パーカー袖の深いシワ、バルーンスカートのギャザーとフリル、ニーソックスの膝裏の陰影を段階的に描き込みます。",
        sketch_fade=0.06,
    )

    # Batch 6: Facial Features, Eyes, Leaf, LGTM Signboard & Ornaments (瞳・表情・LGTM看板・鈴とリボンの細部)
    detail_zone_mask = np.zeros((H, W), dtype=bool)
    detail_zone_mask[15:410, 280:1040] = True   # Head, face, eyes, ears, leaf, peace hand, LGTM board
    detail_zone_mask[330:745, 340:710] = True   # Chest ribbon/bells, waist pockets/bells, pom-poms
    detail_zone_mask[810:1385, 290:590] = True  # Knee ribbon, boots, boot bells & pom-poms
    detail_zone_mask &= fg_mask

    b6_slic = extract_constructive_elements(
        ref_arr, render_b5, detail_zone_mask, weights * 1.5,
        n_segments=4200, compactness=4.6, max_elements=1050,
        epsilon=0.58, dilate_px=1, min_area=4, min_gain_threshold=0.8
    )
    b6_spots = extract_fine_spot_refinements(
        ref_arr, render_b5, detail_zone_mask, weights * 1.8,
        max_elements=450, diff_thresh=14.0, min_area=3, max_area=480, epsilon=0.45, dilate_px=0
    )
    b6_els = b6_slic + b6_spots
    batches.append({
        "id": "batch-6-facial-and-key-details",
        "phase": 3,
        "title": "3-2. 瞳・表情・LGTM看板・鈴とリボンなど細部の描き込み",
        "elements": b6_els,
        "group_opacity": 1.0,
    })
    render_b6 = evaluate_and_save_batch(
        6, total_batches, 3,
        "3. 構造、陰影、細部を段階的に描き込む",
        "3-2. 瞳・表情・LGTM看板・鈴とリボンなど細部の描き込み",
        "琥珀色の瞳のグラデーションとハイライト、笑顔の口元と小さな八重歯、胸元や靴の金の鈴・赤いリボン・白いポンポン、LGTM看板の文字と枠を精密に描き込みます。",
        sketch_fade=0.03,
    )

    # Batch 7: Delicate Hair Locks, Frills, Soft Gradients & Secondary Details (毛先の繊細な束感・フリル・緻密な陰影)
    b7_els = extract_constructive_elements(
        ref_arr, render_b6, fg_mask, weights * 1.2,
        n_segments=5800, compactness=4.4, max_elements=1450,
        epsilon=0.55, dilate_px=1, min_area=4, min_gain_threshold=0.8
    )
    batches.append({
        "id": "batch-7-delicate-textures-and-frills",
        "phase": 3,
        "title": "3-3. 髪の繊細な毛束・フリル・中間調グラデーションの緻密化",
        "elements": b7_els,
        "group_opacity": 1.0,
    })
    render_b7 = evaluate_and_save_batch(
        7, total_batches, 3,
        "3. 構造、陰影、細部を段階的に描き込む",
        "3-3. 髪の繊細な毛束・フリル・中間調グラデーションの緻密化",
        "髪の細かい毛束の流れや後れ毛、パーカーやワンピースの柔らかな中間調グラデーション、フリルや靴紐の立体感を緻密に描き込みます。",
        sketch_fade=0.01,
    )

    # =========================================================================
    # PHASE 4: 全体を確認し、修正・仕上げを行う
    # =========================================================================
    # Batch 8: Global Inspection & Edge/Shading Refinement (全体確認・輪郭エッジと2影・反射光の精密修正)
    b8_slic = extract_constructive_elements(
        ref_arr, render_b7, fg_mask, weights * 1.3,
        n_segments=8500, compactness=4.0, max_elements=900,
        epsilon=0.48, dilate_px=0, min_area=3, min_gain_threshold=0.8
    )
    b8_spots = extract_fine_spot_refinements(
        ref_arr, render_b7, fg_mask, weights * 1.5,
        max_elements=450, diff_thresh=11.0, min_area=2, max_area=350, epsilon=0.42, dilate_px=0
    )
    b8_els = b8_slic + b8_spots
    batches.append({
        "id": "batch-8-global-refinement",
        "phase": 4,
        "title": "4-1. 全体確認・輪郭エッジと微細陰影の精密修正",
        "elements": b8_els,
        "group_opacity": 1.0,
    })
    render_b8 = evaluate_and_save_batch(
        8, total_batches, 4,
        "4. 全体を確認し、修正・仕上げを行う",
        "4-1. 全体確認・輪郭エッジと微細陰影の精密修正",
        "現在の描画状態を全体確認し、境界のわずかなズレや2影・反射光、指先や文字のエッジ、足元の接地影を精密に修正します。",
        sketch_fade=0.005,
    )

    # Batch 9: Ultra-Fine Lineart, Eyelashes, Iris Detail & Signboard Crispness (色トレス主線・まつ毛・虹彩・極細ディテール)
    b9_spots = extract_fine_spot_refinements(
        ref_arr, render_b8, fg_mask, weights * 2.0,
        max_elements=1100, diff_thresh=8.5, min_area=2, max_area=240, epsilon=0.38, dilate_px=0
    )
    batches.append({
        "id": "batch-9-fine-lineart-and-eyes",
        "phase": 4,
        "title": "4-2. 色トレス主線・まつ毛・瞳の虹彩・文字輪郭の極細描き込み",
        "elements": b9_spots,
        "group_opacity": 1.0,
    })
    render_b9 = evaluate_and_save_batch(
        9, total_batches, 4,
        "4. 全体を確認し、修正・仕上げを行う",
        "4-2. 色トレス主線・まつ毛・瞳の虹彩・文字輪郭の極細描き込み",
        "瞳の繊細な虹彩とまつ毛、口元の八重歯、鈴の金属光沢、LGTM文字のシャープな輪郭、全身の色トレス主線を極細パスで描き込みます。",
        sketch_fade=0.0,
    )

    # Batch 10: Final Polish, Specular Catchlights, Hair Shine & Micro-Accents (最終仕上げ・ハイライト・極小ディテール完成)
    b10_spots = extract_fine_spot_refinements(
        ref_arr, render_b9, fg_mask, weights * 2.5,
        max_elements=850, diff_thresh=6.5, min_area=1, max_area=150, epsilon=0.35, dilate_px=0
    )
    batches.append({
        "id": "batch-10-final-polish",
        "phase": 4,
        "title": "4-3. 最終仕上げ・瞳の輝き・髪のツヤ・微細アクセント完成",
        "elements": b10_spots,
        "group_opacity": 1.0,
    })
    render_b10 = evaluate_and_save_batch(
        10, total_batches, 4,
        "4. 全体を確認し、修正・仕上げを行う",
        "4-3. 最終仕上げ・瞳の輝き・髪のツヤ・微細アクセント完成",
        "瞳のハイライト、髪の天使の輪、頬のチーク、LGTM看板のきらめき、極小の色面補正を施して超高精細SVGを完成させます。",
        sketch_fade=0.0,
    )

    final_svg_str = build_svg_document(W, H, bg_hex, batches)
    final_svg_path = os.path.join(OUT_DIR, "lgtm_character_final.svg")
    final_png_path = os.path.join(OUT_DIR, "lgtm_character_final.png")
    with open(final_svg_path, "w", encoding="utf-8") as f:
        f.write(final_svg_str)
    Image.fromarray(render_b10).save(final_png_path)

    total_elements = count_drawable_elements(batches)
    summary = {
        "width": W,
        "height": H,
        "bg_hex": bg_hex,
        "total_drawable_elements": total_elements,
        "final_svg_path": final_svg_path,
        "final_png_path": final_png_path,
        "batches": batch_metrics,
    }
    with open(os.path.join(OUT_DIR, "drawing_process_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT_DIR, "batches_data.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "width": W,
                "height": H,
                "bg_hex": bg_hex,
                "total_elements": total_elements,
                "batches": batches,
                "metrics": batch_metrics,
            },
            f,
            ensure_ascii=False,
        )

    print(f"\n=== COMPLETED ALL {total_batches} BATCHES ===")
    print(f"Total drawable SVG elements: {total_elements:,}")
    print(f"Final SVG saved to: {final_svg_path}")
    return summary


if __name__ == "__main__":
    run_progressive_pipeline()
