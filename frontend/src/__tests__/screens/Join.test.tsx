import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import MainScreen from '../../renderer/screens/MainScreen';
import { ClientContext } from '../../renderer/utils/ClientContext';

// Mock the socket module
const mockSocket = {
  on: jest.fn(),
  off: jest.fn(),
  emit: jest.fn(),
  connected: false,
  connect: jest.fn(),
};
jest.mock('../../renderer/utils/socket', () => ({
  getSocket: () => mockSocket,
  connectMiddleware: () => mockSocket,
  getMiddlewareInfo: () => ({ port: 5001, url: 'http://localhost:5001' }),
}));

jest.mock('../../renderer/platform', () => ({
  __esModule: true,
  default: {
    getSettings: jest.fn().mockResolvedValue({}),
    saveSettings: jest.fn().mockResolvedValue(undefined),
    getDefaults: jest.fn().mockResolvedValue({}),
    ipcListen: jest.fn(),
    ipcRemoveListener: jest.fn(),
    rendererReady: jest.fn(),
    setPeerId: jest.fn(),
    disconnect: jest.fn(),
    toggleMute: jest.fn(),
  },
}));

const mockContextValue: any = {
  middlewareConnected: false,
  serverConnected: false,
  userId: '',
  status: 'waiting',
  roomId: '',
  cameraOn: true,
  muted: false,
  cameras: [],
  selectedCamera: 0,
  waitingForPeer: false,
  errorMessage: '',
  toggleCamera: jest.fn(),
  toggleMute: jest.fn(),
  selectCamera: jest.fn(),
  refreshCameras: jest.fn(),
  audioDevices: [],
  selectedAudio: 0,
  selectAudio: jest.fn(),
  refreshAudioDevices: jest.fn(),
  joinRoom: jest.fn(),
  leaveRoom: jest.fn(),
  setOnFrame: jest.fn(),
  clearError: jest.fn(),
  connectToServer: jest.fn(),
  chat: { messages: [], sendMessage: jest.fn() },
};

function renderMainScreen() {
  return render(
    <ClientContext.Provider value={mockContextValue}>
      <MainScreen />
    </ClientContext.Provider>
  );
}

describe('Join (Lobby view)', () => {
  it('renders Room ID input', () => {
    renderMainScreen();
    expect(screen.getByPlaceholderText('Enter code or leave blank')).toBeInTheDocument();
  });

  it('renders Join button', () => {
    renderMainScreen();
    expect(screen.getByText('Join')).toBeInTheDocument();
  });

  it('renders lobby title', () => {
    renderMainScreen();
    expect(screen.getByText('QKD Video Chat')).toBeInTheDocument();
  });
});
