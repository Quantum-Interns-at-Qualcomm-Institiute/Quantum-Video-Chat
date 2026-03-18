import '@testing-library/jest-dom';
import { render, screen, fireEvent } from '@testing-library/react';
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

// Mock platform
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
const mockLeaveRoom = jest.fn();
const mockToggleCamera = jest.fn();
const mockToggleMute = jest.fn();
const mockConnectToServer = jest.fn();
const mockClearError = jest.fn();

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
    toggleCamera: mockToggleCamera,
    toggleMute: mockToggleMute,
    selectCamera: jest.fn(),
    refreshCameras: jest.fn(),
    audioDevices: [],
    selectedAudio: 0,
    selectAudio: jest.fn(),
    refreshAudioDevices: jest.fn(),
    joinRoom: mockJoinRoom,
    leaveRoom: mockLeaveRoom,
    setOnFrame: jest.fn(),
    clearError: mockClearError,
    connectToServer: mockConnectToServer,
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

describe('MainScreen — Lobby view', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSocket.on.mockClear();
    mockSocket.off.mockClear();
    mockSocket.emit.mockClear();
  });

  // ── Lobby title ───────────────────────────────────────────────────────
  it('renders title in lobby', () => {
    renderMainScreen();
    expect(screen.getByText('QKD Video Chat')).toBeInTheDocument();
  });

  // ── Header ────────────────────────────────────────────────────────────
  it('renders Header with logo in lobby', () => {
    renderMainScreen();
    expect(screen.getByAltText('UCSD Logo')).toBeInTheDocument();
  });

  // ── Server connection ─────────────────────────────────────────────────
  it('renders Connect button', () => {
    renderMainScreen();
    expect(screen.getByText('Connect')).toBeInTheDocument();
  });

  it('renders server host input', () => {
    renderMainScreen();
    expect(screen.getByPlaceholderText('192.168.x.x')).toBeInTheDocument();
  });

  it('renders server port input', () => {
    renderMainScreen();
    expect(screen.getByPlaceholderText('7777')).toBeInTheDocument();
  });

  // ── Session controls ──────────────────────────────────────────────────
  it('renders Start Session button', () => {
    renderMainScreen();
    expect(screen.getByText('Start Session')).toBeInTheDocument();
  });

  it('renders Join button', () => {
    renderMainScreen();
    expect(screen.getByText('Join')).toBeInTheDocument();
  });

  it('disables Start Session when not connected', () => {
    renderMainScreen();
    expect(screen.getByText('Start Session')).toBeDisabled();
  });

  it('disables Join when not connected', () => {
    renderMainScreen();
    expect(screen.getByText('Join')).toBeDisabled();
  });

  // ── Room ID input ─────────────────────────────────────────────────────
  it('renders Room ID input', () => {
    renderMainScreen();
    expect(screen.getByPlaceholderText('Enter code or leave blank')).toBeInTheDocument();
  });

  // ── Media controls ────────────────────────────────────────────────────
  it('renders camera toggle button', () => {
    renderMainScreen();
    expect(screen.getByTitle('Turn camera off')).toBeInTheDocument();
  });

  it('renders mic toggle button', () => {
    renderMainScreen();
    expect(screen.getByTitle('Mute microphone')).toBeInTheDocument();
  });

  // ── Waiting state ─────────────────────────────────────────────────────
  it('shows waiting for peer message', () => {
    renderMainScreen({ waitingForPeer: true, userId: 'TEST1' });
    expect(screen.getByText(/Waiting for peer to join/)).toBeInTheDocument();
  });

  it('shows user ID when waiting', () => {
    renderMainScreen({ waitingForPeer: true, userId: 'abc123' });
    expect(screen.getByText('abc123')).toBeInTheDocument();
  });

  // ── Error toast ───────────────────────────────────────────────────────
  it('shows error as toast when errorMessage set', () => {
    renderMainScreen({ errorMessage: 'User does not exist.' });
    expect(screen.getByText('User does not exist.')).toBeInTheDocument();
  });

  it('renders toast with role=alert', () => {
    renderMainScreen({ errorMessage: 'Something went wrong.' });
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});

describe('MainScreen — InCall view', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders peer canvas in session', () => {
    const { container } = renderMainScreen({ roomId: 'XY123' });
    expect(container.querySelector('.incall-peer-canvas')).toBeInTheDocument();
  });

  it('renders room ID in session', () => {
    renderMainScreen({ roomId: 'XY123' });
    expect(screen.getByText('XY123')).toBeInTheDocument();
  });

  it('renders Leave button in session', () => {
    renderMainScreen({ roomId: 'XY123' });
    expect(screen.getByTitle('Leave session')).toBeInTheDocument();
  });

  it('renders camera toggle in session', () => {
    renderMainScreen({ roomId: 'XY123' });
    expect(screen.getByTitle('Turn camera off')).toBeInTheDocument();
  });

  it('renders mic toggle in session', () => {
    renderMainScreen({ roomId: 'XY123' });
    expect(screen.getByTitle('Mute microphone')).toBeInTheDocument();
  });

  it('shows Camera Off label when camera is off', () => {
    renderMainScreen({ roomId: 'XY123', cameraOn: false });
    expect(screen.getByText('Camera Off')).toBeInTheDocument();
  });

  it('shows Muted label when muted', () => {
    renderMainScreen({ roomId: 'XY123', muted: true });
    expect(screen.getByText('Muted')).toBeInTheDocument();
  });

  it('hides Header during in-call', () => {
    renderMainScreen({ roomId: 'XY123' });
    expect(screen.queryByAltText('UCSD Logo')).not.toBeInTheDocument();
  });

  it('shows elapsed timer', () => {
    renderMainScreen({ roomId: 'XY123' });
    expect(screen.getByText('00:00')).toBeInTheDocument();
  });
});
