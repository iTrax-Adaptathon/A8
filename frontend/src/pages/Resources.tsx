import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useCapacity } from '../hooks/useCapacity';
import { ResourcesBeds } from './resources/ResourcesBeds';
import { ResourcesTheatres } from './resources/ResourcesTheatres';
import { ResourcesStaff } from './resources/ResourcesStaff';

export const Resources: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = searchParams.get('tab') || 'beds';
  const deptParam = searchParams.get('departmentId');
  const initialDeptId = deptParam ? parseInt(deptParam, 10) : undefined;

  const { capacity } = useCapacity();
  const [activeTab, setActiveTab] = useState<string>(currentTab);

  useEffect(() => {
    const tab = searchParams.get('tab') || 'beds';
    setActiveTab(tab);
  }, [searchParams]);

  const handleSwitchTab = (tab: string) => {
    setActiveTab(tab);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', tab);
      return next;
    });
  };

  const bedCount = capacity?.beds?.total ?? 0;
  const theatreCount = capacity?.theatres?.total ?? 0;
  const staffCount = capacity?.staff?.total ?? 0;

  return (
    <div className="flex flex-col gap-lg">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-headline-lg" style={{ fontWeight: 700 }}>
            Hospital Resources & Capacity Allocation
          </h1>
          <p className="text-body-sm" style={{ color: 'var(--on-surface-variant)' }}>
            Real-time control over physical beds, surgical theatres, operating slots, and clinical staff
          </p>
        </div>
      </div>

      {/* Sub-tab Navigation */}
      <div className="tab-bar">
        <button
          className={`tab-item ${activeTab === 'beds' ? 'active' : ''}`}
          onClick={() => handleSwitchTab('beds')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
            hotel
          </span>
          Beds Inventory
          <span
            className="badge badge-neutral"
            style={{
              fontSize: '11px',
              backgroundColor: activeTab === 'beds' ? 'rgba(255,255,255,0.2)' : undefined,
              color: activeTab === 'beds' ? '#ffffff' : undefined,
            }}
          >
            {bedCount}
          </span>
        </button>

        <button
          className={`tab-item ${activeTab === 'theatres' ? 'active' : ''}`}
          onClick={() => handleSwitchTab('theatres')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
            medical_services
          </span>
          Operating Theatres & Slots
          <span
            className="badge badge-neutral"
            style={{
              fontSize: '11px',
              backgroundColor: activeTab === 'theatres' ? 'rgba(255,255,255,0.2)' : undefined,
              color: activeTab === 'theatres' ? '#ffffff' : undefined,
            }}
          >
            {theatreCount}
          </span>
        </button>

        <button
          className={`tab-item ${activeTab === 'staff' ? 'active' : ''}`}
          onClick={() => handleSwitchTab('staff')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
            badge
          </span>
          Clinical Staff Directory
          <span
            className="badge badge-neutral"
            style={{
              fontSize: '11px',
              backgroundColor: activeTab === 'staff' ? 'rgba(255,255,255,0.2)' : undefined,
              color: activeTab === 'staff' ? '#ffffff' : undefined,
            }}
          >
            {staffCount}
          </span>
        </button>
      </div>

      {/* Render Active Sub-view */}
      {activeTab === 'beds' && <ResourcesBeds initialDepartmentId={initialDeptId} />}
      {activeTab === 'theatres' && <ResourcesTheatres />}
      {activeTab === 'staff' && <ResourcesStaff />}
    </div>
  );
};
