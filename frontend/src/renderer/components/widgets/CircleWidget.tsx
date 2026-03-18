import './CircleWidget.css';

type WidgetStatus = 'waiting' | 'good' | 'bad';

interface CircleWidgetProps {
  topText:     string;
  bottomText:  string;
  status:      WidgetStatus;
  children?:   React.ReactNode;
}

export default function CircleWidget({ topText, bottomText, status, children }: CircleWidgetProps) {
  return (
    <div className="circle-widget">
      <div>{topText}</div>
      <div className={`circle ${status}`}>{children}</div>
      <div>{bottomText}</div>
    </div>
  );
}