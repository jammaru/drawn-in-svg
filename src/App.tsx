import React, { useEffect, useState, useMemo, useRef } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Download,
  Layers,
  Film,
  Sparkles,
  CheckCircle2,
  Eye,
  Sliders,
  ChevronRight,
} from 'lucide-react';

interface SvgElementItem {
  tag: string;
  attrs: Record<string, string>;
  cx?: number;
  cy?: number;
  area?: number;
}

interface BatchGroup {
  id: string;
  phase: number;
  title: string;
  elements: SvgElementItem[];
  group_opacity: number;
}

interface BatchMetric {
  batch: number;
  phase: number;
  phase_name: string;
  title: string;
  description: string;
  batch_elements: number;
  cumulative_elements: number;
  mae_all: number;
  mae_fg: number;
  psnr_db: number;
}

interface BatchesData {
  width: number;
  height: number;
  bg_hex: string;
  total_elements: number;
  batches: BatchGroup[];
  metrics: BatchMetric[];
}

const SKETCH_OPACITIES = [0.9, 0.85, 0.25, 0.12, 0.06, 0.03, 0.01, 0.005, 0.0, 0.0];

export default function App() {
  const [data, setData] = useState<BatchesData | null>(null);
  const [activeTab, setActiveTab] = useState<'video' | 'interactive' | 'compare' | 'batches'>('video');
  const [currentElementStep, setCurrentElementStep] = useState<number>(7554);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(32);
  const [compareSplit, setCompareSplit] = useState<number>(50);
  const [showReferenceOverlay, setShowReferenceOverlay] = useState<boolean>(false);
  const animRef = useRef<number | null>(null);

  useEffect(() => {
    fetch('/batches_data.json')
      .then((r) => r.json())
      .then((json: BatchesData) => {
        setData(json);
        setCurrentElementStep(json.total_elements);
      })
      .catch((err) => console.error('Failed to load batches_data.json:', err));
  }, []);

  useEffect(() => {
    if (!isPlaying || !data) return;
    let lastTime = performance.now();
    const tick = (now: number) => {
      const dt = now - lastTime;
      if (dt >= 16) {
        lastTime = now;
        setCurrentElementStep((prev) => {
          const next = prev + playbackSpeed;
          if (next >= data.total_elements) {
            setIsPlaying(false);
            return data.total_elements;
          }
          return next;
        });
      }
      animRef.current = requestAnimationFrame(tick);
    };
    animRef.current = requestAnimationFrame(tick);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isPlaying, playbackSpeed, data]);

  const activeBatchInfo = useMemo(() => {
    if (!data) return null;
    for (let i = 0; i < data.metrics.length; i++) {
      if (currentElementStep <= data.metrics[i].cumulative_elements) {
        return { index: i, metric: data.metrics[i] };
      }
    }
    return { index: data.metrics.length - 1, metric: data.metrics[data.metrics.length - 1] };
  }, [data, currentElementStep]);

  const currentSketchOpacity = useMemo(() => {
    if (!activeBatchInfo) return 0.0;
    return SKETCH_OPACITIES[activeBatchInfo.index] ?? 0.0;
  }, [activeBatchInfo]);

  const selectBatchStep = (batchIdx: number) => {
    if (!data) return;
    setIsPlaying(false);
    setCurrentElementStep(data.metrics[batchIdx].cumulative_elements);
  };

  const handleRestartPlay = () => {
    setCurrentElementStep(1);
    setIsPlaying(true);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                An illustration, drawn in SVG
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  {data ? data.total_elements.toLocaleString() : '7,554'} SVG elements (10 batches)
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Paths stacked from the rough sketch to the finish. The video and the picture are the same elements.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <a
              href="/lgtm_character_final.svg"
              download="lgtm_character_final.svg"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white transition"
            >
              <Download className="w-3.5 h-3.5" />
              Download finished SVG (7,554 elements)
            </a>
            <a
              href="/drawing_process_full.mp4"
              download="drawing_process_full.mp4"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition"
            >
              <Film className="w-3.5 h-3.5" />
              Comparison video (MP4)
            </a>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4 flex gap-2 border-t border-slate-800/70 pt-2 pb-2 overflow-x-auto">
          <button
            onClick={() => setActiveTab('video')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeTab === 'video'
                ? 'bg-rose-500 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            Comparison video (MP4)
          </button>
          <button
            onClick={() => setActiveTab('interactive')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeTab === 'interactive'
                ? 'bg-rose-500 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            Play the SVG (1–7,554 elements)
          </button>
          <button
            onClick={() => setActiveTab('compare')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeTab === 'compare'
                ? 'bg-rose-500 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            Original vs finished SVG
          </button>
          <button
            onClick={() => setActiveTab('batches')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeTab === 'batches'
                ? 'bg-rose-500 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            All 10 batches
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        {activeTab === 'video' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h2 className="text-base font-bold text-white">
                    Original (left) and the SVG being drawn (right)
                  </h2>
                  <p className="text-xs text-slate-400">
                    The original illustration is on the left. The right side is the SVG, from the rough construction through all 7,554 elements.
                  </p>
                </div>
                <a
                  href="/drawing_process_full.mp4"
                  download="drawing_process_full.mp4"
                  className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  Save MP4
                </a>
              </div>
              <video
                src="/drawing_process_full.mp4"
                controls
                autoPlay
                loop
                playsInline
                className="w-full rounded-xl border border-slate-800 bg-white"
              />
            </div>

            <div className="lg:col-span-4 bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h2 className="text-sm font-bold text-white">
                    Canvas only (drawing_process_canvas.mp4)
                  </h2>
                  <p className="text-[11px] text-slate-400">Timelapse of the drawing canvas alone</p>
                </div>
                <a
                  href="/drawing_process_canvas.mp4"
                  download="drawing_process_canvas.mp4"
                  className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1"
                >
                  <Download className="w-3 h-3" />
                  Save
                </a>
              </div>
              <video
                src="/drawing_process_canvas.mp4"
                controls
                autoPlay
                loop
                muted
                playsInline
                className="w-full rounded-xl border border-slate-800 bg-white"
              />
            </div>
          </div>
        )}

        {activeTab === 'interactive' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left/Center Live SVG Viewport */}
            <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col items-center shadow-xl">
              <div className="w-full flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-rose-500/20 text-rose-300 border border-rose-500/30">
                    Live SVG canvas
                  </span>
                  {activeBatchInfo && (
                    <span className="text-xs text-slate-300 font-medium">
                      {activeBatchInfo.metric.title}
                    </span>
                  )}
                </div>
                <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={showReferenceOverlay}
                    onChange={(e) => setShowReferenceOverlay(e.target.checked)}
                    className="rounded border-slate-700 bg-slate-800 text-rose-500"
                  />
                  Fade the original over the SVG
                </label>
              </div>

              <div className="relative w-full max-w-[520px] aspect-[1122/1402] rounded-xl overflow-hidden border border-slate-700 shadow-inner bg-[#fcfbf8]">
                {data ? (
                  <svg
                    viewBox={`0 0 ${data.width} ${data.height}`}
                    className="w-full h-full block"
                  >
                    <rect width={data.width} height={data.height} fill={data.bg_hex} />
                    {(() => {
                      let remaining = currentElementStep - 1;
                      return data.batches.map((b) => {
                        if (remaining <= 0) return null;
                        const countInBatch = Math.min(b.elements.length, remaining);
                        remaining -= countInBatch;
                        const isSketch =
                          b.id === 'batch-1-rough-atari' || b.id === 'batch-2-rough-lineart';
                        const op = isSketch ? currentSketchOpacity : 1.0;
                        if (isSketch && op <= 0.001) return null;
                        return (
                          <g key={b.id} id={b.id} opacity={op}>
                            {b.elements.slice(0, countInBatch).map((el, idx) => {
                              const Tag = el.tag as any;
                              return <Tag key={idx} {...el.attrs} />;
                            })}
                          </g>
                        );
                      });
                    })()}
                  </svg>
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-600 text-sm">
                    Loading SVG data...
                  </div>
                )}

                {showReferenceOverlay && (
                  <img
                    src="/reference.png"
                    alt="Reference overlay"
                    className="absolute inset-0 w-full h-full object-contain opacity-40 pointer-events-none"
                  />
                )}
              </div>

              {/* Playback Timeline Controls */}
              <div className="w-full mt-4 bg-slate-950/80 border border-slate-800 rounded-xl p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        if (data && currentElementStep >= data.total_elements) {
                          setCurrentElementStep(1);
                          setIsPlaying(true);
                        } else {
                          setIsPlaying(!isPlaying);
                        }
                      }}
                      className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center gap-1.5 transition"
                    >
                      {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                      {isPlaying ? 'Pause' : 'Play the drawing'}
                    </button>
                    <button
                      onClick={handleRestartPlay}
                      className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1 transition"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      From the start
                    </button>
                    <div className="flex items-center gap-1 ml-2">
                      {[16, 32, 64, 128].map((spd) => (
                        <button
                          key={spd}
                          onClick={() => setPlaybackSpeed(spd)}
                          className={`px-2 py-1 rounded text-[11px] font-semibold ${
                            playbackSpeed === spd
                              ? 'bg-indigo-600 text-white'
                              : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {spd / 16}x
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-xs text-slate-400 mr-1.5">Elements:</span>
                    <span className="text-sm font-bold text-emerald-400 font-mono">
                      {currentElementStep.toLocaleString()}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                      {' '}
                      / {data ? data.total_elements.toLocaleString() : '7,554'}
                    </span>
                  </div>
                </div>

                <input
                  type="range"
                  min={1}
                  max={data ? data.total_elements : 7554}
                  value={currentElementStep}
                  onChange={(e) => {
                    setIsPlaying(false);
                    setCurrentElementStep(Number(e.target.value));
                  }}
                  className="w-full accent-rose-500 cursor-pointer"
                />
              </div>
            </div>

            {/* Right Column: 4 Phases & 10 Batches Inspector */}
            <div className="lg:col-span-5 flex flex-col gap-4">
              {activeBatchInfo && (
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-lg">
                  <div className="text-xs font-semibold text-rose-400 mb-1">
                    Current stage (phase {activeBatchInfo.metric.phase}/4 · batch{' '}
                    {activeBatchInfo.metric.batch}/{data?.metrics.length ?? 10})
                  </div>
                  <h2 className="text-base font-bold text-white mb-1.5">
                    {activeBatchInfo.metric.title}
                  </h2>
                  <p className="text-xs text-slate-300 leading-relaxed mb-3">
                    {activeBatchInfo.metric.description}
                  </p>
                  <div className="grid grid-cols-3 gap-2 text-center bg-slate-950/70 rounded-xl p-2.5 border border-slate-800/80">
                    <div>
                      <div className="text-[11px] text-slate-400">Added in this batch</div>
                      <div className="text-sm font-bold text-white font-mono">
                        +{activeBatchInfo.metric.batch_elements.toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] text-slate-400">Total SVG elements</div>
                      <div className="text-sm font-bold text-emerald-400 font-mono">
                        {activeBatchInfo.metric.cumulative_elements.toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] text-slate-400">Match (PSNR)</div>
                      <div className="text-sm font-bold text-indigo-400 font-mono">
                        {activeBatchInfo.metric.psnr_db} dB
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-lg">
                <h3 className="text-sm font-bold text-white mb-2.5 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-rose-400" />
                  Batches (click a stage to jump there)
                </h3>
                <div className="space-y-2 max-h-[540px] overflow-y-auto pr-1">
                  {data?.metrics.map((m, idx) => {
                    const isCurrent = activeBatchInfo?.index === idx;
                    const isDone = currentElementStep >= m.cumulative_elements;
                    return (
                      <button
                        key={m.batch}
                        onClick={() => selectBatchStep(idx)}
                        className={`w-full text-left p-2.5 rounded-xl border transition flex items-start justify-between gap-2 ${
                          isCurrent
                            ? 'bg-rose-500/15 border-rose-500/60 text-white'
                            : isDone
                            ? 'bg-slate-950/60 border-slate-800 text-slate-200 hover:border-slate-700'
                            : 'bg-slate-950/30 border-slate-800/50 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-start gap-2.5">
                          <CheckCircle2
                            className={`w-4 h-4 mt-0.5 shrink-0 ${
                              isDone ? 'text-emerald-400' : 'text-slate-600'
                            }`}
                          />
                          <div>
                            <div className="text-[11px] text-rose-300/90 font-medium">
                              {m.phase_name}
                            </div>
                            <div className="text-xs font-bold">{m.title}</div>
                            <div className="text-[11px] text-slate-400 mt-0.5 line-clamp-2">
                              {m.description}
                            </div>
                          </div>
                        </div>
                        <div className="text-right shrink-0 font-mono">
                          <span className="text-xs font-semibold text-emerald-400 block">
                            {m.cumulative_elements.toLocaleString()} elements
                          </span>
                          <span className="text-[10px] text-slate-500">
                            +{m.batch_elements.toLocaleString()}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'compare' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col items-center">
              <h3 className="text-sm font-bold text-white mb-2">
                Slider (left: original PNG / right: finished SVG, 7,554 elements)
              </h3>
              <div className="relative w-full max-w-[500px] aspect-[1122/1402] rounded-xl overflow-hidden border border-slate-700 select-none">
                <img
                  src="/lgtm_character_final.svg"
                  alt="Completed SVG"
                  className="absolute inset-0 w-full h-full object-contain"
                />
                <div
                  className="absolute inset-0 overflow-hidden"
                  style={{ clipPath: `inset(0 ${100 - compareSplit}% 0 0)` }}
                >
                  <img
                    src="/reference.png"
                    alt="Original Reference"
                    className="w-full h-full object-contain"
                  />
                </div>
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.9)]"
                  style={{ left: `${compareSplit}%` }}
                />
              </div>
              <div className="w-full max-w-[500px] mt-3 flex items-center gap-3">
                <span className="text-xs text-slate-400">Original</span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={compareSplit}
                  onChange={(e) => setCompareSplit(Number(e.target.value))}
                  className="flex-1 accent-rose-500"
                />
                <span className="text-xs text-rose-400 font-semibold">Finished SVG (7,554 elements)</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3 flex flex-col items-center">
                <span className="text-xs font-semibold text-slate-300 mb-2">
                  Original PNG
                </span>
                <img
                  src="/reference.png"
                  alt="Reference"
                  className="w-full rounded-lg border border-slate-800"
                />
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3 flex flex-col items-center">
                <span className="text-xs font-semibold text-emerald-400 mb-2">
                  Finished SVG (lgtm_character_final.svg / 7,554 elements)
                </span>
                <img
                  src="/lgtm_character_final.svg"
                  alt="Final SVG"
                  className="w-full rounded-lg border border-slate-800"
                />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'batches' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {data?.metrics.map((m) => (
              <div
                key={m.batch}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-3 flex flex-col justify-between shadow-lg"
              >
                <div>
                  <div className="flex items-center justify-between text-[11px] text-rose-400 font-semibold mb-1">
                    <span>Batch {m.batch}/10</span>
                    <span className="font-mono text-emerald-400">
                      Total {m.cumulative_elements.toLocaleString()} elements
                    </span>
                  </div>
                  <h4 className="text-xs font-bold text-white mb-1">{m.title}</h4>
                  <p className="text-[11px] text-slate-400 mb-2.5 leading-snug">{m.description}</p>
                </div>
                <div className="rounded-xl overflow-hidden border border-slate-800 bg-white">
                  <img
                    src={`/batches/batch_${String(m.batch).padStart(2, '0')}.png`}
                    alt={m.title}
                    className="w-full h-auto object-contain"
                  />
                </div>
                <button
                  onClick={() => {
                    selectBatchStep(m.batch - 1);
                    setActiveTab('interactive');
                  }}
                  className="mt-2.5 w-full py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 flex items-center justify-center gap-1 transition"
                >
                  Open this stage in the SVG viewer
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
