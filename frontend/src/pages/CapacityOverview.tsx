import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCapacity } from '../hooks/useCapacity';
import { getWaitlist } from '../api/endpoints';
import { WaitlistEntry } from '../api/types';
import { useWebSocketEvent } from '../api/websocket';
import { KpiTile } from '../components/common/KpiTile';
import { DepartmentCard } from '../components/common/DepartmentCard';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';

export const CapacityOverview: React.FC = () => {
  const navigate = useNavigate();
  const { capacity, loading, error, refetch: refetchCapacity } = useCapacity();
  const [waitlist, setWaitlist] = useState<WaitlistEntry[]>([]);
  const [waitlistLoading, setWaitlistLoading] = useState<boolean>(true);

  const fetchWaitlist = useCallback(async () => {
    setWaitlistLoading(true);
    try {
      const res = await getWaitlist({ status: 'WAITING', limit: 5 });
      setWaitlist(res.data);
    } catch {
      // Handled silently for preview or display empty
    } finally {
      setWaitlistLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWaitlist();
  }, [fetchWaitlist]);

  // Refetch waitlist preview when waitlist changes
  useWebSocketEvent(['WAITLIST_UPDATED', 'MATCH_ASSIGNED'], () => {
    fetchWaitlist();
  });

  if (loading && !capacity) {
    return <LoadingState message="Loading hospital capacity intelligence..." />;
  }

  if (error && !capacity) {
    return (
      <ErrorState
        title="Failed to Load Capacity Overview"
        message={`Backend returned: ${error}`}
        onRetry={refetchCapacity}
      />
    );
  }

  if (!capacity) return null;

  const totalWaiting =
    (capacity.queues?.waitingForBeds ?? 0) +
    (capacity.queues?.waitingForTheatres ?? 0) +
    (capacity.queues?.waitingForStaff ?? 0);

  const occupancy = capacity.overallOccupancyPercentage ?? 0;
  const alertLevel = capacity.overallAlertLevel || 'NORMAL';
  const criticalDepts = capacity.criticalCapacityDepartments || [];
  const highUtilDepts = capacity.highUtilizationDepartments || [];
  const beds = capacity.beds || { total: 0, available: 0, occupied: 0, cleaning: 0, maintenance: 0 };
  const theatres = capacity.theatres || {
    total: 0,
    available: 0,
    inUse: 0,
    cleaning: 0,
    unavailable: 0,
    bookedSlots: 0,
    availableSlots: 0,
    nextAvailableSlot: null,
  };
  const staff = capacity.staff || { total: 0, available: 0, assigned: 0, offDuty: 0 };
  const queues = capacity.queues || { waitingForBeds: 0, waitingForTheatres: 0, waitingForStaff: 0 };
  const deptMetrics = capacity.departmentMetrics || [];

  return (
    <div className="flex flex-col gap-lg">
      {/* 1. Operational System Status Banner */}
      <section
        className="card flex items-center justify-between"
        style={{
          padding: 'var(--space-md) var(--space-lg)',
          backgroundColor:
            alertLevel === 'CRITICAL_CAPACITY'
              ? 'var(--color-error-bg)'
              : alertLevel === 'HIGH_UTILIZATION'
              ? '#fef3c7'
              : 'var(--surface-container-low)',
          borderColor:
            alertLevel === 'CRITICAL_CAPACITY'
              ? '#fca5a5'
              : alertLevel === 'HIGH_UTILIZATION'
              ? '#fde68a'
              : 'var(--outline-variant)',
        }}
      >
        <div className="flex items-center gap-md">
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: 'var(--radius-md)',
              backgroundColor:
                alertLevel === 'CRITICAL_CAPACITY'
                  ? 'var(--color-error)'
                  : alertLevel === 'HIGH_UTILIZATION'
                  ? 'var(--color-cleaning)'
                  : 'var(--color-available)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '24px' }}>
              {alertLevel === 'NORMAL' ? 'check_circle' : 'warning'}
            </span>
          </div>

          <div>
            <div className="flex items-center gap-sm">
              <span className="text-headline-sm" style={{ fontWeight: 700 }}>
                OVERALL CAPACITY STATUS: {alertLevel.replace('_', ' ')}
              </span>
              <StatusBadge status={alertLevel} />
            </div>
            <p className="text-body-md" style={{ color: 'var(--on-surface-variant)', marginTop: '2px' }}>
              Hospital Occupancy is at{' '}
              <strong>{occupancy.toFixed(1)}%</strong> ({capacity.occupiedBeds ?? 0} of{' '}
              {capacity.totalBeds ?? 0} operational beds occupied).
              {criticalDepts.length > 0 && (
                <span style={{ color: 'var(--color-error)', fontWeight: 600, marginLeft: '6px' }}>
                  Critical capacity in: {criticalDepts.join(', ')}.
                </span>
              )}
              {highUtilDepts.length > 0 && (
                <span style={{ color: '#b45309', fontWeight: 600, marginLeft: '6px' }}>
                  High utilization in: {highUtilDepts.join(', ')}.
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-sm">
          <button className="btn btn-outline btn-sm" onClick={refetchCapacity}>
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
              refresh
            </span>
            Refresh State
          </button>
        </div>
      </section>

      {/* 2. 8-KPI Tiles Grid */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
          gap: 'var(--space-md)',
        }}
      >
        <KpiTile
          label="Hospital Occupancy"
          value={`${occupancy.toFixed(1)}%`}
          subtext={`${capacity.occupiedBeds ?? 0}/${capacity.totalBeds ?? 0} beds`}
          icon="show_chart"
          variant={
            occupancy >= 90
              ? 'danger'
              : occupancy >= 80
              ? 'warning'
              : 'primary'
          }
        />
        <KpiTile
          label="Available Beds"
          value={beds.available}
          subtext="Ready for admission"
          icon="check_circle"
          variant="default"
        />
        <KpiTile
          label="Occupied Beds"
          value={beds.occupied}
          subtext="Admitted patients"
          icon="airline_seat_flat"
          variant="secondary"
        />
        <KpiTile
          label="Cleaning In-Progress"
          value={beds.cleaning}
          subtext="Turnaround queue"
          icon="autorenew"
          variant="warning"
        />
        <KpiTile
          label="Maintenance / Out"
          value={beds.maintenance}
          subtext="Temporarily offline"
          icon="build"
          variant="default"
        />
        <KpiTile
          label="Theatres Available"
          value={`${theatres.available} / ${theatres.total}`}
          subtext={`${theatres.bookedSlots} slots booked`}
          icon="medical_services"
          variant="secondary"
        />
        <KpiTile
          label="Staff on Shift"
          value={`${staff.assigned} / ${Math.max(0, staff.total - staff.offDuty)}`}
          subtext={`${staff.available} available to assign`}
          icon="badge"
          variant="default"
        />
        <KpiTile
          label="Waitlist Queue"
          value={totalWaiting}
          subtext={`${queues.waitingForBeds} bed, ${queues.waitingForTheatres} theatre`}
          icon="hourglass_empty"
          variant={totalWaiting > 0 ? 'warning' : 'default'}
        />
      </section>

      {/* 3. Department Utilization Cards Grid */}
      <section>
        <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-md)' }}>
          <div>
            <h2 className="text-headline-md" style={{ fontWeight: 700 }}>
              Department Capacity & Unit Occupancy
            </h2>
            <p className="text-body-sm" style={{ color: 'var(--on-surface-variant)' }}>
              Real-time operational distribution across all clinical wards
            </p>
          </div>
          <button
            className="btn btn-outline btn-sm"
            onClick={() => navigate('/resources')}
          >
            View All Resources
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
              arrow_forward
            </span>
          </button>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 'var(--space-lg)',
          }}
        >
          {deptMetrics.map((dept) => (
            <DepartmentCard
              key={dept.departmentId}
              dept={dept}
              onClick={() => navigate(`/resources?departmentId=${dept.departmentId}`)}
            />
          ))}
        </div>
      </section>

      {/* 4. Active Waitlist Preview */}
      <section className="card" style={{ padding: 'var(--space-lg)' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-md)' }}>
          <div>
            <h3 className="text-headline-sm" style={{ fontWeight: 700 }}>
              Active Priority Waitlist (Top Queue)
            </h3>
            <p className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
              Deterministic queue order (Priority 1 = STAT urgent). Matches resolved on resource release.
            </p>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => navigate('/patients?tab=waitlist')}
          >
            Manage Waitlist
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
              launch
            </span>
          </button>
        </div>

        {waitlistLoading && waitlist.length === 0 ? (
          <LoadingState message="Loading waitlist queue..." />
        ) : waitlist.length === 0 ? (
          <div
            style={{
              padding: 'var(--space-lg)',
              textAlign: 'center',
              color: 'var(--outline)',
              backgroundColor: 'var(--surface-container-low)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            No patients currently waiting in the queue.
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Queue #</th>
                  <th>Priority</th>
                  <th>Resource Needed</th>
                  <th>Patient ID</th>
                  <th>Dept #</th>
                  <th>Reason / Notes</th>
                  <th>Requested At</th>
                </tr>
              </thead>
              <tbody>
                {waitlist.map((entry, idx) => (
                  <tr key={entry.id}>
                    <td className="font-tabular" style={{ fontWeight: 600 }}>
                      #{idx + 1}
                    </td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          backgroundColor:
                            entry.priority === 1
                              ? 'var(--color-error-bg)'
                              : entry.priority === 2
                              ? '#fef3c7'
                              : 'var(--surface-container-low)',
                          color:
                            entry.priority === 1
                              ? 'var(--color-error-text)'
                              : entry.priority === 2
                              ? '#b45309'
                              : 'var(--on-surface-variant)',
                        }}
                      >
                        P{entry.priority} {entry.priority === 1 ? 'URGENT' : ''}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-neutral">{entry.resourceType}</span>
                      {entry.requiredBedType && (
                        <span className="text-label-sm" style={{ marginLeft: '6px', color: 'var(--outline)' }}>
                          ({entry.requiredBedType})
                        </span>
                      )}
                      {entry.requiredStaffRole && (
                        <span className="text-label-sm" style={{ marginLeft: '6px', color: 'var(--outline)' }}>
                          ({entry.requiredStaffRole})
                        </span>
                      )}
                    </td>
                    <td className="font-tabular">Patient #{entry.patientId}</td>
                    <td>Dept #{entry.departmentId}</td>
                    <td style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {entry.reason || 'Standard waitlist placement'}
                    </td>
                    <td className="text-label-sm font-tabular" style={{ color: 'var(--outline)' }}>
                      {new Date(entry.requestedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
