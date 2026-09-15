import React, { useState, useEffect, useCallback } from 'react';
import {
  getWaitlist,
  cancelWaitlistEntry,
  getDepartments,
  getAvailableBeds,
  confirmMatch,
} from '../../api/endpoints';
import {
  WaitlistEntry,
  Department,
  Bed,
  WaitlistResourceType,
  WaitlistStatus,
} from '../../api/types';
import { useWebSocketEvent } from '../../api/websocket';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Pagination } from '../../components/common/Pagination';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';

export const WaitlistView: React.FC = () => {
  const [entries, setEntries] = useState<WaitlistEntry[]>([]);
  const [totalCount, setTotalCount] = useState<number | undefined>(undefined);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination
  const [selectedResourceType, setSelectedResourceType] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('WAITING');
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [limit] = useState<number>(20);
  const [offset, setOffset] = useState<number>(0);

  // Match confirmation dialog state
  const [confirmingEntry, setConfirmingEntry] = useState<WaitlistEntry | null>(null);
  const [candidateBeds, setCandidateBeds] = useState<Bed[]>([]);
  const [selectedBedId, setSelectedBedId] = useState<number>(0);
  const [confirmNotes, setConfirmNotes] = useState<string>('');
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    getDepartments().then(setDepartments).catch(() => {});
  }, []);

  const fetchWaitlist = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getWaitlist({
        resourceType: (selectedResourceType as WaitlistResourceType) || undefined,
        status: (selectedStatus as WaitlistStatus) || undefined,
        departmentId: selectedDept ? Number(selectedDept) : undefined,
        limit,
        offset,
      });
      // Important: preserve backend deterministic queue order; do not sort!
      setEntries(res.data);
      setTotalCount(res.totalCount);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [selectedResourceType, selectedStatus, selectedDept, limit, offset]);

  useEffect(() => {
    fetchWaitlist();
  }, [fetchWaitlist]);

  // WebSocket targeted refresh
  useWebSocketEvent(['WAITLIST_UPDATED', 'MATCH_ASSIGNED', 'BED_UPDATED'], () => {
    fetchWaitlist();
  });

  // Cancel an entry
  const handleCancel = async (id: number) => {
    if (!window.confirm('Remove this patient from the waiting queue?')) return;
    try {
      await cancelWaitlistEntry(id);
      fetchWaitlist();
    } catch (err: unknown) {
      alert(`Failed to remove: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  // Open manual match confirmation for a BED entry
  const handleOpenConfirm = async (entry: WaitlistEntry) => {
    setConfirmingEntry(entry);
    setActionError(null);
    setActionSuccess(null);
    setConfirmNotes('Confirmed allocation via Operations board');

    if (entry.resourceType === 'BED') {
      try {
        const beds = await getAvailableBeds(entry.departmentId);
        // Filter by bed type if required
        const eligible = entry.requiredBedType
          ? beds.filter((b) => b.bedType === entry.requiredBedType)
          : beds;
        setCandidateBeds(eligible);
        if (eligible.length > 0) setSelectedBedId(eligible[0].id);
      } catch {
        setCandidateBeds([]);
      }
    }
  };

  // Submit match confirmation
  const handleConfirmMatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirmingEntry || !selectedBedId) return;

    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      await confirmMatch({
        resourceType: 'BED',
        resourceId: selectedBedId,
        waitlistEntryId: confirmingEntry.id,
        notes: confirmNotes,
      });
      setActionSuccess(`Match confirmed! Patient #${confirmingEntry.patientId} assigned to Bed #${selectedBedId}.`);
      setTimeout(() => {
        setConfirmingEntry(null);
        fetchWaitlist();
      }, 1200);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  const getDeptName = (deptId: number) => {
    const d = departments.find((dept) => dept.id === deptId);
    return d ? `${d.name} (${d.code})` : `Dept #${deptId}`;
  };

  return (
    <div className="flex flex-col gap-md">
      {/* Filters Toolbar */}
      <div
        className="card flex items-center justify-between"
        style={{ padding: 'var(--space-sm) var(--space-md)', flexWrap: 'wrap', gap: 'var(--space-sm)' }}
      >
        <div className="flex items-center gap-sm" style={{ flexWrap: 'wrap' }}>
          <div style={{ minWidth: '160px' }}>
            <select
              className="select-control"
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setOffset(0);
              }}
            >
              <option value="WAITING">Status: WAITING Only</option>
              <option value="FULFILLED">Status: FULFILLED</option>
              <option value="CANCELLED">Status: CANCELLED</option>
              <option value="">All Statuses</option>
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
              <option value="THEATRE">THEATRE</option>
              <option value="STAFF">STAFF</option>
            </select>
          </div>

          <div style={{ minWidth: '180px' }}>
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

          {(selectedResourceType || selectedStatus !== 'WAITING' || selectedDept) && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => {
                setSelectedResourceType('');
                setSelectedStatus('WAITING');
                setSelectedDept('');
                setOffset(0);
              }}
            >
              Reset
            </button>
          )}
        </div>

        <div className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Queue entries: <strong className="font-tabular">{totalCount ?? entries.length}</strong>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={fetchWaitlist} />}

      {/* Waitlist Queue Table */}
      {loading && entries.length === 0 ? (
        <LoadingState message="Loading deterministic waitlist queue..." />
      ) : entries.length === 0 ? (
        <div className="card" style={{ padding: 'var(--space-2xl)', textAlign: 'center', color: 'var(--outline)' }}>
          No entries found in the waitlist for the selected criteria.
        </div>
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="table-container" style={{ border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank #</th>
                  <th>Priority</th>
                  <th>Resource Required</th>
                  <th>Patient ID</th>
                  <th>Department</th>
                  <th>Reason / Clinical Need</th>
                  <th>Requested At</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, idx) => {
                  const globalRank = offset + idx + 1;
                  const isWaiting = entry.status === 'WAITING';

                  return (
                    <tr key={entry.id}>
                      <td className="font-tabular" style={{ fontWeight: 700, color: 'var(--primary)' }}>
                        #{globalRank}
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
                          <span className="text-label-sm" style={{ marginLeft: '4px', color: 'var(--outline)' }}>
                            ({entry.requiredBedType})
                          </span>
                        )}
                        {entry.requiredStaffRole && (
                          <span className="text-label-sm" style={{ marginLeft: '4px', color: 'var(--outline)' }}>
                            ({entry.requiredStaffRole})
                          </span>
                        )}
                      </td>
                      <td className="font-tabular text-label-md" style={{ fontWeight: 600 }}>
                        Patient #{entry.patientId}
                      </td>
                      <td>{getDeptName(entry.departmentId)}</td>
                      <td style={{ maxWidth: '320px' }}>{entry.reason || 'Standard allocation'}</td>
                      <td className="font-tabular text-label-sm" style={{ color: 'var(--outline)' }}>
                        {new Date(entry.requestedAt).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td>
                        <StatusBadge status={entry.status} />
                        {entry.fulfilledResourceId && (
                          <div className="text-label-sm font-tabular" style={{ color: 'var(--color-available)', fontSize: '11px', marginTop: '2px' }}>
                            Resource #{entry.fulfilledResourceId}
                          </div>
                        )}
                      </td>
                      <td>
                        {isWaiting && (
                          <div className="flex items-center gap-xs">
                            {entry.resourceType === 'BED' && (
                              <button
                                className="btn btn-primary btn-sm"
                                style={{ fontSize: '11px', padding: '2px 8px' }}
                                onClick={() => handleOpenConfirm(entry)}
                              >
                                Allocate Bed
                              </button>
                            )}
                            <button
                              className="btn btn-outline btn-sm"
                              style={{ fontSize: '11px', padding: '2px 6px', color: 'var(--color-error)' }}
                              onClick={() => handleCancel(entry.id)}
                            >
                              Cancel
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
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

      {/* Confirm Match Modal */}
      {confirmingEntry && (
        <div className="side-panel-overlay" onClick={() => setConfirmingEntry(null)}>
          <div
            className="card"
            style={{
              width: '460px',
              maxWidth: '92vw',
              margin: 'auto',
              padding: 'var(--space-xl)',
              backgroundColor: 'var(--surface-container-lowest)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-md)' }}>
              <h3 className="text-headline-sm" style={{ fontWeight: 700 }}>
                Confirm Match &amp; Bed Allocation
              </h3>
              <button className="btn btn-outline btn-sm" onClick={() => setConfirmingEntry(null)}>
                &times;
              </button>
            </div>

            {actionError && (
              <div
                style={{
                  padding: 'var(--space-sm)',
                  backgroundColor: 'var(--color-error-bg)',
                  color: 'var(--color-error-text)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '12px',
                  marginBottom: 'var(--space-sm)',
                }}
              >
                {actionError}
              </div>
            )}
            {actionSuccess && (
              <div
                style={{
                  padding: 'var(--space-sm)',
                  backgroundColor: 'var(--color-available-bg)',
                  color: 'var(--color-available)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '12px',
                  fontWeight: 600,
                  marginBottom: 'var(--space-sm)',
                }}
              >
                {actionSuccess}
              </div>
            )}

            <div
              style={{
                padding: 'var(--space-sm) var(--space-md)',
                backgroundColor: 'var(--surface-container-low)',
                borderRadius: 'var(--radius-md)',
                marginBottom: 'var(--space-md)',
              }}
            >
              <div className="text-label-sm">
                Candidate: <strong>Patient #{confirmingEntry.patientId}</strong>
              </div>
              <div className="text-label-sm" style={{ marginTop: '2px' }}>
                Department: {getDeptName(confirmingEntry.departmentId)}
              </div>
              <div className="text-label-sm" style={{ marginTop: '2px' }}>
                Priority: <strong>P{confirmingEntry.priority}</strong> • Required Bed:{' '}
                {confirmingEntry.requiredBedType || 'Any General/ICU'}
              </div>
            </div>

            <form onSubmit={handleConfirmMatch} className="flex flex-col gap-md">
              <div className="flex flex-col gap-xs">
                <label className="text-label-sm">Select Available Bed:</label>
                {candidateBeds.length === 0 ? (
                  <div style={{ color: 'var(--color-error)', fontSize: '12px' }}>
                    No matching available beds in {getDeptName(confirmingEntry.departmentId)}.
                  </div>
                ) : (
                  <select
                    className="select-control"
                    value={selectedBedId}
                    onChange={(e) => setSelectedBedId(Number(e.target.value))}
                    required
                  >
                    {candidateBeds.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.bedNumber} ({b.bedType})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="flex flex-col gap-xs">
                <label className="text-label-sm">Coordinator Notes:</label>
                <input
                  type="text"
                  className="input-text"
                  value={confirmNotes}
                  onChange={(e) => setConfirmNotes(e.target.value)}
                />
              </div>

              <p className="text-label-sm" style={{ color: 'var(--outline)' }}>
                Confirming immediately triggers the validated atomic admission/transfer transaction and records MATCH_IDENTIFIED audit event.
              </p>

              <div className="flex items-center justify-end gap-sm" style={{ marginTop: 'var(--space-xs)' }}>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setConfirmingEntry(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={actionLoading || candidateBeds.length === 0}
                >
                  {actionLoading ? 'Allocating...' : 'Confirm Allocation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
