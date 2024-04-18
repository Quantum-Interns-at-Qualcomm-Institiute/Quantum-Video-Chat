import { useNavigate } from 'react-router-dom';
import { MemoryRouter as Router, Routes, Route } from 'react-router-dom';
import Header from '../components/Header';

import './Start.css';

function Hello() {
  const navigate = useNavigate();

  const handleStart = () => {
    const code = Math.random().toString().slice(2, 10); // TODO: Remove this part entirely
    navigate(`/session/host/${code}`);
  };

  const handleJoin = () => {
    navigate('./join');
  };

  return (
    <>
      <Header />
      <div className="start-content">
        <div className="codeForm">
          {/* TODO: Make these buttons be components instead */}
          <button type="button" onClick={handleStart}>Start Session</button>
          <button type="button" onClick={handleJoin}>Join Session</button>
        </div>
      </div>
    </>
  );
}
export default function Start() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Hello />} />
      </Routes>
    </Router>
  );
}
