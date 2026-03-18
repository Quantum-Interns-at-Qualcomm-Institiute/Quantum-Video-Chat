import Locked from '../../../../assets/Lock.svg';
import Unlock from '../../../../assets/Unlock.svg';

import './StatusWidget.css';

type WidgetStatus = 'waiting' | 'good' | 'bad';

interface StatusWidgetProps {
  status: WidgetStatus;
}

const STATUS_CONTENT: Record<WidgetStatus, React.ReactNode[]> = {
  waiting: ['Establishing', <br key="b1" />, 'Connection', <br key="b2" />, '...'],
  good:    ['Communications', <br key="b1" />, 'Secure', <img key="icon" src={Locked} alt="Locked" />],
  bad:     ['Eavesdropper', <br key="b1" />, 'Detected', <img key="icon" src={Unlock} alt="Unlocked" />],
};

export default function StatusWidget({ status }: StatusWidgetProps) {
  return (
    <div className={`status-widget ${status}`}>
      {STATUS_CONTENT[status] ?? null}
    </div>
  );
}
