import React from 'react';

export const AppFooter: React.FC = () => {
  return (
    <footer
      style={{
        borderTop: '1px solid var(--outline-variant)',
        backgroundColor: 'var(--surface-container-lowest)',
        padding: 'var(--space-md) var(--space-xl)',
        marginTop: 'auto',
      }}
    >
      <div
        className="flex items-center justify-between"
        style={{ maxWidth: '1680px', margin: '0 auto', width: '100%' }}
      >
        <div className="flex items-center gap-sm">
          <span className="text-label-sm" style={{ fontWeight: 600, color: 'var(--on-surface)' }}>
            FlowCare
          </span>
          <span className="text-label-sm" style={{ color: 'var(--outline)' }}>
            • Deterministic Hospital Capacity Orchestration
          </span>
        </div>
        <div className="flex items-center gap-md text-label-sm" style={{ color: 'var(--outline)' }}>
          <span>State Engine: SQLite / ACID Transacted</span>
          <span>•</span>
          <span>REST & WebSocket Synchronized</span>
        </div>
      </div>
    </footer>
  );
};
