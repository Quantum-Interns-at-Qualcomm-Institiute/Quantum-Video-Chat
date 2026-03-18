/**
 * MediaControls — Camera and microphone toggle buttons.
 *
 * Single responsibility: media device controls.
 */
import CameraOnIcon from './icons/CameraOnIcon';
import CameraOffIcon from './icons/CameraOffIcon';
import MicOnIcon from './icons/MicOnIcon';
import MicOffIcon from './icons/MicOffIcon';

interface MediaControlsProps {
  cameraOn:      boolean;
  muted:         boolean;
  toggleCamera:  () => void;
  toggleMute:    () => void;
}

export default function MediaControls({ cameraOn, muted, toggleCamera, toggleMute }: MediaControlsProps) {
  return (
    <div className="media-controls">
      <button
        className={`button media-btn ${cameraOn ? '' : 'media-btn--off'}`}
        type="button"
        onClick={toggleCamera}
        title={cameraOn ? 'Turn camera off' : 'Turn camera on'}
      >
        {cameraOn ? <CameraOnIcon size={16} /> : <CameraOffIcon size={16} />}
        <span>{cameraOn ? 'Cam On' : 'Cam Off'}</span>
      </button>

      <button
        className={`button media-btn ${muted ? 'media-btn--off' : ''}`}
        type="button"
        onClick={toggleMute}
        title={muted ? 'Unmute microphone' : 'Mute microphone'}
      >
        {muted ? <MicOffIcon size={16} /> : <MicOnIcon size={16} />}
        <span>{muted ? 'Muted' : 'Mic On'}</span>
      </button>
    </div>
  );
}
