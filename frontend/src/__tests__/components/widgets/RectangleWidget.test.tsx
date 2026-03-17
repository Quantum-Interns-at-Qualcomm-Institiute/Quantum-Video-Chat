import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import RectangleWidget from '../../../renderer/components/widgets/RectangleWidget';

describe('RectangleWidget', () => {
  it('renders topText', () => {
    render(
      <RectangleWidget topText="Label" status="good">
        Content
      </RectangleWidget>
    );
    expect(screen.getByText('Label')).toBeInTheDocument();
  });

  it('renders children', () => {
    render(
      <RectangleWidget topText="L" status="waiting">
        Hello
      </RectangleWidget>
    );
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('applies status CSS class', () => {
    const { container } = render(
      <RectangleWidget topText="L" status="bad">
        X
      </RectangleWidget>
    );
    expect(container.innerHTML).toContain('bad');
  });
});
