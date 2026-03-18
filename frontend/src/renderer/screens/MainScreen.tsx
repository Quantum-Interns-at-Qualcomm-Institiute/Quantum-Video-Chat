/**
 * MainScreen — Thin shell that switches between Lobby and InCall views.
 *
 * Responsibilities: conditional rendering + toast error display + header.
 */
import { useContext } from 'react';
import { ClientContext } from '../utils/ClientContext';

import Header from '../components/Header';
import Lobby from '../components/Lobby';
import InCall from '../components/InCall';
import Toast from '../components/Toast';

import './MainScreen.css';

export default function MainScreen() {
  const client = useContext(ClientContext);
  const inSession = !!client.roomId;

  return (
    <div className="main-screen">
      {!inSession && <Header />}

      <div className="main-body">
        {inSession ? <InCall /> : <Lobby />}
      </div>

      {client.errorMessage && (
        <Toast
          message={client.errorMessage}
          onDismiss={client.clearError}
        />
      )}
    </div>
  );
}
