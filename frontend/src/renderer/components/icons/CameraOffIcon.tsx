import React from 'react';

interface IconProps {
  size?: number;
  className?: string;
}

export default function CameraOffIcon({ size = 18, className }: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <line x1="1" y1="1" x2="23" y2="23" />
      <path d="M16 16V5a2 2 0 0 0-2-2H5" />
      <rect x="2" y="5" width="14" height="14" rx="2" />
      <polygon points="22 5 16 9.5 16 14.5 22 19 22 5" />
    </svg>
  );
}
