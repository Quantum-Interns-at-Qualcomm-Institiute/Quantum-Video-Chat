import { useEffect, useRef, useContext } from 'react';
import { ClientContext } from '../utils/ClientContext';

import Header from '../components/Header';
import StatusPopup from '../components/StatusPopup';
import VideoPlayer from '../components/VideoPlayer';
import NoiseCanvas from '../components/NoiseCanvas';
import CircleWidget from '../components/widgets/CircleWidget';
import RectangleWidget from '../components/widgets/RectangleWidget';

import { drawOnCanvas } from '../utils/canvas';
import './Session.css';

export default function Session() {
  const peerCanvasRef = useRef<HTMLCanvasElement>(null);
  const selfCanvasRef = useRef<HTMLCanvasElement>(null);

  const client = useContext(ClientContext);

  // ── Route incoming frames to the correct canvas ────────────────────────
  useEffect(() => {
    client.setOnFrame((canvasData: any) => {
      if (canvasData.self) {
        drawOnCanvas(selfCanvasRef.current, canvasData);
      } else {
        drawOnCanvas(peerCanvasRef.current, canvasData);
      }
    });
  }, []);

  const handleLeave = () => client.leaveRoom();

  return (
    <>
      <Header status={client.status} />
      {client.status === 'bad' && <StatusPopup />}

      <div className="session-content">
        <h3 className="room-id">Room ID: {client.roomId}</h3>

        <div className="top">
          {/* ── Left: Peer video ─────────────────────────────────────── */}
          <div className="video-wrapper">
            <canvas ref={peerCanvasRef} id="peer-stream">
              Waiting for peer…
            </canvas>
          </div>

          <div className="vert-spacer" />

          {/* ── Right: Self video (camera) ───────────────────────────── */}
          <div className="video-wrapper" id="right-video">
            {client.cameraOn ? (
              /* Canvas is always mounted; when no frames arrive it stays blank.
                 Wrapping in the same border-styled div keeps layout consistent. */
              <canvas ref={selfCanvasRef} id="self-stream" className="self-canvas" />
            ) : (
              <VideoPlayer status={client.status} cameraEnabled={false} id="self-stream" />
            )}
          </div>
        </div>

        <div className="bottom">
          <RectangleWidget topText="Accumulated Secret Key" status={client.status}>
            {client.status === 'good' ? '# Mbits' : '…'}
          </RectangleWidget>
          <div className="vert-spacer" />
          <CircleWidget topText="Key Rate" bottomText="Mbits/s" status={client.status}>
            {client.status === 'good' ? '3.33' : '…'}
          </CircleWidget>
          <div className="vert-spacer" />
          <CircleWidget topText="Error Rate %" bottomText="Mbits" status={client.status}>
            {client.status === 'good' ? '0.2' : '…'}
          </CircleWidget>
          <div className="vert-spacer" />

          <button
            className="btn camera-button"
            type="button"
            onClick={client.toggleCamera}
          >
            {client.cameraOn ? '📷 Cam On' : '🚫 Cam Off'}
          </button>

          <div className="vert-spacer" />

          <button className="btn btn-danger leave-button" type="button" onClick={handleLeave}>
            Leave
          </button>
        </div>
      </div>
    </>
  );
}
