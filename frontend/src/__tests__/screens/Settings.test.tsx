import '@testing-library/jest-dom';
import { render, screen, fireEvent } from '@testing-library/react';
import Header from '../../renderer/components/Header';
import { ClientContext } from '../../renderer/utils/ClientContext';

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
  waitingForPeer: false,
  errorMessage: '',
  toggleCamera: jest.fn(),
  toggleMute: jest.fn(),
  joinRoom: jest.fn(),
  leaveRoom: jest.fn(),
  setOnFrame: jest.fn(),
  clearError: jest.fn(),
  connectToServer: jest.fn(),
  chat: { messages: [], sendMessage: jest.fn() },
};

function renderHeader() {
  return render(
    <ClientContext.Provider value={mockContextValue}>
      <Header />
    </ClientContext.Provider>
  );
}

describe('Settings (replaced by theme toggle)', () => {
  it('renders theme toggle instead of settings', () => {
    renderHeader();
    // No settings gear or overlay
    expect(screen.queryByText('Settings')).not.toBeInTheDocument();
    // Theme toggle exists
    expect(screen.getByLabelText(/switch to light mode/i)).toBeInTheDocument();
  });

  it('does not render settings overlay', () => {
    renderHeader();
    expect(screen.queryByText('Dark Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('Mute Microphone')).not.toBeInTheDocument();
  });

  it('toggles between light and dark mode', () => {
    renderHeader();
    const btn = screen.getByLabelText(/switch to light mode/i);
    fireEvent.click(btn);
    expect(screen.getByLabelText(/switch to dark mode/i)).toBeInTheDocument();
  });
});
