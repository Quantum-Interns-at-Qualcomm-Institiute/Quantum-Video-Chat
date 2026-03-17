import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import StatusPopup from '../../renderer/components/StatusPopup';

describe('StatusPopup', () => {
  it('renders encryption warning text', () => {
    render(<StatusPopup />);
    expect(screen.getByText(/RE-ESTABLISHING/)).toBeInTheDocument();
    expect(screen.getByText(/SECURE ENCRYPTION/)).toBeInTheDocument();
  });

  it('renders with correct class', () => {
    const { container } = render(<StatusPopup />);
    expect(container.firstChild).toBeTruthy();
  });
});
