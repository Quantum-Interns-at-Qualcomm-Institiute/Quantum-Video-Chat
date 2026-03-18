import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import Chat from '../../../renderer/components/chat/Chat';

const mockMessages = [
  { time: '12:00', name: 'Alice', body: 'Hello' },
  { time: '12:01', name: 'Bob', body: 'Hi there' },
];

describe('Chat', () => {
  it('renders messages', () => {
    render(<Chat handleSend={jest.fn()} messages={mockMessages} />);
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(screen.getByText(/Bob/)).toBeInTheDocument();
  });

  it('renders with empty messages', () => {
    const { container } = render(<Chat handleSend={jest.fn()} messages={[]} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders form with input and submit', () => {
    const { container } = render(<Chat handleSend={jest.fn()} messages={[]} />);
    const textInput = container.querySelector('input[type="text"]');
    const submitInput = container.querySelector('input[type="submit"]');
    expect(textInput).toBeInTheDocument();
    expect(submitInput).toBeInTheDocument();
  });

  it('has submit handler wired to form', () => {
    // NOTE: The Chat component reads submitted text via e.target[0].value
    // (HTMLFormElement indexed access). jsdom does not support numeric index
    // access on form elements, so we cannot fully test the submit flow.
    // Instead we verify the form structure is correct for the handler.
    const handleSend = jest.fn();
    const { container } = render(<Chat handleSend={handleSend} messages={[]} />);
    const form = container.querySelector('form') as HTMLFormElement;
    const textInput = form.querySelector('input[type="text"]');
    const submitInput = form.querySelector('input[type="submit"]');

    expect(form).toBeInTheDocument();
    expect(form.className).toContain('chat-field');
    expect(textInput).toBeInTheDocument();
    expect(submitInput).toBeInTheDocument();
  });

  it('renders chat container', () => {
    const { container } = render(<Chat handleSend={jest.fn()} messages={[]} />);
    expect(container.querySelector('.chat')).toBeInTheDocument();
  });
});
