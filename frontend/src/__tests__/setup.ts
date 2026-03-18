/**
 * Global test setup — mocks browser APIs not available in jsdom.
 */

// Mock HTMLCanvasElement.getContext (jsdom doesn't provide canvas 2d context)
HTMLCanvasElement.prototype.getContext = jest.fn().mockReturnValue({
  createImageData: jest.fn().mockReturnValue({ data: new Uint8ClampedArray(4) }),
  putImageData: jest.fn(),
  getImageData: jest.fn().mockReturnValue({ data: new Uint8ClampedArray(4) }),
  drawImage: jest.fn(),
  clearRect: jest.fn(),
  fillRect: jest.fn(),
  fillText: jest.fn(),
  measureText: jest.fn().mockReturnValue({ width: 0 }),
  canvas: { width: 0, height: 0 },
}) as any;

// Mock navigator.mediaDevices.getUserMedia
Object.defineProperty(navigator, 'mediaDevices', {
  value: {
    getUserMedia: jest.fn().mockResolvedValue({
      getTracks: () => [{ stop: jest.fn() }],
    }),
  },
  writable: true,
});
