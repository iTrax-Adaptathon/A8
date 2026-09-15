import React from 'react';

interface KpiTileProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon?: string;
  variant?: 'primary' | 'secondary' | 'warning' | 'danger' | 'default';
}

export const KpiTile: React.FC<KpiTileProps> = ({
  label,
  value,
  subtext,
  icon,
  variant = 'default',
}) => {
  let valueColor = 'var(--on-surface)';
  let iconColor = 'var(--outline)';

  if (variant === 'primary') {
    valueColor = 'var(--primary)';
    iconColor = 'var(--primary)';
  } else if (variant === 'secondary') {
    valueColor = 'var(--secondary)';
    iconColor = 'var(--secondary)';
  } else if (variant === 'warning') {
    valueColor = 'var(--color-cleaning)';
    iconColor = 'var(--color-cleaning)';
  } else if (variant === 'danger') {
    valueColor = 'var(--color-error)';
    iconColor = 'var(--color-error)';
  }

  return (
    <div className="kpi-tile">
      <div className="flex items-center justify-between">
        <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {label}
        </span>
        {icon && (
          <span className="material-symbols-outlined" style={{ fontSize: '18px', color: iconColor }}>
            {icon}
          </span>
        )}
      </div>
      <div className="text-display-md font-tabular" style={{ color: valueColor, fontWeight: 700, margin: '2px 0' }}>
        {value}
      </div>
      {subtext && (
        <span className="text-label-sm" style={{ color: 'var(--outline)' }}>
          {subtext}
        </span>
      )}
    </div>
  );
};
