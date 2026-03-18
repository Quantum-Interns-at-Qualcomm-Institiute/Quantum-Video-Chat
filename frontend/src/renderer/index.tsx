import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// Apply saved theme before first render so there's no flash of wrong theme.
// Reads the same key used by Settings.tsx.
try {
  const saved = localStorage.getItem('qvc-settings');
  const darkMode = saved ? JSON.parse(saved).darkMode !== false : true;
  document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
} catch (_) {
  document.documentElement.setAttribute('data-theme', 'dark');
}

const container = document.getElementById("root") as HTMLElement;
const root = createRoot(container);
root.render(<App />);
