import { useEffect, useRef } from 'react';
import NoiseCanvas from './NoiseCanvas';
import './VideoPlayer.css';

interface VideoPlayerProps {
  srcObject?: MediaStream | null;
  status?: string;
  cameraEnabled?: boolean;
  id?: string;
}

/**
 * Displays a live video feed or, when no feed is available / camera is off,
 * an animated noise canvas.
 */
export default function VideoPlayer({
  srcObject,
  status = 'waiting',
  cameraEnabled = true,
  id,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (video) video.srcObject = srcObject ?? null;
  }, [srcObject]);

  const showNoise  = !cameraEnabled || !srcObject;
  const noiseLabel = cameraEnabled ? 'No Signal' : 'Camera Disabled';

  return (
    <div className={`video-player ${status}`} id={id}>
      {showNoise ? (
        <NoiseCanvas label={noiseLabel} />
      ) : (
        <video ref={videoRef} autoPlay playsInline muted />
      )}
    </div>
  );
}
