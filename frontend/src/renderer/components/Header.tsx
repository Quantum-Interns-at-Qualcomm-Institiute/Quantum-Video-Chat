import { useContext, useState, useEffect } from 'react';
import { ClientContext } from '../utils/ClientContext';
import { getStoredTheme, applyTheme, getLogoVisible, setLogoVisible as persistLogoVisible } from '../utils/theme';
import SunIcon from './icons/SunIcon';
import MoonIcon from './icons/MoonIcon';
import ImageIcon from './icons/ImageIcon';
import Logo from '../../../assets/Logo.png';
import './Header.css';

export default function Header() {
  const { middlewareConnected, serverConnected, waitingForPeer, roomId } = useContext(ClientContext);
  const [darkMode, setDarkMode] = useState(() => getStoredTheme() === 'dark');
  const [logoVisible, setLogoVisible] = useState(() => getLogoVisible());

  useEffect(() => {
    applyTheme(darkMode ? 'dark' : 'light');
  }, [darkMode]);

  const toggleLogo = () => {
    const next = !logoVisible;
    setLogoVisible(next);
    persistLogoVisible(next);
  };

  // Derive session state label
  let stateLabel = 'idle';
  if (roomId)               stateLabel = 'in session';
  else if (waitingForPeer)  stateLabel = 'waiting';
  else if (serverConnected) stateLabel = 'ready';

  return (
    <div className="header">
      <div className="header-left">
        {logoVisible && <img src={Logo} alt="UCSD Logo" id="logo" />}
      </div>
      <div className="header-right">
        <div className="conn-status">
          <span
            className={`conn-dot ${middlewareConnected ? 'conn-dot--ok' : 'conn-dot--off'}`}
            title={middlewareConnected ? 'Middleware connected' : 'Middleware disconnected'}
          />
          <span className="conn-label">middleware</span>

          <span className="conn-sep">&middot;</span>

          <span
            className={`conn-dot ${
              serverConnected       ? 'conn-dot--ok'   :
              middlewareConnected   ? 'conn-dot--idle'  :
                                     'conn-dot--off'
            }`}
            title={serverConnected ? 'QKD server connected' : 'QKD server not connected'}
          />
          <span className="conn-label">server</span>

          <span className="conn-sep">&middot;</span>

          <span className={`conn-state conn-state--${stateLabel.replace(/\s/g, '-')}`}>
            {stateLabel}
          </span>
        </div>

        <button
          className="header-theme-btn"
          onClick={toggleLogo}
          aria-label={logoVisible ? 'Hide logo' : 'Show logo'}
          title={logoVisible ? 'Hide logo' : 'Show logo'}
        >
          <ImageIcon size={16} />
        </button>

        <button
          className="header-theme-btn"
          onClick={() => setDarkMode((prev) => !prev)}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          title={darkMode ? 'Light mode' : 'Dark mode'}
        >
          {darkMode ? <SunIcon size={16} /> : <MoonIcon size={16} />}
        </button>
      </div>
    </div>
  );
}
