// import Ellipsis from "../../assets/ellipsis.png";
import Locked from '../../../../assets/Lock.svg';
import Unlock from '../../../../assets/Unlock.svg';

import './StatusWidget.css';

export default function StatusWidget(props) {
  function getStatusContext(status) {
    switch (status) {
      case 'waiting':
        return ['Establishing', <br />, 'Connection', <br />, '...'];

      case 'good':
        return ['Communcations', <br />, 'Secure', <img src={Locked} />];

      case 'bad':
        return ['Eavesdropper', <br />, 'Detected', <img src={Unlock} />];

      default:
        return '';
    }
  }

  return (
    <div className={`status-widget ${props.status}`}>
      {getStatusContext(props.status)}
    </div>
  );
}
