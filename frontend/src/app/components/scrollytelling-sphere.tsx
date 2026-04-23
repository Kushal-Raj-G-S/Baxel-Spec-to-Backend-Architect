"use client";

import React, { useEffect, useRef, useState } from "react";

const FRAME_COUNT = 240;
const FRAME_CACHE_RADIUS = 10;
const FRAME_CACHE_EVICT_RADIUS = 24;
const SMOOTHING_FACTOR = 0.16;
const SMOOTHING_EPSILON = 0.0005;

export default function ScrollytellingSphere() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameCacheRef = useRef<Map<number, HTMLImageElement>>(new Map());
  const loadingFramesRef = useRef<Set<number>>(new Set());
  const targetFrameRef = useRef(0);
  const [progress, setProgress] = useState(0);
  const [initialFrameReady, setInitialFrameReady] = useState(false);
  const [bufferedFrameCount, setBufferedFrameCount] = useState(0);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0, pixelRatio: 1 });
  const [mounted, setMounted] = useState(false);
  const lastDrawnFrameRef = useRef<number>(-1);
  const targetProgressRef = useRef(0);
  const smoothedProgressRef = useRef(0);
  const renderRafRef = useRef<number | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const loadFrame = (index: number) => {
    if (index < 0 || index >= FRAME_COUNT) return;

    const cache = frameCacheRef.current;
    const loading = loadingFramesRef.current;
    if (cache.has(index) || loading.has(index)) return;

    loading.add(index);
    const img = new Image();
    img.decoding = "async";
    img.fetchPriority = "low";
    const paddedIndex = (index + 1).toString().padStart(3, "0");
    img.src = `/3d-frames/ezgif-frame-${paddedIndex}.jpg`;

    img.onload = () => {
      loading.delete(index);
      cache.set(index, img);
      setBufferedFrameCount(cache.size);

      if (index === 0) {
        setInitialFrameReady(true);
      }
    };

    img.onerror = () => {
      loading.delete(index);
    };
  };

  const warmAndEvictFrames = (centerIndex: number) => {
    for (let i = centerIndex - FRAME_CACHE_RADIUS; i <= centerIndex + FRAME_CACHE_RADIUS; i++) {
      loadFrame(i);
    }

    const cache = frameCacheRef.current;
    for (const [index, img] of cache.entries()) {
      if (Math.abs(index - centerIndex) > FRAME_CACHE_EVICT_RADIUS) {
        cache.delete(index);
        img.src = "";
      }
    }

    setBufferedFrameCount(cache.size);
  };

  useEffect(() => {
    warmAndEvictFrames(0);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let ticking = false;

    const updateProgress = () => {
      const rect = container.getBoundingClientRect();
      const scrollRange = Math.max(1, rect.height - window.innerHeight);
      const current = -rect.top;
      const next = Math.min(1, Math.max(0, current / scrollRange));
      setProgress(next);
      ticking = false;
    };

    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(updateProgress);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    updateProgress();

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const updateCanvasSize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;

      const cssWidth = parent.clientWidth;
      const cssHeight = parent.clientHeight;
      // Prioritize smoothness: keep render resolution at CSS pixel size.
      const pixelRatio = 1;

      canvas.style.width = `${cssWidth}px`;
      canvas.style.height = `${cssHeight}px`;
      canvas.width = Math.max(1, Math.floor(cssWidth * pixelRatio));
      canvas.height = Math.max(1, Math.floor(cssHeight * pixelRatio));

      setCanvasSize({ width: cssWidth, height: cssHeight, pixelRatio });
    };

    updateCanvasSize();
    window.addEventListener("resize", updateCanvasSize);

    return () => {
      window.removeEventListener("resize", updateCanvasSize);
    };
  }, []);

  useEffect(() => {
    const centerIndex = Math.min(FRAME_COUNT - 1, Math.max(0, Math.round(progress * (FRAME_COUNT - 1))));
    targetFrameRef.current = centerIndex;
    warmAndEvictFrames(centerIndex);
  }, [progress]);

  useEffect(() => {
    targetProgressRef.current = progress;

    const canRender = initialFrameReady && canvasSize.width > 0 && canvasSize.height > 0;
    if (!canRender || renderRafRef.current !== null) return;

    const drawFrame = () => {
      const canvas = canvasRef.current;
      if (!canvas) {
        renderRafRef.current = null;
        return;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        renderRafRef.current = null;
        return;
      }

      const target = targetProgressRef.current;
      const current = smoothedProgressRef.current;
      const delta = target - current;
      const nextProgress = Math.abs(delta) < SMOOTHING_EPSILON ? target : current + delta * SMOOTHING_FACTOR;
      smoothedProgressRef.current = nextProgress;

      const index = Math.min(FRAME_COUNT - 1, Math.max(0, Math.round(nextProgress * (FRAME_COUNT - 1))));
      let currentImage = frameCacheRef.current.get(index);

      if (!currentImage) {
        for (let distance = 1; distance <= FRAME_CACHE_RADIUS; distance++) {
          currentImage = frameCacheRef.current.get(index - distance) || frameCacheRef.current.get(index + distance);
          if (currentImage) break;
        }
      }

      if (currentImage && currentImage.complete && lastDrawnFrameRef.current !== index) {
        const { width: cssWidth, height: cssHeight, pixelRatio } = canvasSize;

        ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        ctx.clearRect(0, 0, cssWidth, cssHeight);

        const hRatio = cssWidth / currentImage.width;
        const vRatio = cssHeight / currentImage.height;
        const ratio = Math.max(hRatio, vRatio);

        const centerShiftX = (cssWidth - currentImage.width * ratio) / 2;
        const centerShiftY = (cssHeight - currentImage.height * ratio) / 2 + 25;

        ctx.drawImage(
          currentImage,
          0,
          0,
          currentImage.width,
          currentImage.height,
          centerShiftX,
          centerShiftY,
          currentImage.width * ratio,
          currentImage.height * ratio
        );

        lastDrawnFrameRef.current = index;
      }

      const shouldContinue =
        Math.abs(target - smoothedProgressRef.current) > SMOOTHING_EPSILON ||
        !frameCacheRef.current.has(targetFrameRef.current);

      if (shouldContinue) {
        renderRafRef.current = requestAnimationFrame(drawFrame);
      } else {
        renderRafRef.current = null;
      }
    };

    renderRafRef.current = requestAnimationFrame(drawFrame);
  }, [progress, canvasSize, initialFrameReady, bufferedFrameCount]);

  useEffect(() => {
    return () => {
      if (renderRafRef.current !== null) {
        cancelAnimationFrame(renderRafRef.current);
      }
    };
  }, []);

  // Robust style calculators
  const getHeroStyle = () => {
    let opacity = 1;
    let y = 0;
    if (progress > 0.1 && progress <= 0.15) {
      opacity = 1 - (progress - 0.1) / 0.05;
      y = -20 * (1 - opacity);
    } else if (progress > 0.15) {
      opacity = 0;
      y = -20;
    }
    return { opacity, transform: `translateY(${y}px)` };
  };

  const getSectionStyle = (startIn: number, endIn: number, startOut: number, endOut: number) => {
    let opacity = 0;
    let y = 20;
    if (progress > startIn && progress <= endIn) {
      opacity = (progress - startIn) / (endIn - startIn);
      y = 20 * (1 - opacity);
    } else if (progress > endIn && progress <= startOut) {
      opacity = 1;
      y = 0;
    } else if (progress > startOut && progress <= endOut) {
      opacity = 1 - (progress - startOut) / (endOut - startOut);
      y = -20 * (1 - opacity);
    } else if (progress > endOut) {
      opacity = 0;
      y = -20;
    }
    return { opacity, transform: `translateY(${y}px)` };
  };

  const getCTAStyle = () => {
    let opacity = 0;
    let y = 20;
    if (progress > 0.85 && progress <= 0.9) {
      opacity = (progress - 0.85) / 0.05;
      y = 20 * (1 - opacity);
    } else if (progress > 0.9) {
      opacity = 1;
      y = 0;
    }
    return { opacity, transform: `translateY(${y}px)` };
  };

  return (
    <div
      ref={containerRef}
      className="relative w-full"
      style={{ height: "400vh" }}
    >
      <div className="sticky top-16 flex flex-col items-center justify-start w-full px-6 pt-4">

        {/* Camouflaged 3D Section */}
        <div className="relative w-full max-w-6xl h-[70vh] rounded-[2rem] overflow-hidden bg-transparent">
          {/* Loader */}
          {!initialFrameReady && (
            <div className="absolute inset-0 z-50 flex items-center justify-center bg-transparent">
              <p className="text-black/60 tracking-widest uppercase text-sm font-semibold">
                Buffering 3D Frames ({bufferedFrameCount})
              </p>
            </div>
          )}

          <canvas
            ref={canvasRef}
            className="absolute inset-0 h-full w-full object-cover"
          />
        </div>

        {/* Storytelling Text Overlays */}
        <div className="relative w-full max-w-4xl h-10 mt-2">

          {mounted && (
            <>
              {/* HERO */}
              <div
                style={{ ...getHeroStyle(), transition: 'opacity 0.1s, transform 0.1s' }}
                className={`absolute inset-0 flex flex-col items-center text-center ${progress > 0.2 ? 'pointer-events-none' : ''}`}
              >
                <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-2">
                  Baxel Intelligence.
                </h1>
                <p className="text-base md:text-lg text-white/60 max-w-lg font-medium">
                  Turn messy PRDs into production-ready backend blueprints.
                </p>
              </div>

              {/* ENGINEERING REVEAL */}
              <div
                style={{ ...getSectionStyle(0.15, 0.2, 0.35, 0.4), transition: 'opacity 0.1s, transform 0.1s' }}
                className="absolute inset-0 flex flex-col items-center text-center pointer-events-none"
              >
                <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-3">
                  Deconstruct complexity.
                </h2>
                <p className="text-base text-white/70 max-w-lg font-medium">
                  Every entity, relation, and constraint is automatically extracted and mapped perfectly.
                </p>
              </div>

              {/* PROCESSING */}
              <div
                style={{ ...getSectionStyle(0.4, 0.45, 0.6, 0.65), transition: 'opacity 0.1s, transform 0.1s' }}
                className="absolute inset-0 flex flex-col items-center text-center pointer-events-none"
              >
                <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-3">
                  Intelligent pipeline.
                </h2>
                <p className="text-base text-white/70 max-w-lg font-medium">
                  Multi-stage reasoning surfaces gaps and conflicts in real-time, keeping you in flow.
                </p>
              </div>

              {/* GENERATION */}
              <div
                style={{ ...getSectionStyle(0.65, 0.7, 0.8, 0.85), transition: 'opacity 0.1s, transform 0.1s' }}
                className="absolute inset-0 flex flex-col items-center text-center pointer-events-none"
              >
                <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-3">
                  Deployable output.
                </h2>
                <p className="text-base text-white/70 max-w-lg font-medium">
                  Export comprehensive API definitions and Node.js skeletons instantly.
                </p>
              </div>

              {/* CTA */}
              <div
                style={{ ...getCTAStyle(), transition: 'opacity 0.1s, transform 0.1s' }}
                className={`absolute inset-0 flex flex-col items-center text-center ${progress < 0.85 ? 'pointer-events-none' : 'pointer-events-auto'}`}
              >
                <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-4">
                  Ship faster.
                </h2>
                <div className="flex gap-4 justify-center">
                  <a href="/auth" className="rounded-full bg-[#C2D68C] px-6 py-2.5 text-sm font-semibold text-[#1F261D] shadow-[0_0_15px_rgba(194,214,140,0.3)] transition hover:scale-105">
                    Experience Baxel
                  </a>
                  <a href="/pricing" className="rounded-full border border-white/20 bg-white/5 backdrop-blur-md px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10">
                    View Pricing
                  </a>
                </div>
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
