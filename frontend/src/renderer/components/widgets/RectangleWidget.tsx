import './RectangleWidget.css';

type WidgetStatus = 'waiting' | 'good' | 'bad';

interface RectangleWidgetProps {
  topText:   string;
  status:    WidgetStatus;
  children?: React.ReactNode;
}

export default function RectangleWidget({ topText, status, children }: RectangleWidgetProps) {
  return (
    <div className="rectangle-widget">
      <div>{topText}</div>
      <div className={`rectangle ${status}`}>{children}</div>
    </div>
  );
}