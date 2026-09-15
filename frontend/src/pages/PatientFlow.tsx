import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useCapacity } from '../hooks/useCapacity';
import { PatientsList } from './patient_flow/PatientsList';
import { WaitlistView } from './patient_flow/WaitlistView';

export const PatientFlow: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = searchParams.get('tab') || 'patients';

  const { capacity } = useCapacity();
  const [activeTab, setActiveTab] = useState<string>(currentTab);

  useEffect(() => {
    const tab = searchParams.get('tab') || 'patients';
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

  const occupiedCount = capacity?.beds?.occupied ?? 0;
  const waitingCount =
    (capacity?.queues?.waitingForBeds ?? 0) +
    (capacity?.queues?.waitingForTheatres ?? 0) +
    (capacity?.queues?.waitingForStaff ?? 0);

  return (
    <div className="flex flex-col gap-lg">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-headline-lg" style={{ fontWeight: 700 }}>
            Patient Flow &amp; Transit Orchestration
          </h1>
          <p className="text-body-sm" style={{ color: 'var(--on-surface-variant)' }}>
            Hospital patient census, bed transit workflows, admission queue and deterministic match fulfillment
          </p>
        </div>
      </div>

      {/* Tab Selector */}
      <div className="tab-bar">
        <button
          className={`tab-item ${activeTab === 'patients' ? 'active' : ''}`}
          onClick={() => handleSwitchTab('patients')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
            people
          </span>
          Patient Census &amp; Transits
          <span
            className="badge badge-neutral"
            style={{
              fontSize: '11px',
              backgroundColor: activeTab === 'patients' ? 'rgba(255,255,255,0.2)' : undefined,
              color: activeTab === 'patients' ? '#ffffff' : undefined,
            }}
          >
            {occupiedCount} Admitted
          </span>
        </button>

        <button
          className={`tab-item ${activeTab === 'waitlist' ? 'active' : ''}`}
          onClick={() => handleSwitchTab('waitlist')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
            queue
          </span>
          Active Waitlist Queue
          <span
            className="badge badge-neutral"
            style={{
              fontSize: '11px',
              backgroundColor: activeTab === 'waitlist' ? 'rgba(255,255,255,0.2)' : undefined,
              color: activeTab === 'waitlist' ? '#ffffff' : undefined,
            }}
          >
            {waitingCount}
          </span>
        </button>
      </div>

      {/* Tab View */}
      {activeTab === 'patients' && <PatientsList />}
      {activeTab === 'waitlist' && <WaitlistView />}
    </div>
  );
};
