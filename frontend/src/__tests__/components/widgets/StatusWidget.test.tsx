import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import StatusWidget from '../../../renderer/components/widgets/StatusWidget';

describe('StatusWidget', () => {
  it('renders waiting status', () => {
    render(<StatusWidget status="waiting" />);
    expect(screen.getByText(/Establishing/)).toBeInTheDocument();
  });

  it('renders good status', () => {
    render(<StatusWidget status="good" />);
    expect(screen.getByText(/Secure/)).toBeInTheDocument();
  });

  it('renders bad status', () => {
    render(<StatusWidget status="bad" />);
    expect(screen.getByText(/Detected/)).toBeInTheDocument();
  });

  it('renders without status', () => {
    const { container } = render(<StatusWidget />);
    expect(container.firstChild).toBeTruthy();
  });
});
