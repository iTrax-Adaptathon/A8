import React from 'react';
import { DepartmentUtilization } from '../../api/types';
import { StatusBadge } from './StatusBadge';

interface DepartmentCardProps {
  dept: DepartmentUtilization;
  onClick?: () => void;
}

export const DepartmentCard: React.FC<DepartmentCardProps> = ({ dept, onClick }) => {
  const occPct = dept.totalBeds > 0 ? (dept.occupiedBeds / dept.totalBeds) * 100 : 0;
  const cleanPct = dept.totalBeds > 0 ? (dept.cleaningBeds / dept.totalBeds) * 100 : 0;
  const maintPct = dept.totalBeds > 0 ? (dept.maintenanceBeds / dept.totalBeds) * 100 : 0;
  const availPct = Math.max(0, 100 - occPct - cleanPct - maintPct);

  return (
    <div
      className={`card ${onClick ? 'card-interactive' : ''}`}
      style={{ padding: 'var(--space-md)' }}
      onClick={onClick}
    >
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-sm)' }}>
        <div>
          <div className="text-headline-sm" style={{ fontWeight: 600 }}>
            {dept.departmentName}
          </div>
          <div className="text-label-sm" style={{ color: 'var(--outline)' }}>
            Code: {dept.departmentCode} • Dept #{dept.departmentId}
          </div>
        </div>
        <StatusBadge status={dept.alertLevel} />
      </div>

      <div className="flex items-baseline justify-between" style={{ margin: 'var(--space-sm) 0 4px 0' }}>
        <span className="text-label-md" style={{ color: 'var(--on-surface-variant)' }}>
          Bed Occupancy
        </span>
        <span className="text-headline-sm font-tabular" style={{ fontWeight: 700, color: 'var(--primary)' }}>
          {dept.occupancyPercentage.toFixed(1)}%
        </span>
      </div>

      {/* Multi-segment Capacity Bar */}
      <div className="capacity-bar-track" style={{ height: '8px', marginBottom: 'var(--space-md)' }}>
        <div
          className="capacity-bar-fill-occupied"
          style={{ width: `${occPct}%` }}
          title={`Occupied: ${dept.occupiedBeds} beds (${occPct.toFixed(1)}%)`}
        />
        <div
          className="capacity-bar-fill-cleaning"
          style={{ width: `${cleanPct}%` }}
          title={`Cleaning: ${dept.cleaningBeds} beds (${cleanPct.toFixed(1)}%)`}
        />
        <div
          className="capacity-bar-fill-maintenance"
          style={{ width: `${maintPct}%` }}
          title={`Maintenance: ${dept.maintenanceBeds} beds (${maintPct.toFixed(1)}%)`}
        />
        <div
          className="capacity-bar-fill-available"
          style={{ width: `${availPct}%` }}
          title={`Available: ${dept.availableBeds} beds (${availPct.toFixed(1)}%)`}
        />
      </div>

      {/* Stat breakdown pills */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 'var(--space-xs)',
          textAlign: 'center',
          backgroundColor: 'var(--surface-container-low)',
          padding: 'var(--space-xs) var(--space-sm)',
          borderRadius: 'var(--radius-md)',
        }}
      >
        <div>
          <div className="text-label-sm font-tabular" style={{ fontWeight: 700, color: 'var(--color-available)' }}>
            {dept.availableBeds}
          </div>
          <div className="text-label-sm" style={{ fontSize: '10px', color: 'var(--outline)' }}>
            AVAIL
          </div>
        </div>
        <div>
          <div className="text-label-sm font-tabular" style={{ fontWeight: 700, color: 'var(--secondary)' }}>
            {dept.occupiedBeds}
          </div>
          <div className="text-label-sm" style={{ fontSize: '10px', color: 'var(--outline)' }}>
            OCCUPIED
          </div>
        </div>
        <div>
          <div className="text-label-sm font-tabular" style={{ fontWeight: 700, color: 'var(--color-cleaning)' }}>
            {dept.cleaningBeds}
          </div>
          <div className="text-label-sm" style={{ fontSize: '10px', color: 'var(--outline)' }}>
            CLEAN
          </div>
        </div>
        <div>
          <div className="text-label-sm font-tabular" style={{ fontWeight: 700, color: 'var(--outline)' }}>
            {dept.totalBeds}
          </div>
          <div className="text-label-sm" style={{ fontSize: '10px', color: 'var(--outline)' }}>
            TOTAL
          </div>
        </div>
      </div>
    </div>
  );
};
