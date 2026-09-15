import React, { useEffect } from 'react';

interface SidePanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export const SidePanel: React.FC<SidePanelProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="side-panel-overlay" onClick={onClose}>
      <div className="side-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div
          className="flex items-center justify-between"
          style={{
            padding: 'var(--space-md) var(--space-lg)',
            borderBottom: '1px solid var(--outline-variant)',
            backgroundColor: 'var(--surface-container-low)',
          }}
        >
          <div>
            <h3 className="text-headline-sm" style={{ fontWeight: 600 }}>
              {title}
            </h3>
            {subtitle && (
              <p className="text-label-sm" style={{ color: 'var(--outline)' }}>
                {subtitle}
              </p>
            )}
          </div>
          <button
            className="btn btn-outline btn-sm"
            onClick={onClose}
            style={{ padding: '4px', border: 'none', background: 'transparent' }}
            title="Close"
          >
            <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>
              close
            </span>
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: 'var(--space-lg)', flex: 1, overflowY: 'auto' }}>
          {children}
        </div>
      </div>
    </div>
  );
};
