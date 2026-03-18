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

function makeContext(overrides: Partial<any> = {}) {
  return {
    middlewareConnected: true,
    serverConnected: true,
    userId: '',
    status: 'waiting',
    roomId: 'test-room-42',
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

describe('Session (InCall view)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders room ID from context', () => {
    renderMainScreen({ roomId: 'my-room-123' });
    expect(screen.getByText('my-room-123')).toBeInTheDocument();
  });

  it('renders canvas for peer video', () => {
    const { container } = renderMainScreen();
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeInTheDocument();
  });

  it('renders camera toggle', () => {
    renderMainScreen();
    expect(screen.getByText('Camera')).toBeInTheDocument();
  });

  it('renders mic toggle', () => {
    renderMainScreen();
    expect(screen.getByText('Mic')).toBeInTheDocument();
  });

  it('renders Leave button', () => {
    renderMainScreen();
    expect(screen.getByText('Leave')).toBeInTheDocument();
  });

  it('does not render Accumulated Secret Key widget', () => {
    renderMainScreen();
    expect(screen.queryByText('Accumulated Secret Key')).not.toBeInTheDocument();
  });

  it('does not render Key Rate widget', () => {
    renderMainScreen();
    expect(screen.queryByText('Key Rate')).not.toBeInTheDocument();
  });

  it('does not render Error Rate widget', () => {
    renderMainScreen();
    expect(screen.queryByText('Error Rate %')).not.toBeInTheDocument();
  });

  it('hides Header during in-call', () => {
    renderMainScreen();
    expect(screen.queryByAltText('UCSD Logo')).not.toBeInTheDocument();
  });

  it('shows elapsed timer', () => {
    renderMainScreen();
    expect(screen.getByText('00:00')).toBeInTheDocument();
  });
});
