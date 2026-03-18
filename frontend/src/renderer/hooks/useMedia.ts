/**
 * useMedia — Manages camera and microphone state + device selection.
 *
 * Single responsibility: local media device toggles, camera picker,
 * and audio input picker.
 * Accepts an optional socket provider for dependency injection (testing).
 */
import { useState, useEffect, useCallback } from 'react';
import { Socket } from 'socket.io-client';
import { getSocket } from '../utils/socket';

export interface CameraDevice {
  index: number;
  label: string;
}

export interface AudioDevice {
  index: number;
  label: string;
}

export interface MediaState {
  cameraOn:             boolean;
  muted:                boolean;
  cameras:              CameraDevice[];
  selectedCamera:       number;
  audioDevices:         AudioDevice[];
  selectedAudio:        number;
  toggleCamera:         () => void;
  toggleMute:           () => void;
  selectCamera:         (deviceIndex: number) => void;
  refreshCameras:       () => void;
  selectAudio:          (deviceIndex: number) => void;
  refreshAudioDevices:  () => void;
}

/**
 * @param socketProvider — Optional function returning a Socket instance.
 *        Defaults to ``getSocket``. Pass a custom provider in tests.
 */
export function useMedia(
  socketProvider: () => Socket = getSocket,
): MediaState {
  const [cameraOn, setCameraOn]             = useState(true);
  const [muted, setMuted]                   = useState(false);
  const [cameras, setCameras]               = useState<CameraDevice[]>([]);
  const [selectedCamera, setSelectedCamera] = useState(0);
  const [audioDevices, setAudioDevices]     = useState<AudioDevice[]>([]);
  const [selectedAudio, setSelectedAudio]   = useState(0);

  const toggleCamera = () => {
    setCameraOn((prev) => {
      const newVal = !prev;
      socketProvider().emit('toggle_camera', { enabled: newVal });
      return newVal;
    });
  };

  const toggleMute = () => {
    setMuted((prev) => {
      const newVal = !prev;
      socketProvider().emit('toggle_mute', { muted: newVal });
      return newVal;
    });
  };

  const refreshCameras = useCallback(() => {
    socketProvider().emit('list_cameras');
  }, [socketProvider]);

  const selectCamera = useCallback((deviceIndex: number) => {
    setSelectedCamera(deviceIndex);
    socketProvider().emit('select_camera', { device: deviceIndex });
  }, [socketProvider]);

  const refreshAudioDevices = useCallback(() => {
    socketProvider().emit('list_audio_devices');
  }, [socketProvider]);

  const selectAudio = useCallback((deviceIndex: number) => {
    setSelectedAudio(deviceIndex);
    socketProvider().emit('select_audio', { device: deviceIndex });
  }, [socketProvider]);

  // Listen for camera-list responses from the middleware
  useEffect(() => {
    const socket = socketProvider();

    const onCameraList = (devices: CameraDevice[]) => {
      setCameras(devices);
      // If current selection isn't in the list, default to first device
      if (devices.length > 0 && !devices.some((d) => d.index === selectedCamera)) {
        setSelectedCamera(devices[0].index);
      }
    };

    socket.on('camera-list', onCameraList);
    return () => { socket.off('camera-list', onCameraList); };
  }, [socketProvider, selectedCamera]);

  // Listen for audio-device-list responses from the middleware
  useEffect(() => {
    const socket = socketProvider();

    const onAudioDeviceList = (devices: AudioDevice[]) => {
      setAudioDevices(devices);
      if (devices.length > 0 && !devices.some((d) => d.index === selectedAudio)) {
        setSelectedAudio(devices[0].index);
      }
    };

    socket.on('audio-device-list', onAudioDeviceList);
    return () => { socket.off('audio-device-list', onAudioDeviceList); };
  }, [socketProvider, selectedAudio]);

  return {
    cameraOn, muted, cameras, selectedCamera, audioDevices, selectedAudio,
    toggleCamera, toggleMute, selectCamera, refreshCameras,
    selectAudio, refreshAudioDevices,
  };
}
