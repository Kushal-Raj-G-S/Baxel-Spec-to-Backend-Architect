"use client";

import React, { useEffect, useRef, useState } from "react";
import { useScroll, useMotionValueEvent } from "framer-motion";

const FRAME_COUNT = 240;

export default function ScrollytellingSphere() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [images, setImages] = useState<HTMLImageElement[]>([]);
  const [imagesLoaded, setImagesLoaded] = useState(0);
  const [progress, setProgress] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Preload images
  useEffect(() => {
    const loadedImages: HTMLImageElement[] = [];
    let loadedCount = 0;

    for (let i = 1; i <= FRAME_COUNT; i++) {
      const img = new Image();
      const paddedIndex = i.toString().padStart(3, "0");
      img.src = `/3d-frames/ezgif-frame-${paddedIndex}.jpg`;
      img.onload = () => {
        loadedCount++;
        setImagesLoaded(loadedCount);
      };
      loadedImages.push(img);
    }
    setImages(loadedImages);
  }, []);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  // Track progress strictly in state to avoid SSR overlap bugs
  useMotionValueEvent(scrollYProgress, "change", (latest) => {
    setProgress(latest);
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || images.length < FRAME_COUNT) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;

    const render = () => {
      // Use the raw scrollYProgress to drive the frame index smoothly
      const currentProgress = scrollYProgress.get();
      const index = Math.min(FRAME_COUNT - 1, Math.max(0, Math.round(currentProgress * (FRAME_COUNT - 1))));
      const currentImage = images[index];

      if (currentImage && currentImage.complete && canvas.width > 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const hRatio = canvas.width / currentImage.width;
        const vRatio = canvas.height / currentImage.height;
        const ratio = Math.max(hRatio, vRatio);

        const centerShift_x = (canvas.width - currentImage.width * ratio) / 2;
        // Added +60 to push the 3D frames a bit lower within the canvas
        const centerShift_y = (canvas.height - currentImage.height * ratio) / 2 + 25;

        ctx.drawImage(
          currentImage,
          0, 0, currentImage.width, currentImage.height,
          centerShift_x, centerShift_y, currentImage.width * ratio, currentImage.height * ratio
        );
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    const resizeCanvas = () => {
      const parent = canvas.parentElement;
      if (parent) {
        canvas.width = parent.clientWidth;
        canvas.height = parent.clientHeight;
      }
    };

    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", resizeCanvas);
    };
  }, [images, scrollYProgress]);

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
          {imagesLoaded < FRAME_COUNT && (
            <div className="absolute inset-0 z-50 flex items-center justify-center bg-transparent">
              <p className="text-black/60 tracking-widest uppercase text-sm font-semibold">
                Loading Animation {Math.round((imagesLoaded / FRAME_COUNT) * 100)}%
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
                <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-black mb-2">
                  Baxel Intelligence.
                </h1>
                <p className="text-base md:text-lg text-black/60 max-w-lg font-medium">
                  Turn messy PRDs into production-ready backend blueprints.
                </p>
              </div>

              {/* ENGINEERING REVEAL */}
              <div
                style={{ ...getSectionStyle(0.15, 0.2, 0.35, 0.4), transition: 'opacity 0.1s, transform 0.1s' }}
                className="absolute inset-0 flex flex-col items-center text-center pointer-events-none"
              >
                <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-black mb-3">
                  Deconstruct complexity.
                </h2>
                <p className="text-base text-black/70 max-w-lg font-medium">
                  Every entity, relation, and constraint is automatically extracted and mapped perfectly.
                </p>
              </div>

              {/* PROCESSING */}
              <div
                style={{ ...getSectionStyle(0.4, 0.45, 0.6, 0.65), transition: 'opacity 0.1s, transform 0.1s' }}
                className="absolute inset-0 flex flex-col items-center text-center pointer-events-none"
              >
                <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-black mb-3">
                  Intelligent pipeline.
                </h2>
                <p className="text-base text-black/70 max-w-lg font-medium">
                  Multi-stage reasoning surfaces gaps and conflicts in real-time, keeping you in flow.
                </p>
              </div>

              {/* GENERATION */}
              <div
                style={{ ...getSectionStyle(0.65, 0.7, 0.8, 0.85), transition: 'opacity 0.1s, transform 0.1s' }}
                className="absolute inset-0 flex flex-col items-center text-center pointer-events-none"
              >
                <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-black mb-3">
                  Deployable output.
                </h2>
                <p className="text-base text-black/70 max-w-lg font-medium">
                  Export comprehensive API definitions and Node.js skeletons instantly.
                </p>
              </div>

              {/* CTA */}
              <div
                style={{ ...getCTAStyle(), transition: 'opacity 0.1s, transform 0.1s' }}
                className={`absolute inset-0 flex flex-col items-center text-center ${progress < 0.85 ? 'pointer-events-none' : 'pointer-events-auto'}`}
              >
                <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-black mb-4">
                  Ship faster.
                </h2>
                <div className="flex gap-4">
                  <a href="/auth" className="rounded-full bg-gradient-to-r from-[#0050FF] to-[#00D6FF] px-6 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:scale-105">
                    Experience Baxel
                  </a>
                  <a href="/features" className="rounded-full border border-black/10 bg-black/5 backdrop-blur-md px-6 py-2.5 text-sm font-semibold text-black transition hover:bg-black/10">
                    View Features
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
