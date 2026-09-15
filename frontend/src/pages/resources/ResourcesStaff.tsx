import React, { useState, useEffect, useCallback } from 'react';
import {
  getStaff,
  getDepartments,
  updateStaffStatus,
  getStaffAssignments,
  releaseStaffAssignment,
  getMatches,
} from '../../api/endpoints';
import {
  Staff,
  Department,
  StaffRole,
  StaffStatus,
  StaffAssignment,
  MatchResult,
} from '../../api/types';
import { useWebSocketEvent } from '../../api/websocket';
import { StatusBadge } from '../../components/common/StatusBadge';
import { SidePanel } from '../../components/common/SidePanel';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';

export const ResourcesStaff: React.FC = () => {
  const [staffList, setStaffList] = useState<Staff[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [selectedRole, setSelectedRole] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');

  // Selected staff member for detail panel
  const [activeStaff, setActiveStaff] = useState<Staff | null>(null);
  const [assignments, setAssignments] = useState<StaffAssignment[]>([]);
  const [assignmentsLoading, setAssignmentsLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // On-demand matches preview (Rule 2)
  const [matches, setMatches] = useState<MatchResult | null>(null);
  const [loadingMatches, setLoadingMatches] = useState<boolean>(false);

  useEffect(() => {
    getDepartments().then(setDepartments).catch(() => {});
  }, []);

  const fetchStaff = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getStaff({
        departmentId: selectedDept ? Number(selectedDept) : undefined,
        role: (selectedRole as StaffRole) || undefined,
        status: (selectedStatus as StaffStatus) || undefined,
        limit: 100,
      });
      setStaffList(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [selectedDept, selectedRole, selectedStatus]);

  useEffect(() => {
    fetchStaff();
  }, [fetchStaff]);

  // WebSocket targeted refresh
  useWebSocketEvent(['STAFF_UPDATED', 'MATCH_ASSIGNED'], () => {
    fetchStaff();
  });

  const handleOpenStaff = async (staff: Staff) => {
    setActiveStaff(staff);
    setActionError(null);
    setActionSuccess(null);
    setMatches(null);

    // Fetch assignments for this staff member
    setAssignmentsLoading(true);
    try {
      const res = await getStaffAssignments({ staffId: staff.id });
      setAssignments(res.data);
    } catch {
      setAssignments([]);
    } finally {
      setAssignmentsLoading(false);
    }
  };

  const handleClosePanel = () => {
    setActiveStaff(null);
    setAssignments([]);
    setMatches(null);
  };

  // Toggle duty status (AVAILABLE <-> OFF_DUTY)
  const handleToggleStatus = async (newStatus: StaffStatus) => {
    if (!activeStaff) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await updateStaffStatus(activeStaff.id, {
        newStatus,
        autoAssign: true,
      });
      setActiveStaff(updated);
      setActionSuccess(`Staff duty status updated to ${newStatus}.`);
      fetchStaff();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Release an active assignment
  const handleReleaseAssignment = async (assignmentId: number) => {
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const res = await releaseStaffAssignment(assignmentId, 'Assignment released by coordinator');
      if (res.autoAssignment?.matched) {
        setActionSuccess('Assignment released! Staff auto-assigned to waiting request.');
      } else {
        setActionSuccess('Staff assignment released; staff returned to AVAILABLE.');
      }
      // Refresh assignments
      if (activeStaff) {
        const aRes = await getStaffAssignments({ staffId: activeStaff.id });
        setAssignments(aRes.data);
      }
      fetchStaff();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Check on-demand matches (Rule 2)
  const handleCheckMatches = async () => {
    if (!activeStaff) return;
    setLoadingMatches(true);
    try {
      const res = await getMatches('STAFF', activeStaff.id);
      setMatches(res);
    } catch (err: unknown) {
      alert(`Could not evaluate matches: ${err instanceof Error ? err.message : String(err)}`);
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
      {/* Filter toolbar */}
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
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
            >
              <option value="">All Staff Roles</option>
              <option value="SURGEON">SURGEON</option>
              <option value="ANAESTHETIST">ANAESTHETIST</option>
              <option value="DOCTOR">DOCTOR</option>
              <option value="NURSE">NURSE</option>
              <option value="PORTER">PORTER</option>
            </select>
          </div>

          <div style={{ minWidth: '140px' }}>
            <select
              className="select-control"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="AVAILABLE">AVAILABLE</option>
              <option value="ASSIGNED">ASSIGNED</option>
              <option value="OFF_DUTY">OFF_DUTY</option>
            </select>
          </div>

          {(selectedDept || selectedRole || selectedStatus) && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => {
                setSelectedDept('');
                setSelectedRole('');
                setSelectedStatus('');
              }}
            >
              Reset Filters
            </button>
          )}
        </div>

        <div className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Showing <strong className="font-tabular">{staffList.length}</strong> clinical staff members
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={fetchStaff} />}

      {loading && staffList.length === 0 ? (
        <LoadingState message="Loading clinical staff directory..." />
      ) : staffList.length === 0 ? (
        <div className="card" style={{ padding: 'var(--space-2xl)', textAlign: 'center', color: 'var(--outline)' }}>
          No staff found matching the selected filters.
        </div>
      ) : (
        /* Staff Grid */
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: 'var(--space-md)',
          }}
        >
          {staffList.map((staff) => (
            <div
              key={staff.id}
              className="card card-interactive"
              style={{
                padding: 'var(--space-md)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-xs)',
              }}
              onClick={() => handleOpenStaff(staff)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-xs">
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--surface-container-high)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--primary)',
                    }}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
                      person
                    </span>
                  </div>
                  <div>
                    <div className="text-headline-sm" style={{ fontWeight: 600 }}>
                      {staff.name}
                    </div>
                    <div className="text-label-sm" style={{ color: 'var(--outline)' }}>
                      {staff.role} • ID #{staff.id}
                    </div>
                  </div>
                </div>
                <StatusBadge status={staff.status} />
              </div>

              <div className="text-body-sm" style={{ color: 'var(--on-surface-variant)', marginTop: '4px' }}>
                {getDeptName(staff.departmentId)}
              </div>

              <div
                className="flex items-center justify-between text-label-sm font-tabular"
                style={{
                  marginTop: 'var(--space-xs)',
                  paddingTop: 'var(--space-xs)',
                  borderTop: '1px solid var(--surface-container)',
                  color: 'var(--outline)',
                }}
              >
                <span>Shift:</span>
                <span>
                  {new Date(staff.shiftStart).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} –{' '}
                  {new Date(staff.shiftEnd).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Staff Detail SidePanel */}
      <SidePanel
        isOpen={activeStaff !== null}
        onClose={handleClosePanel}
        title={activeStaff ? activeStaff.name : ''}
        subtitle={activeStaff ? `${activeStaff.role} • ${getDeptName(activeStaff.departmentId)}` : undefined}
      >
        {activeStaff && (
          <div className="flex flex-col gap-lg">
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

            {/* Profile Info */}
            <div className="card" style={{ padding: 'var(--space-md)', backgroundColor: 'var(--surface-container-low)' }}>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Current Status:
                </span>
                <StatusBadge status={activeStaff.status} />
              </div>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Clinical Role:
                </span>
                <span className="badge badge-neutral">{activeStaff.role}</span>
              </div>
              <div className="flex items-center justify-between font-tabular">
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Shift Window:
                </span>
                <span className="text-label-sm">
                  {new Date(activeStaff.shiftStart).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} –{' '}
                  {new Date(activeStaff.shiftEnd).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>

            {/* Status Actions */}
            <div className="card" style={{ padding: 'var(--space-md)' }}>
              <h4 className="text-label-lg" style={{ fontWeight: 600, marginBottom: 'var(--space-xs)' }}>
                Duty Status Management
              </h4>
              <p className="text-body-sm" style={{ color: 'var(--outline)', marginBottom: 'var(--space-sm)' }}>
                Note: ASSIGNED status is managed automatically through patient/surgery assignments.
              </p>

              <div className="flex items-center gap-sm">
                {activeStaff.status === 'OFF_DUTY' ? (
                  <button
                    className="btn btn-primary w-full"
                    disabled={actionLoading}
                    onClick={() => handleToggleStatus('AVAILABLE')}
                  >
                    Set On-Duty (AVAILABLE)
                  </button>
                ) : activeStaff.status === 'AVAILABLE' ? (
                  <button
                    className="btn btn-outline w-full"
                    disabled={actionLoading}
                    onClick={() => handleToggleStatus('OFF_DUTY')}
                  >
                    Set OFF_DUTY
                  </button>
                ) : (
                  <span className="text-label-sm" style={{ color: 'var(--secondary)', fontWeight: 600 }}>
                    Staff is currently engaged in an active assignment. Release the assignment below to return to AVAILABLE.
                  </span>
                )}
              </div>
            </div>

            {/* Active Assignments */}
            <div className="card" style={{ padding: 'var(--space-md)' }}>
              <h4 className="text-label-lg" style={{ fontWeight: 600, marginBottom: 'var(--space-sm)' }}>
                Assignments History ({assignments.length})
              </h4>

              {assignmentsLoading ? (
                <div style={{ padding: 'var(--space-sm)', textAlign: 'center', color: 'var(--outline)' }}>
                  Loading assignments...
                </div>
              ) : assignments.length === 0 ? (
                <p className="text-body-sm" style={{ color: 'var(--outline)' }}>
                  No active or past assignments recorded for this staff member.
                </p>
              ) : (
                <div className="flex flex-col gap-xs">
                  {assignments.map((a) => (
                    <div
                      key={a.id}
                      style={{
                        padding: '8px 10px',
                        backgroundColor: 'var(--surface-container-low)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--outline-variant)',
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-label-md" style={{ fontWeight: 600 }}>
                          {a.assignmentType} Assignment #{a.id}
                        </span>
                        <StatusBadge status={a.status} />
                      </div>
                      <div className="text-label-sm" style={{ color: 'var(--outline)', marginTop: '2px' }}>
                        {a.surgeryId && `Surgery #${a.surgeryId} • `}
                        {a.patientId && `Patient #${a.patientId} • `}
                        Started {new Date(a.startTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                      {a.status === 'ACTIVE' && (
                        <button
                          className="btn btn-outline btn-sm"
                          style={{ marginTop: 'var(--space-xs)', fontSize: '11px' }}
                          disabled={actionLoading}
                          onClick={() => handleReleaseAssignment(a.id)}
                        >
                          Release Assignment
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* On-Demand Matches (Rule 2) */}
            {activeStaff.status === 'AVAILABLE' && (
              <div className="card" style={{ padding: 'var(--space-md)' }}>
                <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                  <div>
                    <div className="text-label-md" style={{ fontWeight: 600 }}>
                      Eligible Queue Matches
                    </div>
                    <div className="text-label-sm" style={{ color: 'var(--outline)' }}>
                      Check waitlist entries requiring this staff role
                    </div>
                  </div>
                  <button
                    className="btn btn-outline btn-sm"
                    disabled={loadingMatches}
                    onClick={handleCheckMatches}
                  >
                    {loadingMatches ? 'Checking...' : 'Check Matches'}
                  </button>
                </div>

                {matches && (
                  <div style={{ marginTop: 'var(--space-sm)' }}>
                    {matches.candidates.length === 0 ? (
                      <p className="text-body-sm" style={{ color: 'var(--outline)' }}>
                        No waiting requests currently demand this role and department.
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
                                #{c.rank} Waitlist #{c.waitlistEntryId}
                              </span>
                              <span className="badge badge-warning" style={{ fontSize: '10px' }}>
                                Priority {c.priority}
                              </span>
                            </div>
                            <div className="text-label-sm" style={{ color: 'var(--outline)', fontSize: '11px' }}>
                              Patient #{c.patientId} {c.surgeryId ? `(Surgery #${c.surgeryId})` : ''}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </SidePanel>
    </div>
  );
};
