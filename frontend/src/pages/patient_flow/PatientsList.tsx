import React, { useState, useEffect, useCallback } from 'react';
import {
  getPatients,
  getPatientHistory,
  createPatient,
  admitPatient,
  transferPatient,
  dischargePatient,
  getDepartments,
  getAvailableBeds,
} from '../../api/endpoints';
import {
  Patient,
  Department,
  Bed,
  FlowEvent,
  PatientStatus,
} from '../../api/types';
import { useWebSocketEvent } from '../../api/websocket';
import { StatusBadge } from '../../components/common/StatusBadge';
import { SidePanel } from '../../components/common/SidePanel';
import { Pagination } from '../../components/common/Pagination';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';

export const PatientsList: React.FC = () => {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [totalCount, setTotalCount] = useState<number | undefined>(undefined);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination & Filters
  const [limit] = useState<number>(20);
  const [offset, setOffset] = useState<number>(0);
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Selected Patient for detail panel
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [history, setHistory] = useState<FlowEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);

  // Patient Actions state
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Admit / Transfer Form state
  const [actionType, setActionType] = useState<'admit' | 'transfer' | 'discharge' | null>(null);
  const [targetDeptId, setTargetDeptId] = useState<number>(0);
  const [targetBedId, setTargetBedId] = useState<number>(0);
  const [actionNotes, setActionNotes] = useState<string>('');
  const [availableBeds, setAvailableBeds] = useState<Bed[]>([]);
  const [loadingBeds, setLoadingBeds] = useState<boolean>(false);

  // Registration modal
  const [showRegisterModal, setShowRegisterModal] = useState<boolean>(false);
  const [regName, setRegName] = useState<string>('');
  const [regAge, setRegAge] = useState<number>(30);
  const [regGender, setRegGender] = useState<string>('Female');
  const [regMrn, setRegMrn] = useState<string>('');

  // Fetch departments
  useEffect(() => {
    getDepartments().then(setDepartments).catch(() => {});
  }, []);

  // Fetch patients
  const fetchPatients = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getPatients({
        status: (selectedStatus as PatientStatus) || undefined,
        departmentId: selectedDept ? Number(selectedDept) : undefined,
        limit,
        offset,
      });
      setPatients(res.data);
      setTotalCount(res.totalCount);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [selectedStatus, selectedDept, limit, offset]);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  // WebSocket targeted updates
  useWebSocketEvent(['PATIENT_UPDATED', 'BED_UPDATED', 'MATCH_ASSIGNED'], () => {
    fetchPatients();
  });

  // Fetch available beds when targetDeptId changes in admit/transfer
  useEffect(() => {
    if (targetDeptId > 0 && (actionType === 'admit' || actionType === 'transfer')) {
      setLoadingBeds(true);
      getAvailableBeds(targetDeptId)
        .then((beds) => {
          setAvailableBeds(beds);
          if (beds.length > 0) setTargetBedId(beds[0].id);
        })
        .catch(() => setAvailableBeds([]))
        .finally(() => setLoadingBeds(false));
    } else {
      setAvailableBeds([]);
    }
  }, [targetDeptId, actionType]);

  const handleSelectPatient = async (patient: Patient) => {
    setSelectedPatient(patient);
    setActionType(null);
    setActionError(null);
    setActionSuccess(null);
    setActionNotes('');

    // Fetch history
    setHistoryLoading(true);
    try {
      const histRes = await getPatientHistory(patient.id, 50, 0);
      setHistory(histRes.data);
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleClosePanel = () => {
    setSelectedPatient(null);
    setActionType(null);
    setHistory([]);
  };

  // Submit Register Patient
  const handleRegisterPatient = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setActionError(null);
    try {
      const newPatient = await createPatient({
        name: regName,
        age: regAge,
        gender: regGender,
        medicalRecordNumber: regMrn || `MRN-${Math.floor(100000 + Math.random() * 900000)}`,
      });
      setShowRegisterModal(false);
      setRegName('');
      setRegMrn('');
      fetchPatients();
      handleSelectPatient(newPatient);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Submit Admit
  const handleAdmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatient || !targetDeptId || !targetBedId) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await admitPatient(selectedPatient.id, {
        departmentId: targetDeptId,
        bedId: targetBedId,
        notes: actionNotes || 'Admitted via Clinical Ops',
      });
      setSelectedPatient(updated);
      setActionSuccess(`Patient admitted to Bed #${targetBedId}!`);
      setActionType(null);
      fetchPatients();
      // Refresh history
      const histRes = await getPatientHistory(updated.id);
      setHistory(histRes.data);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Submit Transfer
  const handleTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatient || !targetDeptId || !targetBedId) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await transferPatient(selectedPatient.id, {
        targetDepartmentId: targetDeptId,
        targetBedId,
        notes: actionNotes || 'Transferred via Clinical Ops',
      });
      setSelectedPatient(updated);
      setActionSuccess(`Patient transferred to Bed #${targetBedId}! Previous bed marked CLEANING.`);
      setActionType(null);
      fetchPatients();
      // Refresh history
      const histRes = await getPatientHistory(updated.id);
      setHistory(histRes.data);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Submit Discharge
  const handleDischarge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatient) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await dischargePatient(selectedPatient.id, {
        notes: actionNotes || 'Discharged from hospital care',
      });
      setSelectedPatient(updated);
      setActionSuccess('Patient discharged successfully! Bed marked for CLEANING turnaround.');
      setActionType(null);
      fetchPatients();
      // Refresh history
      const histRes = await getPatientHistory(updated.id);
      setHistory(histRes.data);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  const getDeptName = (deptId?: number | null) => {
    if (!deptId) return '—';
    const d = departments.find((dept) => dept.id === deptId);
    return d ? `${d.name} (${d.code})` : `Dept #${deptId}`;
  };

  const filteredPatients = searchQuery
    ? patients.filter(
        (p) =>
          p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          p.medicalRecordNumber.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : patients;

  return (
    <div className="flex flex-col gap-md">
      {/* Control bar */}
      <div
        className="card flex items-center justify-between"
        style={{ padding: 'var(--space-sm) var(--space-md)', flexWrap: 'wrap', gap: 'var(--space-sm)' }}
      >
        <div className="flex items-center gap-sm" style={{ flexWrap: 'wrap' }}>
          <div style={{ width: '220px' }}>
            <input
              type="text"
              className="input-text"
              placeholder="Search by name or MRN..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div style={{ minWidth: '150px' }}>
            <select
              className="select-control"
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All Patient Statuses</option>
              <option value="REGISTERED">REGISTERED</option>
              <option value="ADMITTED">ADMITTED</option>
              <option value="TRANSFERRED">TRANSFERRED</option>
              <option value="DISCHARGED">DISCHARGED</option>
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

          {(selectedStatus || selectedDept || searchQuery) && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => {
                setSelectedStatus('');
                setSelectedDept('');
                setSearchQuery('');
                setOffset(0);
              }}
            >
              Reset
            </button>
          )}
        </div>

        <button className="btn btn-primary btn-sm" onClick={() => setShowRegisterModal(true)}>
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
            person_add
          </span>
          Register Patient
        </button>
      </div>

      {error && <ErrorState message={error} onRetry={fetchPatients} />}

      {/* Patient Table */}
      {loading && patients.length === 0 ? (
        <LoadingState message="Loading hospital patient census..." />
      ) : filteredPatients.length === 0 ? (
        <div className="card" style={{ padding: 'var(--space-2xl)', textAlign: 'center', color: 'var(--outline)' }}>
          No patient records match the selected filters.
        </div>
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="table-container" style={{ border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Patient Name</th>
                  <th>MRN</th>
                  <th>Age / Sex</th>
                  <th>Status</th>
                  <th>Assigned Department</th>
                  <th>Bed Number</th>
                  <th>Admitted At</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredPatients.map((p) => (
                  <tr
                    key={p.id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSelectPatient(p)}
                  >
                    <td>
                      <div className="text-label-md" style={{ fontWeight: 600, color: 'var(--primary)' }}>
                        {p.name}
                      </div>
                      <div className="text-label-sm" style={{ color: 'var(--outline)' }}>
                        ID #{p.id}
                      </div>
                    </td>
                    <td className="font-tabular text-label-sm" style={{ fontWeight: 600 }}>
                      {p.medicalRecordNumber}
                    </td>
                    <td>
                      {p.age}y • {p.gender}
                    </td>
                    <td>
                      <StatusBadge status={p.currentStatus} />
                    </td>
                    <td>{getDeptName(p.currentDepartmentId)}</td>
                    <td>
                      {p.currentBedId ? (
                        <span className="badge badge-neutral font-tabular">Bed #{p.currentBedId}</span>
                      ) : (
                        <span style={{ color: 'var(--outline)', fontSize: '12px' }}>—</span>
                      )}
                    </td>
                    <td className="font-tabular text-label-sm" style={{ color: 'var(--outline)' }}>
                      {p.admittedAt
                        ? new Date(p.admittedAt).toLocaleString([], {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : '—'}
                    </td>
                    <td>
                      <button
                        className="btn btn-outline btn-sm"
                        style={{ fontSize: '11px', padding: '2px 8px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectPatient(p);
                        }}
                      >
                        Manage Flow
                      </button>
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

      {/* Patient Detail & Flow Action SidePanel */}
      <SidePanel
        isOpen={selectedPatient !== null}
        onClose={handleClosePanel}
        title={selectedPatient ? selectedPatient.name : ''}
        subtitle={selectedPatient ? `${selectedPatient.medicalRecordNumber} • ${selectedPatient.age}y ${selectedPatient.gender}` : undefined}
      >
        {selectedPatient && (
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

            {/* Current State Info */}
            <div className="card" style={{ padding: 'var(--space-md)', backgroundColor: 'var(--surface-container-low)' }}>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Current Status:
                </span>
                <StatusBadge status={selectedPatient.currentStatus} />
              </div>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Department:
                </span>
                <span className="text-label-md">{getDeptName(selectedPatient.currentDepartmentId)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Assigned Bed:
                </span>
                <span className="text-label-md font-tabular">
                  {selectedPatient.currentBedId ? `Bed #${selectedPatient.currentBedId}` : 'None'}
                </span>
              </div>
            </div>

            {/* Operational Flow Actions */}
            <div className="card" style={{ padding: 'var(--space-md)' }}>
              <h4 className="text-label-lg" style={{ fontWeight: 600, marginBottom: 'var(--space-sm)' }}>
                Patient Transit Actions
              </h4>

              {/* Action Buttons based on status */}
              <div className="flex items-center gap-sm" style={{ marginBottom: actionType ? 'var(--space-md)' : 0 }}>
                {selectedPatient.currentStatus === 'REGISTERED' && (
                  <button
                    className={`btn ${actionType === 'admit' ? 'btn-primary' : 'btn-secondary'} w-full`}
                    onClick={() => {
                      setActionType(actionType === 'admit' ? null : 'admit');
                      if (departments.length > 0) setTargetDeptId(departments[0].id);
                    }}
                  >
                    Admit to Bed
                  </button>
                )}

                {(selectedPatient.currentStatus === 'ADMITTED' || selectedPatient.currentStatus === 'TRANSFERRED') && (
                  <>
                    <button
                      className={`btn ${actionType === 'transfer' ? 'btn-primary' : 'btn-secondary'} w-full`}
                      onClick={() => {
                        setActionType(actionType === 'transfer' ? null : 'transfer');
                        if (departments.length > 0) setTargetDeptId(departments[0].id);
                      }}
                    >
                      Transfer Bed
                    </button>
                    <button
                      className={`btn ${actionType === 'discharge' ? 'btn-danger' : 'btn-outline'} w-full`}
                      onClick={() => setActionType(actionType === 'discharge' ? null : 'discharge')}
                    >
                      Discharge
                    </button>
                  </>
                )}

                {selectedPatient.currentStatus === 'DISCHARGED' && (
                  <span className="text-label-sm" style={{ color: 'var(--outline)' }}>
                    Patient has been discharged from active care.
                  </span>
                )}
              </div>

              {/* Admit Form */}
              {actionType === 'admit' && (
                <form onSubmit={handleAdmit} className="flex flex-col gap-sm" style={{ marginTop: 'var(--space-sm)' }}>
                  <div className="flex flex-col gap-xs">
                    <label className="text-label-sm">Destination Department:</label>
                    <select
                      className="select-control"
                      value={targetDeptId}
                      onChange={(e) => setTargetDeptId(Number(e.target.value))}
                      required
                    >
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name} ({d.code})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-xs">
                    <label className="text-label-sm">Available Bed:</label>
                    {loadingBeds ? (
                      <span className="text-label-sm" style={{ color: 'var(--outline)' }}>Finding available beds...</span>
                    ) : availableBeds.length === 0 ? (
                      <div style={{ color: 'var(--color-error)', fontSize: '12px' }}>
                        No beds currently available in this department. Place on waitlist or choose another department.
                      </div>
                    ) : (
                      <select
                        className="select-control"
                        value={targetBedId}
                        onChange={(e) => setTargetBedId(Number(e.target.value))}
                        required
                      >
                        {availableBeds.map((b) => (
                          <option key={b.id} value={b.id}>
                            {b.bedNumber} ({b.bedType})
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div className="flex flex-col gap-xs">
                    <label className="text-label-sm">Admission Notes:</label>
                    <input
                      type="text"
                      className="input-text"
                      placeholder="e.g. Admitted from Emergency"
                      value={actionNotes}
                      onChange={(e) => setActionNotes(e.target.value)}
                    />
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={actionLoading || availableBeds.length === 0}
                  >
                    {actionLoading ? 'Admitting...' : 'Confirm Patient Admission'}
                  </button>
                </form>
              )}

              {/* Transfer Form */}
              {actionType === 'transfer' && (
                <form onSubmit={handleTransfer} className="flex flex-col gap-sm" style={{ marginTop: 'var(--space-sm)' }}>
                  <div className="flex flex-col gap-xs">
                    <label className="text-label-sm">Target Department:</label>
                    <select
                      className="select-control"
                      value={targetDeptId}
                      onChange={(e) => setTargetDeptId(Number(e.target.value))}
                      required
                    >
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name} ({d.code})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-xs">
                    <label className="text-label-sm">Target Available Bed:</label>
                    {loadingBeds ? (
                      <span className="text-label-sm" style={{ color: 'var(--outline)' }}>Checking available beds...</span>
                    ) : availableBeds.length === 0 ? (
                      <div style={{ color: 'var(--color-error)', fontSize: '12px' }}>
                        No beds available in destination unit.
                      </div>
                    ) : (
                      <select
                        className="select-control"
                        value={targetBedId}
                        onChange={(e) => setTargetBedId(Number(e.target.value))}
                        required
                      >
                        {availableBeds.map((b) => (
                          <option key={b.id} value={b.id}>
                            {b.bedNumber} ({b.bedType})
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div className="flex flex-col gap-xs">
                    <label className="text-label-sm">Transfer Reason / Notes:</label>
                    <input
                      type="text"
                      className="input-text"
                      placeholder="e.g. Step down from ICU to General Ward"
                      value={actionNotes}
                      onChange={(e) => setActionNotes(e.target.value)}
                    />
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={actionLoading || availableBeds.length === 0}
                  >
                    {actionLoading ? 'Transferring...' : 'Execute Patient Transfer'}
                  </button>
                </form>
              )}

              {/* Discharge Form */}
              {actionType === 'discharge' && (
                <form onSubmit={handleDischarge} className="flex flex-col gap-sm" style={{ marginTop: 'var(--space-sm)' }}>
                  <div className="flex flex-col gap-xs">
                    <label className="text-label-sm">Discharge Summary Notes:</label>
                    <input
                      type="text"
                      className="input-text"
                      placeholder="e.g. Fully recovered, outpatient follow-up scheduled"
                      value={actionNotes}
                      onChange={(e) => setActionNotes(e.target.value)}
                    />
                  </div>

                  <p className="text-label-sm" style={{ color: 'var(--outline)' }}>
                    Discharging releases Bed #{selectedPatient.currentBedId} to CLEANING status, triggering the turnaround pipeline.
                  </p>

                  <button
                    type="submit"
                    className="btn btn-danger"
                    disabled={actionLoading}
                  >
                    {actionLoading ? 'Discharging...' : 'Confirm Discharge & Free Bed'}
                  </button>
                </form>
              )}
            </div>

            {/* Patient Flow History Timeline */}
            <div className="card" style={{ padding: 'var(--space-md)' }}>
              <h4 className="text-label-lg" style={{ fontWeight: 600, marginBottom: 'var(--space-sm)' }}>
                Patient Transit History ({history.length})
              </h4>

              {historyLoading ? (
                <div style={{ padding: 'var(--space-sm)', textAlign: 'center', color: 'var(--outline)' }}>
                  Loading patient timeline...
                </div>
              ) : history.length === 0 ? (
                <p className="text-body-sm" style={{ color: 'var(--outline)' }}>
                  No transit transitions recorded yet.
                </p>
              ) : (
                <div className="flex flex-col gap-sm">
                  {history.map((e) => (
                    <div
                      key={e.id}
                      style={{
                        padding: '8px 10px',
                        backgroundColor: 'var(--surface-container-low)',
                        borderRadius: 'var(--radius-md)',
                        borderLeft: '3px solid var(--primary)',
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-label-sm" style={{ fontWeight: 700, color: 'var(--primary)' }}>
                          {e.eventType.replace(/_/g, ' ')}
                        </span>
                        <span className="text-label-sm font-tabular" style={{ color: 'var(--outline)', fontSize: '11px' }}>
                          {new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>

                      <div className="text-body-sm" style={{ marginTop: '2px' }}>
                        {e.notes || 'State transition recorded'}
                      </div>

                      <div className="text-label-sm" style={{ color: 'var(--outline)', fontSize: '11px', marginTop: '4px' }}>
                        Actor: {e.actorName} ({e.actorId}) • Source: {e.source}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </SidePanel>

      {/* Registration Modal */}
      {showRegisterModal && (
        <div className="side-panel-overlay" onClick={() => setShowRegisterModal(false)}>
          <div
            className="card"
            style={{
              width: '420px',
              maxWidth: '90vw',
              margin: 'auto',
              padding: 'var(--space-xl)',
              backgroundColor: 'var(--surface-container-lowest)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-md)' }}>
              <h3 className="text-headline-sm" style={{ fontWeight: 700 }}>
                Register New Patient
              </h3>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => setShowRegisterModal(false)}
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleRegisterPatient} className="flex flex-col gap-md">
              <div className="flex flex-col gap-xs">
                <label className="text-label-sm">Full Legal Name:</label>
                <input
                  type="text"
                  className="input-text"
                  required
                  placeholder="e.g. Eleanor Vance"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                />
              </div>

              <div className="flex items-center gap-md">
                <div className="flex flex-col gap-xs" style={{ flex: 1 }}>
                  <label className="text-label-sm">Age:</label>
                  <input
                    type="number"
                    min="0"
                    max="130"
                    className="input-text"
                    required
                    value={regAge}
                    onChange={(e) => setRegAge(Number(e.target.value))}
                  />
                </div>
                <div className="flex flex-col gap-xs" style={{ flex: 1 }}>
                  <label className="text-label-sm">Gender:</label>
                  <select
                    className="select-control"
                    value={regGender}
                    onChange={(e) => setRegGender(e.target.value)}
                  >
                    <option value="Female">Female</option>
                    <option value="Male">Male</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="flex flex-col gap-xs">
                <label className="text-label-sm">Medical Record Number (MRN):</label>
                <input
                  type="text"
                  className="input-text"
                  placeholder="Leave blank to auto-generate"
                  value={regMrn}
                  onChange={(e) => setRegMrn(e.target.value)}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={actionLoading}
                style={{ marginTop: 'var(--space-sm)' }}
              >
                {actionLoading ? 'Registering...' : 'Register Patient'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
