import React, { useState, useEffect, useCallback } from 'react';
import { getFlowEvents, getDepartments } from '../api/endpoints';
import {
  FlowEvent,
  Department,
  FlowEventType,
  ResourceType,
} from '../api/types';
import { useWebSocketEvent } from '../api/websocket';
import { StatusBadge } from '../components/common/StatusBadge';
import { SidePanel } from '../components/common/SidePanel';
import { Pagination } from '../components/common/Pagination';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';

export const AuditHistory: React.FC = () => {
  const [events, setEvents] = useState<FlowEvent[]>([]);
  const [totalCount, setTotalCount] = useState<number | undefined>(undefined);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination
  const [limit] = useState<number>(25);
  const [offset, setOffset] = useState<number>(0);
  const [selectedEventType, setSelectedEventType] = useState<string>('');
  const [selectedResourceType, setSelectedResourceType] = useState<string>('');
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [filterPatientId, setFilterPatientId] = useState<string>('');

  // Selected event for detail inspection
  const [selectedEvent, setSelectedEvent] = useState<FlowEvent | null>(null);

  useEffect(() => {
    getDepartments().then(setDepartments).catch(() => {});
  }, []);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getFlowEvents({
        eventType: (selectedEventType as FlowEventType) || undefined,
        resourceType: (selectedResourceType as ResourceType) || undefined,
        departmentId: selectedDept ? Number(selectedDept) : undefined,
        patientId: filterPatientId ? Number(filterPatientId) : undefined,
        limit,
        offset,
      });
      setEvents(res.data);
      setTotalCount(res.totalCount);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [selectedEventType, selectedResourceType, selectedDept, filterPatientId, limit, offset]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // WebSocket targeted refresh when state updates happen
  useWebSocketEvent('*', () => {
    fetchEvents();
  });

  const getDeptName = (deptId?: number | null) => {
    if (!deptId) return '—';
    const d = departments.find((dept) => dept.id === deptId);
    return d ? `${d.name} (${d.code})` : `Dept #${deptId}`;
  };

  return (
    <div className="flex flex-col gap-lg">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-headline-lg" style={{ fontWeight: 700 }}>
            System Audit Trail &amp; Flow Events
          </h1>
          <p className="text-body-sm" style={{ color: 'var(--on-surface-variant)' }}>
            Immutable, append-only operational event ledger with actor provenance and state transitions
          </p>
        </div>

        <button className="btn btn-outline btn-sm" onClick={fetchEvents}>
          <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
            refresh
          </span>
          Refresh Audit Log
        </button>
      </div>

      {/* Filter Toolbar */}
      <div
        className="card flex items-center justify-between"
        style={{ padding: 'var(--space-sm) var(--space-md)', flexWrap: 'wrap', gap: 'var(--space-sm)' }}
      >
        <div className="flex items-center gap-sm" style={{ flexWrap: 'wrap' }}>
          <div style={{ minWidth: '180px' }}>
            <select
              className="select-control"
              value={selectedEventType}
              onChange={(e) => {
                setSelectedEventType(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All Event Types</option>
              <option value="ADMISSION">ADMISSION</option>
              <option value="TRANSFER">TRANSFER</option>
              <option value="DISCHARGE">DISCHARGE</option>
              <option value="BED_STATUS_CHANGE">BED_STATUS_CHANGE</option>
              <option value="BED_RELEASE">BED_RELEASE</option>
              <option value="THEATRE_STATUS_CHANGE">THEATRE_STATUS_CHANGE</option>
              <option value="THEATRE_SLOT_CREATED">THEATRE_SLOT_CREATED</option>
              <option value="THEATRE_SLOT_BOOKED">THEATRE_SLOT_BOOKED</option>
              <option value="THEATRE_SLOT_RELEASED">THEATRE_SLOT_RELEASED</option>
              <option value="THEATRE_SLOT_CANCELLED">THEATRE_SLOT_CANCELLED</option>
              <option value="SURGERY_SCHEDULED">SURGERY_SCHEDULED</option>
              <option value="SURGERY_STARTED">SURGERY_STARTED</option>
              <option value="SURGERY_COMPLETED">SURGERY_COMPLETED</option>
              <option value="STAFF_STATUS_CHANGE">STAFF_STATUS_CHANGE</option>
              <option value="STAFF_ASSIGNED">STAFF_ASSIGNED</option>
              <option value="STAFF_RELEASED">STAFF_RELEASED</option>
              <option value="WAITLIST_ADDED">WAITLIST_ADDED</option>
              <option value="WAITLIST_FULFILLED">WAITLIST_FULFILLED</option>
              <option value="MATCH_IDENTIFIED">MATCH_IDENTIFIED</option>
              <option value="ASSIGNMENT_REJECTED">ASSIGNMENT_REJECTED</option>
            </select>
          </div>

          <div style={{ minWidth: '160px' }}>
            <select
              className="select-control"
              value={selectedResourceType}
              onChange={(e) => {
                setSelectedResourceType(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All Resource Types</option>
              <option value="BED">BED</option>
              <option value="PATIENT">PATIENT</option>
              <option value="THEATRE">THEATRE</option>
              <option value="THEATRE_SLOT">THEATRE_SLOT</option>
              <option value="SURGERY">SURGERY</option>
              <option value="STAFF">STAFF</option>
              <option value="WAITLIST_ENTRY">WAITLIST_ENTRY</option>
            </select>
          </div>

          <div style={{ minWidth: '170px' }}>
            <select
              className="select-control"
              value={selectedDept}
              onChange={(e) => {
                setSelectedDept(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All Departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.code})
                </option>
              ))}
            </select>
          </div>

          <div style={{ width: '150px' }}>
            <input
              type="number"
              className="input-text"
              placeholder="Patient ID..."
              value={filterPatientId}
              onChange={(e) => {
                setFilterPatientId(e.target.value);
                setOffset(0);
              }}
            />
          </div>

          {(selectedEventType || selectedResourceType || selectedDept || filterPatientId) && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => {
                setSelectedEventType('');
                setSelectedResourceType('');
                setSelectedDept('');
                setFilterPatientId('');
                setOffset(0);
              }}
            >
              Reset
            </button>
          )}
        </div>

        <div className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Total logged events: <strong className="font-tabular">{totalCount ?? events.length}</strong>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={fetchEvents} />}

      {/* Events Table */}
      {loading && events.length === 0 ? (
        <LoadingState message="Loading immutable audit log..." />
      ) : events.length === 0 ? (
        <div className="card" style={{ padding: 'var(--space-2xl)', textAlign: 'center', color: 'var(--outline)' }}>
          No audit events found matching the selected filters.
        </div>
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="table-container" style={{ border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp (UTC)</th>
                  <th>Event Type</th>
                  <th>Resource / ID</th>
                  <th>Patient</th>
                  <th>Department</th>
                  <th>State Transition</th>
                  <th>Actor Provenance</th>
                  <th>Source</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr
                    key={e.id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelectedEvent(e)}
                  >
                    <td className="font-tabular text-label-sm" style={{ color: 'var(--outline)', whiteSpace: 'nowrap' }}>
                      {new Date(e.timestamp).toLocaleString([], {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>
                    <td>
                      <StatusBadge status={e.eventType} />
                    </td>
                    <td>
                      {e.resourceType ? (
                        <span className="badge badge-neutral" style={{ fontSize: '10px' }}>
                          {e.resourceType} #{e.resourceId}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="font-tabular">
                      {e.patientId ? `Patient #${e.patientId}` : '—'}
                    </td>
                    <td style={{ fontSize: '12px' }}>
                      {getDeptName(e.departmentId || e.toDepartmentId || e.fromDepartmentId)}
                    </td>
                    <td className="text-label-sm font-tabular">
                      {e.previousState || e.newState ? (
                        <span>
                          <strong style={{ color: 'var(--outline)' }}>{e.previousState || 'None'}</strong>
                          {' &rarr; '}
                          <strong style={{ color: 'var(--primary)' }}>{e.newState || 'None'}</strong>
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <div className="text-label-sm" style={{ fontWeight: 600 }}>
                        {e.actorName || e.actorId}
                      </div>
                      <div className="text-label-sm" style={{ color: 'var(--outline)', fontSize: '10px' }}>
                        {e.actorId}
                      </div>
                    </td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          backgroundColor:
                            e.source === 'AUTO_MATCH'
                              ? 'var(--secondary-fixed)'
                              : e.source === 'MANUAL'
                              ? 'var(--primary-fixed)'
                              : 'var(--surface-container-low)',
                          color:
                            e.source === 'AUTO_MATCH'
                              ? 'var(--secondary)'
                              : e.source === 'MANUAL'
                              ? 'var(--primary)'
                              : 'var(--outline)',
                          fontSize: '10px',
                        }}
                      >
                        {e.source}
                      </span>
                    </td>
                    <td
                      style={{
                        maxWidth: '220px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontSize: '12px',
                        color: 'var(--on-surface-variant)',
                      }}
                      title={e.notes}
                    >
                      {e.notes || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            totalCount={totalCount}
            limit={limit}
            offset={offset}
            onPageChange={setOffset}
          />
        </div>
      )}

      {/* Event Details SidePanel & JSON Inspector */}
      <SidePanel
        isOpen={selectedEvent !== null}
        onClose={() => setSelectedEvent(null)}
        title={selectedEvent ? `Event #${selectedEvent.id}: ${selectedEvent.eventType}` : ''}
        subtitle={selectedEvent ? new Date(selectedEvent.timestamp).toUTCString() : undefined}
      >
        {selectedEvent && (
          <div className="flex flex-col gap-lg">
            {/* Event Summary Card */}
            <div className="card" style={{ padding: 'var(--space-md)', backgroundColor: 'var(--surface-container-low)' }}>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Event Type:
                </span>
                <StatusBadge status={selectedEvent.eventType} />
              </div>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Event ID:
                </span>
                <span className="text-label-sm font-tabular">{selectedEvent.id}</span>
              </div>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Actor:
                </span>
                <span className="text-label-md" style={{ fontWeight: 600 }}>
                  {selectedEvent.actorName} ({selectedEvent.actorId})
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Trigger Source:
                </span>
                <span className="badge badge-neutral">{selectedEvent.source}</span>
              </div>
            </div>

            {/* Transition details */}
            <div className="card" style={{ padding: 'var(--space-md)' }}>
              <h4 className="text-label-lg" style={{ fontWeight: 600, marginBottom: 'var(--space-sm)' }}>
                State Transition &amp; Context
              </h4>
              <div className="flex flex-col gap-xs text-body-sm">
                <div>
                  <strong>Resource:</strong> {selectedEvent.resourceType || 'None'}{' '}
                  {selectedEvent.resourceId ? `#${selectedEvent.resourceId}` : ''}
                </div>
                {selectedEvent.patientId && (
                  <div>
                    <strong>Patient ID:</strong> #{selectedEvent.patientId}
                  </div>
                )}
                {selectedEvent.previousState && (
                  <div>
                    <strong>Previous State:</strong> {selectedEvent.previousState}
                  </div>
                )}
                {selectedEvent.newState && (
                  <div>
                    <strong>New State:</strong> {selectedEvent.newState}
                  </div>
                )}
                {selectedEvent.notes && (
                  <div style={{ marginTop: 'var(--space-xs)' }}>
                    <strong>Notes:</strong> {selectedEvent.notes}
                  </div>
                )}
              </div>
            </div>

            {/* Raw JSON Record Inspector */}
            <div className="card" style={{ padding: 'var(--space-md)' }}>
              <h4 className="text-label-lg" style={{ fontWeight: 600, marginBottom: 'var(--space-xs)' }}>
                Immutable Audit Payload
              </h4>
              <p className="text-label-sm" style={{ color: 'var(--outline)', marginBottom: 'var(--space-sm)' }}>
                Complete database record emitted strictly upon transaction commit
              </p>
              <pre
                style={{
                  backgroundColor: 'var(--surface-container-lowest)',
                  padding: 'var(--space-md)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--outline-variant)',
                  fontSize: '11px',
                  lineHeight: '1.4',
                  overflowX: 'auto',
                  maxHeight: '360px',
                  fontFamily: 'monospace',
                }}
              >
                {JSON.stringify(selectedEvent, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </SidePanel>
    </div>
  );
};
