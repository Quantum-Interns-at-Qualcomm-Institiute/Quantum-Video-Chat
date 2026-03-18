import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import Message from '../../../renderer/components/chat/Message';

describe('Message', () => {
  it('renders formatted message', () => {
    render(
      <Message time="12:00" name="Alice">
        Hello world
      </Message>
    );
    expect(screen.getByText(/12:00/)).toBeInTheDocument();
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(screen.getByText(/Hello world/)).toBeInTheDocument();
  });

  it('returns null when time is missing', () => {
    const { container } = render(
      <Message time="" name="Alice">
        Hello
      </Message>
    );
    expect(container.innerHTML).toBe('');
  });

  it('returns null when name is missing', () => {
    const { container } = render(
      <Message time="12:00" name="">
        Hello
      </Message>
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders without children', () => {
    const { container } = render(
      <Message time="12:00" name="Alice" />
    );
    expect(container.firstChild).toBeTruthy();
  });
});
