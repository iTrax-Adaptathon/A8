import React from 'react';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'System Communication Error',
  message,
  onRetry,
}) => {
  return (
    <div
      className="card"
      style={{
        padding: 'var(--space-xl)',
        backgroundColor: 'var(--color-error-bg)',
        borderColor: '#fca5a5',
        margin: 'var(--space-md) 0',
      }}
    >
      <div className="flex items-start gap-md">
        <span
          className="material-symbols-outlined"
          style={{ fontSize: '28px', color: 'var(--color-error)' }}
        >
          error
        </span>
        <div style={{ flex: 1 }}>
          <h4 className="text-headline-sm" style={{ color: 'var(--color-error-text)', marginBottom: '4px' }}>
            {title}
          </h4>
          <p className="text-body-md" style={{ color: '#7f1d1d', marginBottom: onRetry ? 'var(--space-md)' : 0 }}>
            {message}
          </p>
          {onRetry && (
            <button className="btn btn-primary btn-sm" onClick={onRetry}>
              <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                refresh
              </span>
              Retry Request
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
