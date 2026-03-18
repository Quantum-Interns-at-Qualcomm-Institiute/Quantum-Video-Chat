/**
 * canvas.ts — Shared video frame rendering utilities.
 *
 * Converts Python BGR frame data to browser-native RGBA format and
 * draws it onto an HTMLCanvasElement.
 */

export interface FramePayload {
  frame:  any;
  width:  number;
  height: number;
  self?:  boolean;
}

/**
 * Normalise a Python frame (nested BGR arrays) to a flat RGBA
 * Uint8ClampedArray suitable for ``ImageData``.
 */
export function toRGBA(raw: any): Uint8ClampedArray {
  if (Array.isArray(raw) && Array.isArray(raw[0]) && Array.isArray(raw[0][0])) {
    const flat: number[] = [];
    for (const row of raw) {
      for (const px of row) {
        flat.push(px[2], px[1], px[0], 255); // BGR → RGBA
      }
    }
    return new Uint8ClampedArray(flat);
  }
  const arr = raw.flat ? raw.flat(Infinity) : Array.from(raw);
  return new Uint8ClampedArray(arr);
}

/**
 * Draw a ``FramePayload`` onto a canvas element.  No-ops if *canvas* is null.
 */
export function drawOnCanvas(
  canvas: HTMLCanvasElement | null,
  canvasData: FramePayload,
): void {
  if (!canvas) return;
  canvas.width  = canvasData.width;
  canvas.height = canvasData.height;
  const ctx = canvas.getContext('2d')!;
  ctx.putImageData(
    new ImageData(toRGBA(canvasData.frame), canvasData.width, canvasData.height),
    0,
    0,
  );
}
