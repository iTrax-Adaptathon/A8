import React from 'react';

export const LoadingState: React.FC<{ message?: string }> = ({ message = 'Loading clinical data...' }) => {
  return (
    <div
      className="flex flex-col items-center justify-center"
      style={{ padding: 'var(--space-2xl)', minHeight: '200px', gap: 'var(--space-md)' }}
    >
      <span
        className="material-symbols-outlined"
        style={{
          fontSize: '36px',
          color: 'var(--primary)',
          animation: 'spin 1s linear infinite',
        }}
      >
        progress_activity
      </span>
      <span className="text-body-md" style={{ color: 'var(--on-surface-variant)' }}>
        {message}
      </span>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
