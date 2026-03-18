/**
 * Toast — Auto-dismissing notification overlay.
 *
 * Appears from the top, auto-hides after a timeout.
 * Used for error messages instead of the old side panel.
 */
import { useState, useEffect, useRef } from 'react';
import './Toast.css';

interface ToastProps {
  message: string;
  duration?: number;
  onDismiss: () => void;
}

export default function Toast({ message, duration = 5000, onDismiss }: ToastProps) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (!message) return;
    setVisible(true);

    timerRef.current = setTimeout(() => {
      setVisible(false);
      setTimeout(onDismiss, 300); // wait for fade-out animation
    }, duration);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [message, duration, onDismiss]);

  if (!message) return null;

  return (
    <div
      className={`toast ${visible ? 'toast--visible' : 'toast--hidden'}`}
      role="alert"
      onClick={() => {
        setVisible(false);
        setTimeout(onDismiss, 300);
      }}
    >
      <span className="toast-message">{message}</span>
      <span className="toast-dismiss" aria-label="Dismiss">&times;</span>
    </div>
  );
}
