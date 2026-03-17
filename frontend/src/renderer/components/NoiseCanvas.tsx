import { useEffect, useRef } from 'react';
import './NoiseCanvas.css';

interface NoiseCanvasProps {
  /** Label shown over the static. Defaults to 'Camera Disabled'. */
  label?: string;
  /** Width of the noise texture (lower = faster, looks more like CRT). */
  resolution?: number;
}

/**
 * Renders animated TV-static noise on a canvas.
 * Used as the "camera disabled" placeholder wherever a video feed is absent.
 */
export default function NoiseCanvas({
  label = 'Camera Disabled',
  resolution = 160,
}: NoiseCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef    = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d')!;
    const w = resolution;
    const h = Math.round(resolution * (9 / 16));
    canvas.width  = w;
    canvas.height = h;

    const imageData = ctx.createImageData(w, h);
    const buf = imageData.data;

    const draw = () => {
      for (let i = 0; i < buf.length; i += 4) {
        const v = (Math.random() * 200 + 30) | 0; // bias toward grey, not pure black/white
        buf[i]     = v;
        buf[i + 1] = v;
        buf[i + 2] = v;
        buf[i + 3] = 255;
      }
      ctx.putImageData(imageData, 0, 0);
      rafRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(rafRef.current);
  }, [resolution]);

  return (
    <div className="noise-canvas-wrapper">
      <canvas ref={canvasRef} className="noise-canvas" />
      {label && <span className="noise-label">{label}</span>}
    </div>
  );
}
