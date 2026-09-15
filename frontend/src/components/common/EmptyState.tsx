import React from 'react';

interface EmptyStateProps {
  title?: string;
  message?: string;
  icon?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No Records Found',
  message = 'There are no active records matching the current criteria.',
  icon = 'inbox',
}) => {
  return (
    <div
      className="card flex flex-col items-center justify-center"
      style={{
        padding: 'var(--space-2xl)',
        textAlign: 'center',
        backgroundColor: 'var(--surface-container-low)',
        borderColor: 'var(--outline-variant)',
        borderStyle: 'dashed',
      }}
    >
      <span
        className="material-symbols-outlined"
        style={{ fontSize: '40px', color: 'var(--outline)', marginBottom: 'var(--space-sm)' }}
      >
        {icon}
      </span>
      <div className="text-headline-sm" style={{ color: 'var(--on-surface)', marginBottom: '4px' }}>
        {title}
      </div>
      <div className="text-body-sm" style={{ color: 'var(--on-surface-variant)', maxWidth: '400px' }}>
        {message}
      </div>
    </div>
  );
};
