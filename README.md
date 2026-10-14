# An illustration, drawn in SVG from rough sketch to finish

I made all of this with Gemini 4 Argon: the SVG, the scripts that build it batch by batch, the comparison video, and the viewer. Paths are stacked the way a person draws: rough construction, flat color, shading, then the finish. The lines and the color are SVG elements. The clip below is that SVG being drawn, next to the original.

Left is the source illustration. Right is the SVG.

![Left: the original illustration. Right: the same picture drawn as SVG, from the rough construction through the finish.](output/drawing_process_full.gif)

The finished SVG has **7,554** drawing elements on a 1122×1402 canvas. The rough construction lines stay in the file. In the final state their opacity is 0.

The GIF is a smaller loop of the comparison. The full-size files are [`output/drawing_process_full.mp4`](output/drawing_process_full.mp4) and [`output/drawing_process_full.webm`](output/drawing_process_full.webm).

## Prompt

This is the prompt I used. The reference illustration was attached.

```text
添付した参考画像をできる限り忠実かつ繊細なSVGとして再現し、元画像と描画過程を左右比較する動画も作成してください。

【描画プロセス】
人間が絵を描く自然な制作過程を再現すること：
1. ラフスケッチを描き、構図や比率を決める。
2. 大きな色面を配置し、明暗関係を構築する。
3. 構造、陰影、細部を段階的に描き込む。
4. 全体を確認し、修正・仕上げを行う。

【描画方法】
すべてを一度に描くのではなく、現在の描画状態を確認しながら、次に描く部分をバッチ単位で判断・追加して段階的に完成度を高めてください。要素数は増やしてできるだけ繊細にし、完成したSVGファイルと描画工程の比較動画を出力してください。
```

In English: reproduce the attached reference as a faithful, delicate SVG, and make a side-by-side video of the original and the drawing. Follow the way a person draws — rough sketch and proportion, large areas of color and light, then structure, shading, and detail, then a full check and finish. Do not draw it all at once. Look at the current state, choose the next part in batches, and raise the element count so the result is as delicate as possible. Output the finished SVG and the comparison video.

## The SVG

GitHub shows an SVG file as a still image, and the CSS animation does not run there. Save the file and open it in a browser to watch it draw.

- Animated SVG, about 24 seconds: [`output/lgtm_character_animated.svg`](output/lgtm_character_animated.svg) (2.9 MB)
- Finished SVG: [`output/lgtm_character_final.svg`](output/lgtm_character_final.svg) (2.6 MB)

To scrub element by element, compare against the original with a slider, or jump to a batch:

```bash
npm install
npm run dev
```

Open http://127.0.0.1:43123. The files in `public/` are the same set as `output/`, served by the viewer.

## What the SVG is

`output/lgtm_character_final.svg` is one file. A background rectangle, then ten groups. Each group is one batch, and a later group is painted on top of the earlier ones. Nothing underneath is deleted.

```text
svg
  rect                          canvas, #fcfbf8
  g#batch-1-rough-atari        construction marks
  g#batch-2-rough-lineart      rough contour lines
  g#batch-3 … g#batch-10       filled color patches, finer each time
```

Each `g` has a `data-title` with the name of that stage. Batches 1 and 2 are strokes: circles, ellipses, straight lines, and open paths with `fill="none"`. They are the head sphere, crosshairs, joints, the sign's box, and contour lines taken from the edges of the illustration. Their opacity is lowered as the color arrives. In the finished file it is 0, so the lines are still in the source and do not show.

From batch 3 on, every element is a closed path with one flat `fill`. There is no SVG gradient, filter, embedded image, or `<text>` element. The letters on the LGTM sign are paths too. Batches 3, 4, 5, and 7 are quadratic Bézier outlines only (`Q`). Batches 6, 8, 9, and 10 also contain straight segments (`L`), where a small outline simplified down to a few corners.

## How it was made

Gemini 4 Argon wrote the pipeline and ran it. The file was not written in one pass. `scripts/run_batches.py` adds one group at a time. The comparison video is those partial SVGs, rendered in order. `lgtm_character_animated.svg` is the same groups, revealed with CSS.

1. Batches 1 and 2 do not look at the difference from the original. Batch 1 is the construction drawing: head sphere, crosshairs, joints, the sign's box. Batch 2 is open contour lines taken from the edges of the illustration.
2. Batch 3 splits the foreground with SLIC and lays down large flat colors. The broad silhouette goes down first, then the other patches from the top of the picture downward. It does not drop a patch because the error failed to improve.
3. From batch 4, a patch is kept only when painting it in its average color reduces the difference from the original. Batches 4, 5, and 7 do this over the whole figure. Batches 6 and 8 do it again with extra weight on the face, the sign, the bells, and the ribbons, then add small spots that still disagree.
4. Batches 9 and 10 are not another SLIC pass. They take only the small spots that still differ: eyelashes, the iris, letter edges, catchlights.
5. After every batch, including the first three, the render is scored against the original. Those scores are in `output/drawing_process_metadata.json`. The score is a record. It starts choosing the next patches at batch 4.

## Drawing order

Four stages, ten batches, in the order a person would draw. The counts are elements added in that batch, and the running total at the end of it. The running total includes one canvas background rectangle, so batch 1 adds 75 elements and the total is 76. Each stage is saved as `output/batches/batch_01.svg` through `batch_10.svg`.

### 1. Rough sketch: composition and proportion

<p>
  <img src="output/batches/batch_01.png" width="220" alt="Batch 1. Head sphere, crosshairs, center of gravity, joints, and the sign's perspective.">
  <img src="output/batches/batch_02.png" width="220" alt="Batch 2. Rough lines for the ears, leaf, hoodie, dress, and shoes.">
</p>

| Batch | What gets drawn | Added | Total |
| --- | --- | ---: | ---: |
| 1 | Construction: head sphere, crosshairs, center of gravity, joints, sign perspective | 75 | 76 |
| 2 | Rough lines for the ears, leaf, hoodie, dress, and shoes | 98 | 174 |

### 2. Big color shapes, then light and shadow

<p>
  <img src="output/batches/batch_03.png" width="220" alt="Batch 3. Large flat colors for hair, skin, hoodie, dress, and the sign.">
  <img src="output/batches/batch_04.png" width="220" alt="Batch 4. Shadow and volume from a light at the upper left.">
</p>

| Batch | What gets drawn | Added | Total |
| --- | --- | ---: | ---: |
| 3 | Flat color for the hair, skin, red hoodie, white dress, and sign. The rough lines fade | 246 | 420 |
| 4 | Light from the upper left: cast shadow, the hoodie's volume, the legs | 519 | 939 |

### 3. Structure, shading, and detail

<p>
  <img src="output/batches/batch_05.png" width="200" alt="Batch 5. Hair overlap, hoodie folds, and skirt gathers.">
  <img src="output/batches/batch_06.png" width="200" alt="Batch 6. Eyes, mouth, bells, ribbons, and the LGTM lettering.">
  <img src="output/batches/batch_07.png" width="200" alt="Batch 7. Hair strands, frills, and midtones.">
</p>

| Batch | What gets drawn | Added | Total |
| --- | --- | ---: | ---: |
| 5 | Hair overlap, hoodie folds, skirt gathers, knee-sock shading | 1,062 | 2,001 |
| 6 | Eyes, mouth, bells, ribbons, pompoms, the LGTM letters and frame | 1,383 | 3,384 |
| 7 | Hair strands, frills, and midtones built by stacking flat patches | 1,450 | 4,834 |

### 4. Check the whole picture, then finish

<p>
  <img src="output/batches/batch_08.png" width="200" alt="Batch 8. Corrected edges, second shadow, and the contact shadow under the feet.">
  <img src="output/batches/batch_09.png" width="200" alt="Batch 9. Eyelashes, iris, and colored line art.">
  <img src="output/batches/batch_10.png" width="200" alt="Batch 10. Finished highlights, hair shine, and sparkles on the sign.">
</p>

| Batch | What gets drawn | Added | Total |
| --- | --- | ---: | ---: |
| 8 | Edges, second shadow, reflected light, fingertips, letter edges, contact shadow | 1,350 | 6,184 |
| 9 | Eyelashes, iris, bell highlights, LGTM outlines, colored line art | 702 | 6,886 |
| 10 | Eye highlights, hair shine, blush, sparkles on the sign | 668 | 7,554 |

Element counts and the difference from the original (MAE / PSNR) are in [`output/drawing_process_metadata.json`](output/drawing_process_metadata.json).

## Files

| Path | What it is |
| --- | --- |
| `output/drawing_process_full.gif` | Comparison loop used above. Left: original. Right: SVG being drawn |
| `output/drawing_process_full.mp4` | Same comparison, full size |
| `output/drawing_process_full.webm` | Same comparison, WebM |
| `output/lgtm_character_final.svg` | Finished SVG, including the rough-sketch layers |
| `output/lgtm_character_animated.svg` | The same elements, revealed over about 24 seconds with CSS |
| `output/lgtm_character_final.png` | Raster export of the finished SVG |
| `output/batches/batch_01.svg` … `batch_10.svg` | SVG and PNG at the end of each batch |
| `public/` | The same files, served by the viewer |
| `assets/` | The original illustration |

## License

[MIT](LICENSE). Copyright (c) 2026 jammaru.
