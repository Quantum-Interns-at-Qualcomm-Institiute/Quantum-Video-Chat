/**
 * InCall — Zoom-like in-session video layout.
 *
 * Peer video fills the main area, self-video is a small PiP overlay
 * in the bottom-right, and a bottom toolbar provides cam/mic/leave controls.
 */
import { useEffect, useRef, useContext, useState } from 'react';
import { ClientContext } from '../utils/ClientContext';
import { drawOnCanvas } from '../utils/canvas';

import CameraOnIcon from './icons/CameraOnIcon';
import CameraOffIcon from './icons/CameraOffIcon';
import MicOnIcon from './icons/MicOnIcon';
import MicOffIcon from './icons/MicOffIcon';
import PhoneOffIcon from './icons/PhoneOffIcon';
import NoiseCanvas from './NoiseCanvas';
import StatusPopup from './StatusPopup';
import './InCall.css';

export default function InCall() {
  const client = useContext(ClientContext);
  const peerCanvasRef = useRef<HTMLCanvasElement>(null);
  const selfCanvasRef = useRef<HTMLCanvasElement>(null);
  const [elapsed, setElapsed] = useState(0);

  // ── Route incoming frames to the correct canvas ─────────────────────
  useEffect(() => {
    client.setOnFrame((canvasData: any) => {
      if (canvasData.self) {
        drawOnCanvas(selfCanvasRef.current, canvasData);
      } else {
        drawOnCanvas(peerCanvasRef.current, canvasData);
      }
    });
  }, []);

  // ── Elapsed time counter ────────────────────────────────────────────
  useEffect(() => {
    const interval = setInterval(() => setElapsed((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div className="incall">
      {/* ── Encryption status overlay ─────────────────────────────────── */}
      {client.status === 'bad' && <StatusPopup />}

      {/* ── Peer video (fills the frame) ──────────────────────────────── */}
      <div className="incall-video-area">
        <canvas ref={peerCanvasRef} className="incall-peer-canvas" />
        {/* Show noise when no peer frames yet */}
        <div className="incall-peer-noise">
          <NoiseCanvas label="Waiting for video..." />
        </div>

        {/* ── Self PiP (bottom-right overlay) ─────────────────────────── */}
        <div className="incall-pip">
          <canvas ref={selfCanvasRef} className="incall-pip-canvas" />
          {!client.cameraOn && (
            <div className="incall-pip-off">
              <CameraOffIcon size={16} />
            </div>
          )}
        </div>
      </div>

      {/* ── Info bar ──────────────────────────────────────────────────── */}
      <div className="incall-info">
        <span className="incall-room">
          Room: <strong>{client.roomId}</strong>
        </span>
        <span className="incall-timer">{formatTime(elapsed)}</span>
      </div>

      {/* ── Bottom toolbar ────────────────────────────────────────────── */}
      <div className="incall-toolbar">
        <div className="incall-toolbar-center">
          <button
            className={`incall-tool-btn ${client.cameraOn ? '' : 'incall-tool-btn--off'}`}
            onClick={client.toggleCamera}
            title={client.cameraOn ? 'Turn camera off' : 'Turn camera on'}
          >
            {client.cameraOn ? <CameraOnIcon size={20} /> : <CameraOffIcon size={20} />}
            <span className="incall-tool-label">{client.cameraOn ? 'Camera' : 'Camera Off'}</span>
          </button>

          <button
            className={`incall-tool-btn ${client.muted ? 'incall-tool-btn--off' : ''}`}
            onClick={client.toggleMute}
            title={client.muted ? 'Unmute microphone' : 'Mute microphone'}
          >
            {client.muted ? <MicOffIcon size={20} /> : <MicOnIcon size={20} />}
            <span className="incall-tool-label">{client.muted ? 'Muted' : 'Mic'}</span>
          </button>
        </div>

        <button
          className="incall-leave-btn"
          onClick={() => client.leaveRoom()}
          title="Leave session"
        >
          <PhoneOffIcon size={20} />
          <span className="incall-tool-label">Leave</span>
        </button>
      </div>
    </div>
  );
}
