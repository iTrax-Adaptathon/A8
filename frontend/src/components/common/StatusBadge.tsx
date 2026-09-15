import React from 'react';

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const norm = (status || '').toUpperCase();

  let badgeClass = 'badge-neutral';
  let icon = 'info';

  switch (norm) {
    case 'AVAILABLE':
    case 'NORMAL':
    case 'FULFILLED':
    case 'COMPLETED':
    case 'ACTIVE':
      badgeClass = 'badge-available';
      icon = 'check_circle';
      break;
    case 'OCCUPIED':
    case 'IN_USE':
    case 'ADMITTED':
    case 'IN_PROGRESS':
    case 'ASSIGNED':
    case 'BOOKED':
      badgeClass = 'badge-occupied';
      icon = 'radio_button_checked';
      break;
    case 'CLEANING':
    case 'HIGH_UTILIZATION':
    case 'HIGH':
    case 'WAITING':
    case 'SCHEDULED':
      badgeClass = 'badge-cleaning';
      icon = 'autorenew';
      break;
    case 'MAINTENANCE':
    case 'UNAVAILABLE':
    case 'OFF_DUTY':
    case 'DISCHARGED':
    case 'CANCELLED':
    case 'RELEASED':
      badgeClass = 'badge-maintenance';
      icon = 'pause_circle';
      break;
    case 'CRITICAL_CAPACITY':
    case 'CRITICAL':
    case 'ERROR':
      badgeClass = 'badge-critical';
      icon = 'warning';
      break;
    case 'REGISTERED':
    case 'TRANSFERRED':
      badgeClass = 'badge-neutral';
      icon = 'schedule';
      break;
    default:
      badgeClass = 'badge-neutral';
      icon = 'info';
      break;
  }

  const label = norm.replace(/_/g, ' ');

  return (
    <span className={`badge ${badgeClass} ${className}`}>
      <span className="material-symbols-outlined" style={{ fontSize: '12px' }}>
        {icon}
      </span>
      {label}
    </span>
  );
};
