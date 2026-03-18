import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import VideoPlayer from '../../renderer/components/VideoPlayer';

// jsdom doesn't implement HTMLCanvasElement.getContext — stub it out so
// NoiseCanvas (rendered when no srcObject) doesn't throw.
beforeAll(() => {
  HTMLCanvasElement.prototype.getContext = jest.fn().mockReturnValue({
    createImageData: jest.fn().mockReturnValue({ data: new Uint8ClampedArray(0) }),
    putImageData: jest.fn(),
  });
});

describe('VideoPlayer', () => {
  it('renders noise canvas when no srcObject', () => {
    const { container } = render(<VideoPlayer srcObject={null} />);
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeInTheDocument();
  });

  it('renders the player container', () => {
    const { container } = render(<VideoPlayer srcObject={null} />);
    expect(container.querySelector('.video-player')).toBeInTheDocument();
  });

  it('renders with custom id', () => {
    const { container } = render(<VideoPlayer srcObject={null} id="test-player" />);
    expect(container.firstChild).toBeTruthy();
  });

  it('shows "No Signal" label when camera enabled but no source', () => {
    const { container } = render(<VideoPlayer srcObject={null} cameraEnabled={true} />);
    expect(container.textContent).toContain('No Signal');
  });

  it('shows "Camera Disabled" label when camera is off', () => {
    const { container } = render(<VideoPlayer srcObject={null} cameraEnabled={false} />);
    expect(container.textContent).toContain('Camera Disabled');
  });
});
