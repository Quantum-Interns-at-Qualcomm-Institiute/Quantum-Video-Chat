import '@testing-library/jest-dom';
import { render, screen, fireEvent } from '@testing-library/react';
import Header from '../../renderer/components/Header';
import { ClientContext } from '../../renderer/utils/ClientContext';

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

function renderWithContext(ui: React.ReactElement, overrides: Partial<any> = {}) {
  return render(
    <ClientContext.Provider value={{ ...mockContextValue, ...overrides }}>
      {ui}
    </ClientContext.Provider>
  );
}

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

describe('Header', () => {
  it('renders the logo image', () => {
    renderWithContext(<Header />);
    const logo = screen.getByAltText('UCSD Logo');
    expect(logo).toBeInTheDocument();
  });

  it('renders without props', () => {
    const { container } = renderWithContext(<Header />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders theme toggle button', () => {
    renderWithContext(<Header />);
    const btn = screen.getByLabelText(/switch to light mode/i);
    expect(btn).toBeInTheDocument();
  });

  it('toggles theme on button click', () => {
    renderWithContext(<Header />);
    const btn = screen.getByLabelText(/switch to light mode/i);
    fireEvent.click(btn);
    expect(screen.getByLabelText(/switch to dark mode/i)).toBeInTheDocument();
  });

  it('shows idle state when not connected', () => {
    renderWithContext(<Header />);
    expect(screen.getByText('idle')).toBeInTheDocument();
  });

  it('shows ready state when server connected', () => {
    renderWithContext(<Header />, { serverConnected: true });
    expect(screen.getByText('ready')).toBeInTheDocument();
  });

  it('shows waiting state when waiting for peer', () => {
    renderWithContext(<Header />, { serverConnected: true, waitingForPeer: true });
    expect(screen.getByText('waiting')).toBeInTheDocument();
  });

  it('shows in session state when roomId is set', () => {
    renderWithContext(<Header />, { serverConnected: true, roomId: 'ABC12' });
    expect(screen.getByText('in session')).toBeInTheDocument();
  });
});
