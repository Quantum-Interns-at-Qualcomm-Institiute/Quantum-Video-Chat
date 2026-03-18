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

const mockJoinRoom = jest.fn();

function makeContext(overrides: Partial<any> = {}) {
  return {
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
    joinRoom: mockJoinRoom,
    leaveRoom: jest.fn(),
    setOnFrame: jest.fn(),
    clearError: jest.fn(),
    connectToServer: jest.fn(),
    chat: { messages: [], sendMessage: jest.fn() },
    ...overrides,
  };
}

function renderMainScreen(contextOverrides: Partial<any> = {}) {
  return render(
    <ClientContext.Provider value={makeContext(contextOverrides) as any}>
      <MainScreen />
    </ClientContext.Provider>
  );
}

describe('Start (Lobby view)', () => {
  beforeEach(() => {
    mockJoinRoom.mockClear();
    mockSocket.on.mockClear();
    mockSocket.off.mockClear();
    mockSocket.emit.mockClear();
  });

  it('renders Start Session button', () => {
    renderMainScreen();
    expect(screen.getByText('Start Session')).toBeInTheDocument();
  });

  it('renders Connect button', () => {
    renderMainScreen();
    expect(screen.getByRole('button', { name: 'Connect' })).toBeInTheDocument();
  });

  it('renders lobby title', () => {
    renderMainScreen();
    expect(screen.getByText('QKD Video Chat')).toBeInTheDocument();
  });

  it('shows user ID when waiting and userId is set', () => {
    renderMainScreen({ userId: 'abc123', waitingForPeer: true });
    expect(screen.getByText('abc123')).toBeInTheDocument();
  });

  it('shows waiting state when waitingForPeer is true', () => {
    renderMainScreen({ waitingForPeer: true, userId: 'XY123' });
    expect(screen.getByText(/Waiting for peer to join/)).toBeInTheDocument();
    expect(screen.getByText('XY123')).toBeInTheDocument();
  });

  it('hides waiting state when waitingForPeer is false', () => {
    renderMainScreen({ waitingForPeer: false });
    expect(screen.queryByText(/Waiting for peer to join/)).not.toBeInTheDocument();
    expect(screen.getByText('Start Session')).toBeInTheDocument();
  });
});
