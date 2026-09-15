import React from 'react';
import { NavLink } from 'react-router-dom';
import { ACTOR_ID, ACTOR_NAME } from '../../api/client';
import { useWebSocketState } from '../../api/websocket';
import { useCapacity } from '../../hooks/useCapacity';
import { Logo } from '../common/Logo';

export const AppHeader: React.FC = () => {
  const wsState = useWebSocketState();
  const { capacity } = useCapacity();

  const occupancy = capacity?.overallOccupancyPercentage?.toFixed(1) ?? '—';
  const waitingBeds = capacity?.queues?.waitingForBeds ?? 0;
  const waitingTheatres = capacity?.queues?.waitingForTheatres ?? 0;
  const waitingStaff = capacity?.queues?.waitingForStaff ?? 0;
  const totalWaiting = waitingBeds + waitingTheatres + waitingStaff;
  const freeTheatres = capacity?.theatres?.available ?? '—';

  return (
    <header className="app-header">
      {/* Top Bar */}
      <div
        className="flex items-center justify-between"
        style={{
          height: '56px',
          padding: '0 var(--space-xl)',
          borderBottom: '1px solid var(--surface-container)',
        }}
      >
        {/* Left: Brand + Shift/Facility Context */}
        <div className="flex items-center gap-lg">
          <div className="flex items-center gap-sm">
            <Logo height={28} />
            <div className="flex flex-col" style={{ marginLeft: '-4px' }}>
              <span className="text-label-sm" style={{ color: 'var(--outline)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Clinical Ops
              </span>
            </div>
          </div>

          <div style={{ height: '20px', width: '1px', backgroundColor: 'var(--outline-variant)' }} />

          <div
            className="flex items-center gap-xs"
            style={{
              backgroundColor: 'var(--surface-container-low)',
              padding: '4px 10px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--surface-container)',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '16px', color: 'var(--primary)' }}>
              local_hospital
            </span>
            <span className="text-label-md" style={{ fontWeight: 600, color: 'var(--on-surface)' }}>
              Central Facility
            </span>
          </div>
        </div>

        {/* Right: Live WS State + Actor */}
        <div className="flex items-center gap-lg">
          {/* WebSocket Status */}
          <div
            className="flex items-center gap-xs"
            style={{
              backgroundColor: 'var(--surface-container-low)',
              padding: '4px 10px',
              borderRadius: 'var(--radius-full)',
              border: '1px solid var(--outline-variant)',
            }}
            title={`Realtime Channel: /api/v1/ws/capacity (${wsState})`}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor:
                  wsState === 'CONNECTED'
                    ? 'var(--color-available)'
                    : wsState === 'CONNECTING'
                    ? 'var(--color-cleaning)'
                    : 'var(--color-error)',
                display: 'inline-block',
                boxShadow:
                  wsState === 'CONNECTED' ? '0 0 6px var(--color-available)' : 'none',
              }}
            />
            <span
              className="text-label-sm"
              style={{
                fontWeight: 700,
                color:
                  wsState === 'CONNECTED'
                    ? 'var(--color-available)'
                    : wsState === 'CONNECTING'
                    ? 'var(--color-cleaning)'
                    : 'var(--color-error)',
              }}
            >
              {wsState === 'CONNECTED' ? 'LIVE' : wsState}
            </span>
          </div>

          <div style={{ height: '20px', width: '1px', backgroundColor: 'var(--outline-variant)' }} />

          {/* Actor Profile Indicator */}
          <div className="flex items-center gap-sm">
            <div style={{ textAlign: 'right' }}>
              <div className="text-label-md" style={{ fontWeight: 600, color: 'var(--on-surface)' }}>
                {ACTOR_NAME}
              </div>
              <div className="text-label-sm" style={{ color: 'var(--outline)' }}>
                ID: {ACTOR_ID}
              </div>
            </div>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: 'var(--primary)',
                color: 'var(--on-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
                person
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Bar: Main Nav & Live Summary Stats */}
      <div
        className="flex items-center justify-between"
        style={{
          height: '48px',
          padding: '0 var(--space-xl)',
        }}
      >
        {/* Navigation Tabs */}
        <nav className="flex items-center gap-xs">
          <NavLink
            to="/capacity"
            className={({ isActive }) => `tab-item ${isActive ? 'active' : ''}`}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
              dashboard
            </span>
            Capacity Overview
          </NavLink>
          <NavLink
            to="/resources"
            className={({ isActive }) => `tab-item ${isActive ? 'active' : ''}`}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
              bed
            </span>
            Resources (Beds, Theatres, Staff)
          </NavLink>
          <NavLink
            to="/patients"
            className={({ isActive }) => `tab-item ${isActive ? 'active' : ''}`}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
              personal_injury
            </span>
            Patient Flow (Patients, Waitlist)
          </NavLink>
          <NavLink
            to="/audit"
            className={({ isActive }) => `tab-item ${isActive ? 'active' : ''}`}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
              history
            </span>
            Audit History
          </NavLink>
        </nav>

        {/* Live Operational Metrics Ribbon */}
        <div
          className="flex items-center gap-md"
          style={{
            backgroundColor: 'var(--surface-container-low)',
            padding: '4px 12px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--outline-variant)',
          }}
        >
          <div className="flex items-baseline gap-xs">
            <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)', textTransform: 'uppercase' }}>
              Occupancy:
            </span>
            <span className="text-headline-sm font-tabular" style={{ fontWeight: 700, color: 'var(--primary)' }}>
              {occupancy}%
            </span>
          </div>

          <div style={{ height: '14px', width: '1px', backgroundColor: 'var(--outline-variant)' }} />

          <div className="flex items-baseline gap-xs">
            <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)', textTransform: 'uppercase' }}>
              Waiting:
            </span>
            <span
              className="text-headline-sm font-tabular"
              style={{
                fontWeight: 700,
                color: totalWaiting > 0 ? 'var(--color-cleaning)' : 'var(--color-available)',
              }}
            >
              {totalWaiting}
            </span>
          </div>

          <div style={{ height: '14px', width: '1px', backgroundColor: 'var(--outline-variant)' }} />

          <div className="flex items-baseline gap-xs">
            <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)', textTransform: 'uppercase' }}>
              Theatres:
            </span>
            <span className="text-headline-sm font-tabular" style={{ fontWeight: 700, color: 'var(--secondary)' }}>
              {freeTheatres} Free
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
