import React from 'react';

export const Logo: React.FC<{ height?: number; className?: string }> = ({ height = 32, className = '' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 160 40"
      height={height}
      className={className}
      fill="none"
    >
      <rect x="2" y="6" width="28" height="28" rx="7" fill="#0284C7" />
      <path d="M16 11V29M7 20H25" stroke="#FFFFFF" strokeWidth="3.5" strokeLinecap="round" />
      <circle cx="23" cy="13" r="3" fill="#38BDF8" />
      <text
        x="38"
        y="26"
        fontFamily="Inter, system-ui, sans-serif"
        fontSize="20"
        fontWeight="700"
        fill="#0F172A"
        letterSpacing="-0.5px"
      >
        Flow<tspan fill="#0284C7">Care</tspan>
      </text>
    </svg>
  );
};
