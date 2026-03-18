/**
 * Toast — Auto-dismissing notification overlay.
 *
 * Uses ui-kit toast classes for positioning and animation.
 * Appears from the top, auto-hides after a timeout.
 */
import { useState, useEffect, useRef } from 'react';
import './Toast.css';

interface ToastProps {
  message: string;
  type?: 'error' | 'success';
  duration?: number;
  onDismiss: () => void;
}

export default function Toast({ message, type = 'error', duration = 5000, onDismiss }: ToastProps) {
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

  const variant = type === 'success' ? 'ui-toast-success' : 'ui-toast-error';

  return (
    <div className="ui-toast-container">
      <div
        className={`ui-toast ${variant} ${visible ? 'visible' : ''}`}
        role="alert"
        onClick={() => {
          setVisible(false);
          setTimeout(onDismiss, 300);
        }}
      >
        <span>{message}</span>
        <button className="ui-toast-dismiss" aria-label="Dismiss">&times;</button>
      </div>
    </div>
  );
}
