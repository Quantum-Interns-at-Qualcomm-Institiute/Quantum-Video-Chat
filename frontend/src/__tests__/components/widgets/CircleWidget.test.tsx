import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import CircleWidget from '../../../renderer/components/widgets/CircleWidget';

describe('CircleWidget', () => {
  it('renders topText and bottomText', () => {
    render(
      <CircleWidget topText="Top" bottomText="Bottom" status="good">
        42
      </CircleWidget>
    );
    expect(screen.getByText('Top')).toBeInTheDocument();
    expect(screen.getByText('Bottom')).toBeInTheDocument();
  });

  it('renders children in circle', () => {
    render(
      <CircleWidget topText="T" bottomText="B" status="waiting">
        99
      </CircleWidget>
    );
    expect(screen.getByText('99')).toBeInTheDocument();
  });

  it('applies status CSS class', () => {
    const { container } = render(
      <CircleWidget topText="T" bottomText="B" status="bad">
        0
      </CircleWidget>
    );
    expect(container.innerHTML).toContain('bad');
  });
});
