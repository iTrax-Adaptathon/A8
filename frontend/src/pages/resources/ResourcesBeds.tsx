import React, { useState, useEffect, useCallback } from 'react';
import { getBeds, getDepartments, updateBedStatus, releaseBed, getMatches } from '../../api/endpoints';
import { Bed, Department, BedStatus, BedType, MatchResult } from '../../api/types';
import { useWebSocketEvent } from '../../api/websocket';
import { StatusBadge } from '../../components/common/StatusBadge';
import { SidePanel } from '../../components/common/SidePanel';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';

interface ResourcesBedsProps {
  initialDepartmentId?: number;
}

export const ResourcesBeds: React.FC<ResourcesBedsProps> = ({ initialDepartmentId }) => {
  const [beds, setBeds] = useState<Bed[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedDept, setSelectedDept] = useState<string>(
    initialDepartmentId ? String(initialDepartmentId) : ''
  );
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('');

  // Selected Bed for Detail Panel
  const [selectedBed, setSelectedBed] = useState<Bed | null>(null);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Status Change state
  const [targetStatus, setTargetStatus] = useState<BedStatus>('AVAILABLE');
  const [statusNotes, setStatusNotes] = useState<string>('');

  // On-demand matches preview (Rule 2: requested on-demand only!)
  const [matches, setMatches] = useState<MatchResult | null>(null);
  const [loadingMatches, setLoadingMatches] = useState<boolean>(false);

  // Fetch departments
  useEffect(() => {
    getDepartments().then(setDepartments).catch(() => {});
  }, []);

  // Fetch beds
  const fetchBeds = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getBeds({
        departmentId: selectedDept ? Number(selectedDept) : undefined,
        status: (selectedStatus as BedStatus) || undefined,
        bedType: (selectedType as BedType) || undefined,
        limit: 100,
      });
      setBeds(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [selectedDept, selectedStatus, selectedType]);

  useEffect(() => {
    fetchBeds();
  }, [fetchBeds]);

  // Targeted WebSocket refresh: when beds update
  useWebSocketEvent(['BED_UPDATED', 'MATCH_ASSIGNED', 'PATIENT_UPDATED'], () => {
    fetchBeds();
  });

  const handleSelectBed = (bed: Bed) => {
    setSelectedBed(bed);
    setActionError(null);
    setActionSuccess(null);
    setMatches(null);
    setTargetStatus(bed.status === 'CLEANING' ? 'AVAILABLE' : 'CLEANING');
    setStatusNotes('');
  };

  const handleClosePanel = () => {
    setSelectedBed(null);
    setMatches(null);
  };

  // Action: Release Bed
  const handleRelease = async () => {
    if (!selectedBed) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const res = await releaseBed(selectedBed.id, {
        notes: statusNotes || 'Bed released after sanitization',
        autoAssign: true,
      });
      setSelectedBed(res.bed);
      if (res.autoAssignment?.matched) {
        setActionSuccess(
          `Bed released! Auto-assigned to waitlisted Patient #${res.autoAssignment.patientId}.`
        );
      } else {
        setActionSuccess('Bed successfully marked AVAILABLE.');
      }
      fetchBeds();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Action: Update Status
  const handleUpdateStatus = async () => {
    if (!selectedBed) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await updateBedStatus(selectedBed.id, {
        newStatus: targetStatus,
        notes: statusNotes,
        autoAssign: true,
      });
      setSelectedBed(updated);
      setActionSuccess(`Bed status updated to ${updated.status}.`);
      fetchBeds();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Action: On-demand check eligible candidates
  const handleCheckMatches = async () => {
    if (!selectedBed) return;
    setLoadingMatches(true);
    try {
      const res = await getMatches('BED', selectedBed.id);
      setMatches(res);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingMatches(false);
    }
  };

  const getDeptName = (deptId: number) => {
    const d = departments.find((dept) => dept.id === deptId);
    return d ? `${d.name} (${d.code})` : `Dept #${deptId}`;
  };

  return (
    <div className="flex flex-col gap-md">
      {/* Filter Toolbar */}
      <div
        className="card flex items-center justify-between"
        style={{ padding: 'var(--space-sm) var(--space-md)', flexWrap: 'wrap', gap: 'var(--space-sm)' }}
      >
        <div className="flex items-center gap-sm" style={{ flexWrap: 'wrap' }}>
          <div style={{ minWidth: '180px' }}>
            <select
              className="select-control"
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
            >
              <option value="">All Departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.code})
                </option>
              ))}
            </select>
          </div>

          <div style={{ minWidth: '150px' }}>
            <select
              className="select-control"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="AVAILABLE">AVAILABLE</option>
              <option value="OCCUPIED">OCCUPIED</option>
              <option value="CLEANING">CLEANING</option>
              <option value="MAINTENANCE">MAINTENANCE</option>
            </select>
          </div>

          <div style={{ minWidth: '150px' }}>
            <select
              className="select-control"
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
            >
              <option value="">All Bed Types</option>
              <option value="GENERAL">GENERAL</option>
              <option value="ICU">ICU</option>
              <option value="EMERGENCY">EMERGENCY</option>
              <option value="PEDIATRIC">PEDIATRIC</option>
              <option value="SURGICAL">SURGICAL</option>
            </select>
          </div>

          {(selectedDept || selectedStatus || selectedType) && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => {
                setSelectedDept('');
                setSelectedStatus('');
                setSelectedType('');
              }}
            >
              Reset Filters
            </button>
          )}
        </div>

        <div className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Showing <strong className="font-tabular">{beds.length}</strong> beds
        </div>
      </div>

      {/* Error state */}
      {error && (
        <ErrorState
          title="Failed to Load Beds"
          message={error}
          onRetry={fetchBeds}
        />
      )}

      {/* Loading state */}
      {loading && beds.length === 0 ? (
        <LoadingState message="Loading hospital beds..." />
      ) : beds.length === 0 ? (
        <div
          className="card"
          style={{
            padding: 'var(--space-2xl)',
            textAlign: 'center',
            color: 'var(--outline)',
          }}
        >
          No beds found matching the selected criteria.
        </div>
      ) : (
        /* Bed Grid */
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
            gap: 'var(--space-md)',
          }}
        >
          {beds.map((bed) => (
            <div
              key={bed.id}
              className={`card card-interactive ${
                selectedBed?.id === bed.id ? 'selected-bed' : ''
              }`}
              style={{
                padding: 'var(--space-md)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-xs)',
                borderColor: selectedBed?.id === bed.id ? 'var(--primary)' : undefined,
                borderWidth: selectedBed?.id === bed.id ? '2px' : '1px',
              }}
              onClick={() => handleSelectBed(bed)}
            >
              <div className="flex items-center justify-between">
                <span className="text-headline-sm font-tabular" style={{ fontWeight: 700 }}>
                  {bed.bedNumber}
                </span>
                <StatusBadge status={bed.status} />
              </div>

              <div className="text-label-sm" style={{ color: 'var(--outline)' }}>
                {getDeptName(bed.departmentId)}
              </div>

              <div className="flex items-center justify-between" style={{ marginTop: 'var(--space-xs)' }}>
                <span className="badge badge-neutral" style={{ fontSize: '10px' }}>
                  {bed.bedType}
                </span>

                {bed.status === 'OCCUPIED' && bed.currentPatientId && (
                  <span className="text-label-sm" style={{ color: 'var(--secondary)', fontWeight: 600 }}>
                    Patient #{bed.currentPatientId}
                  </span>
                )}
                {bed.status === 'AVAILABLE' && (
                  <span className="text-label-sm" style={{ color: 'var(--color-available)', fontWeight: 600 }}>
                    Ready
                  </span>
                )}
                {bed.status === 'CLEANING' && (
                  <span className="text-label-sm" style={{ color: 'var(--color-cleaning)', fontWeight: 600 }}>
                    Sanitizing
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Bed Detail & Action SidePanel */}
      <SidePanel
        isOpen={selectedBed !== null}
        onClose={handleClosePanel}
        title={selectedBed ? `Bed: ${selectedBed.bedNumber}` : ''}
        subtitle={selectedBed ? getDeptName(selectedBed.departmentId) : undefined}
      >
        {selectedBed && (
          <div className="flex flex-col gap-lg">
            {/* Status alerts */}
            {actionError && (
              <div
                style={{
                  padding: 'var(--space-sm)',
                  backgroundColor: 'var(--color-error-bg)',
                  color: 'var(--color-error-text)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '12px',
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
                }}
              >
                {actionSuccess}
              </div>
            )}

            {/* Bed Metadata Table */}
            <div
              className="card"
              style={{
                padding: 'var(--space-md)',
                backgroundColor: 'var(--surface-container-low)',
              }}
            >
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Current Status:
                </span>
                <StatusBadge status={selectedBed.status} />
              </div>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Bed Type:
                </span>
                <span className="text-label-md" style={{ fontWeight: 600 }}>
                  {selectedBed.bedType}
                </span>
              </div>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Bed ID:
                </span>
                <span className="text-label-sm font-tabular">{selectedBed.id}</span>
              </div>
              {selectedBed.currentPatientId && (
                <div className="flex items-center justify-between">
                  <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                    Current Patient:
                  </span>
                  <span className="text-label-md font-tabular" style={{ color: 'var(--secondary)', fontWeight: 600 }}>
                    Patient ID #{selectedBed.currentPatientId}
                  </span>
                </div>
              )}
            </div>

            {/* Operational Actions */}
            <div className="flex flex-col gap-sm">
              <h4 className="text-label-lg" style={{ fontWeight: 600 }}>
                Operational Actions
              </h4>

              {/* 1. Quick Release if CLEANING */}
              {selectedBed.status === 'CLEANING' && (
                <div
                  className="card"
                  style={{
                    padding: 'var(--space-md)',
                    borderLeft: '4px solid var(--color-cleaning)',
                  }}
                >
                  <div className="text-label-md" style={{ fontWeight: 600, marginBottom: '4px' }}>
                    Housekeeping Sanitization Complete?
                  </div>
                  <p className="text-body-sm" style={{ color: 'var(--on-surface-variant)', marginBottom: 'var(--space-sm)' }}>
                    Release this bed to AVAILABLE. The engine will deterministically match the highest priority waiting patient.
                  </p>
                  <button
                    className="btn btn-primary w-full"
                    disabled={actionLoading}
                    onClick={handleRelease}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
                      cleaning_services
                    </span>
                    {actionLoading ? 'Releasing...' : 'Release Bed (Auto-Match Waiting Queue)'}
                  </button>
                </div>
              )}

              {/* 2. Status Transition if non-occupied */}
              {selectedBed.status !== 'OCCUPIED' ? (
                <div className="card" style={{ padding: 'var(--space-md)' }}>
                  <div className="text-label-md" style={{ fontWeight: 600, marginBottom: 'var(--space-xs)' }}>
                    Manual Status Transition
                  </div>
                  <p className="text-body-sm" style={{ color: 'var(--outline)', marginBottom: 'var(--space-sm)' }}>
                    Allowed transitions: AVAILABLE &harr; CLEANING &harr; MAINTENANCE
                  </p>

                  <div className="flex flex-col gap-xs" style={{ marginBottom: 'var(--space-sm)' }}>
                    <label className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                      New Status:
                    </label>
                    <select
                      className="select-control"
                      value={targetStatus}
                      onChange={(e) => setTargetStatus(e.target.value as BedStatus)}
                    >
                      {selectedBed.status !== 'AVAILABLE' && <option value="AVAILABLE">AVAILABLE</option>}
                      {selectedBed.status !== 'CLEANING' && <option value="CLEANING">CLEANING</option>}
                      {selectedBed.status !== 'MAINTENANCE' && <option value="MAINTENANCE">MAINTENANCE</option>}
                    </select>
                  </div>

                  <div className="flex flex-col gap-xs" style={{ marginBottom: 'var(--space-md)' }}>
                    <label className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                      Notes:
                    </label>
                    <input
                      type="text"
                      className="input-text"
                      placeholder="e.g. Scheduled deep disinfection"
                      value={statusNotes}
                      onChange={(e) => setStatusNotes(e.target.value)}
                    />
                  </div>

                  <button
                    className="btn btn-secondary w-full"
                    disabled={actionLoading}
                    onClick={handleUpdateStatus}
                  >
                    {actionLoading ? 'Updating...' : `Set Status to ${targetStatus}`}
                  </button>
                </div>
              ) : (
                <div
                  className="card"
                  style={{
                    padding: 'var(--space-md)',
                    backgroundColor: 'var(--surface-container-low)',
                  }}
                >
                  <div className="text-label-md" style={{ fontWeight: 600, color: 'var(--secondary)' }}>
                    Bed is Occupied
                  </div>
                  <p className="text-body-sm" style={{ color: 'var(--on-surface-variant)', marginTop: '4px' }}>
                    Occupied beds cannot have their status altered directly. Manage patient transfer or discharge in the Patient Flow screen to free this bed.
                  </p>
                </div>
              )}

              {/* 3. On-Demand Waitlist Match Preview (Rule 2) */}
              <div className="card" style={{ padding: 'var(--space-md)', marginTop: 'var(--space-xs)' }}>
                <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                  <div>
                    <div className="text-label-md" style={{ fontWeight: 600 }}>
                      Queue Match Preview
                    </div>
                    <div className="text-label-sm" style={{ color: 'var(--outline)' }}>
                      Check eligible waiting candidates for this bed
                    </div>
                  </div>
                  <button
                    className="btn btn-outline btn-sm"
                    disabled={loadingMatches}
                    onClick={handleCheckMatches}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                      search
                    </span>
                    {loadingMatches ? 'Checking...' : 'Check Matches'}
                  </button>
                </div>

                {matches && (
                  <div style={{ marginTop: 'var(--space-sm)' }}>
                    <div className="text-label-sm" style={{ marginBottom: 'var(--space-xs)' }}>
                      Resource assignable now:{' '}
                      <strong style={{ color: matches.resourceAvailable ? 'var(--color-available)' : 'var(--color-cleaning)' }}>
                        {matches.resourceAvailable ? 'YES (AVAILABLE)' : 'NO'}
                      </strong>
                    </div>

                    {matches.candidates.length === 0 ? (
                      <p className="text-body-sm" style={{ color: 'var(--outline)' }}>
                        No waiting patients match this bed type and department right now.
                      </p>
                    ) : (
                      <div className="flex flex-col gap-xs">
                        {matches.candidates.map((c) => (
                          <div
                            key={c.waitlistEntryId}
                            style={{
                              padding: '6px 8px',
                              backgroundColor: 'var(--surface-container-low)',
                              borderRadius: 'var(--radius-sm)',
                              border: '1px solid var(--outline-variant)',
                            }}
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-label-sm" style={{ fontWeight: 600 }}>
                                #{c.rank} Patient #{c.patientId}
                              </span>
                              <span className="badge badge-warning" style={{ fontSize: '10px' }}>
                                Priority {c.priority}
                              </span>
                            </div>
                            <div className="text-label-sm" style={{ color: 'var(--outline)', fontSize: '11px' }}>
                              {c.reason || 'Waitlist entry'}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </SidePanel>
    </div>
  );
};
