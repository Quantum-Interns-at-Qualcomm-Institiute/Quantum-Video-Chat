import React from 'react';

interface IconProps {
  size?: number;
  className?: string;
}

export default function CameraOnIcon({ size = 18, className }: IconProps) {
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
      <rect x="2" y="5" width="14" height="14" rx="2" />
      <polygon points="22 5 16 9.5 16 14.5 22 19 22 5" />
    </svg>
  );
}
