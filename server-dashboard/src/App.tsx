import { NavLink, Routes, Route, Navigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Users from './pages/Users';
import Logs from './pages/Logs';
import Config from './pages/Config';
import './App.css';

export default function App() {
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <h1 className="sidebar-title">QVC Admin</h1>
        <ul className="sidebar-nav">
          <li><NavLink to="/dashboard">Dashboard</NavLink></li>
          <li><NavLink to="/users">Users</NavLink></li>
          <li><NavLink to="/logs">Logs</NavLink></li>
          <li><NavLink to="/config">Config</NavLink></li>
        </ul>
      </nav>

      <main className="main-content">
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/users" element={<Users />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/config" element={<Config />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
