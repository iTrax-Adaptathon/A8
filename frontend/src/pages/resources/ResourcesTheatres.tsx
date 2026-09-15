import React, { useState, useEffect, useCallback } from 'react';
import {
  getTheatres,
  getTheatreSlots,
  updateTheatreStatus,
  releaseTheatre,
  createTheatreSlot,
  cancelTheatreSlot,
  getMatches,
  getDepartments,
} from '../../api/endpoints';
import {
  Theatre,
  TheatreSlot,
  Department,
  TheatreStatus,
  MatchResult,
} from '../../api/types';
import { useWebSocketEvent } from '../../api/websocket';
import { StatusBadge } from '../../components/common/StatusBadge';
import { SidePanel } from '../../components/common/SidePanel';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';

export const ResourcesTheatres: React.FC = () => {
  const [theatres, setTheatres] = useState<Theatre[]>([]);
  const [slots, setSlots] = useState<TheatreSlot[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filter
  const [selectedTheatreId, setSelectedTheatreId] = useState<string>('');

  // Selected Theatre for Detail Panel
  const [activeTheatre, setActiveTheatre] = useState<Theatre | null>(null);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // New Slot Form state
  const [showSlotForm, setShowSlotForm] = useState<boolean>(false);
  const [slotStartTime, setSlotStartTime] = useState<string>('');
  const [slotEndTime, setSlotEndTime] = useState<string>('');

  // On-demand matches for a slot (Rule 2)
  const [slotMatches, setSlotMatches] = useState<{ [slotId: number]: MatchResult }>({});
  const [matchingSlotId, setMatchingSlotId] = useState<number | null>(null);

  useEffect(() => {
    getDepartments().then(setDepartments).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [theatresRes, slotsRes] = await Promise.all([
        getTheatres(),
        getTheatreSlots({ limit: 100 }),
      ]);
      setTheatres(theatresRes.data);
      setSlots(slotsRes.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // WebSocket targeted updates
  useWebSocketEvent(['THEATRE_UPDATED', 'THEATRE_SLOT_UPDATED', 'SURGERY_UPDATED'], () => {
    fetchData();
  });

  const handleOpenTheatre = (t: Theatre) => {
    setActiveTheatre(t);
    setActionError(null);
    setActionSuccess(null);
    setShowSlotForm(false);
  };

  const handleClosePanel = () => {
    setActiveTheatre(null);
    setShowSlotForm(false);
  };

  // Release Theatre
  const handleReleaseTheatre = async (id: number) => {
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const res = await releaseTheatre(id, { notes: 'Theatre cleaned and sterilized', autoAssign: true });
      setActiveTheatre(res.theatre);
      setActionSuccess('Theatre released to AVAILABLE.');
      fetchData();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Update Theatre Status
  const handleUpdateTheatreStatus = async (id: number, newStatus: TheatreStatus) => {
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await updateTheatreStatus(id, { newStatus, autoAssign: true });
      setActiveTheatre(updated);
      setActionSuccess(`Theatre status updated to ${newStatus}.`);
      fetchData();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Create Theatre Slot
  const handleCreateSlot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTheatre || !slotStartTime || !slotEndTime) return;

    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      const startIso = new Date(slotStartTime).toISOString();
      const endIso = new Date(slotEndTime).toISOString();

      const res = await createTheatreSlot({
        theatreId: activeTheatre.id,
        startTime: startIso,
        endTime: endIso,
        autoAssign: true,
      });

      if (res.autoAssignment?.matched) {
        setActionSuccess(
          `Slot created! Auto-scheduled surgery #${res.autoAssignment.surgeryId}.`
        );
      } else {
        setActionSuccess('Operating theatre slot successfully scheduled.');
      }
      setShowSlotForm(false);
      setSlotStartTime('');
      setSlotEndTime('');
      fetchData();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionLoading(false);
    }
  };

  // Cancel Slot
  const handleCancelSlot = async (slotId: number) => {
    if (!window.confirm('Are you sure you want to cancel this theatre slot?')) return;
    setActionLoading(true);
    try {
      await cancelTheatreSlot(slotId, 'Operational cancellation');
      fetchData();
    } catch (err: unknown) {
      alert(`Error cancelling slot: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setActionLoading(false);
    }
  };

  // On-demand check matches for slot (Rule 2)
  const handleCheckSlotMatches = async (slotId: number) => {
    setMatchingSlotId(slotId);
    try {
      const res = await getMatches('THEATRE_SLOT', slotId);
      setSlotMatches((prev) => ({ ...prev, [slotId]: res }));
    } catch (err: unknown) {
      alert(`Could not check candidates: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setMatchingSlotId(null);
    }
  };

  const getDeptName = (deptId: number) => {
    const d = departments.find((dept) => dept.id === deptId);
    return d ? `${d.name} (${d.code})` : `Dept #${deptId}`;
  };

  const filteredTheatres = selectedTheatreId
    ? theatres.filter((t) => t.id === Number(selectedTheatreId))
    : theatres;

  return (
    <div className="flex flex-col gap-md">
      {/* Filter toolbar */}
      <div
        className="card flex items-center justify-between"
        style={{ padding: 'var(--space-sm) var(--space-md)' }}
      >
        <div className="flex items-center gap-sm">
          <div style={{ minWidth: '220px' }}>
            <select
              className="select-control"
              value={selectedTheatreId}
              onChange={(e) => setSelectedTheatreId(e.target.value)}
            >
              <option value="">All Operating Theatres</option>
              {theatres.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} — {t.status}
                </option>
              ))}
            </select>
          </div>
          {selectedTheatreId && (
            <button className="btn btn-outline btn-sm" onClick={() => setSelectedTheatreId('')}>
              Show All
            </button>
          )}
        </div>

        <div className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Showing <strong className="font-tabular">{filteredTheatres.length}</strong> theatres,{' '}
          <strong className="font-tabular">{slots.length}</strong> total slots
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={fetchData} />}

      {loading && theatres.length === 0 ? (
        <LoadingState message="Loading operating theatres..." />
      ) : (
        <div className="flex flex-col gap-lg">
          {filteredTheatres.map((theatre) => {
            const theatreSlots = slots.filter((s) => s.theatreId === theatre.id);

            return (
              <div key={theatre.id} className="card" style={{ padding: 'var(--space-lg)' }}>
                {/* Theatre Header */}
                <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-md)' }}>
                  <div>
                    <div className="flex items-center gap-sm">
                      <span className="text-headline-md" style={{ fontWeight: 700 }}>
                        {theatre.name}
                      </span>
                      <StatusBadge status={theatre.status} />
                    </div>
                    <p className="text-label-sm" style={{ color: 'var(--outline)', marginTop: '2px' }}>
                      {getDeptName(theatre.departmentId)} • Theatre ID #{theatre.id}
                    </p>
                  </div>

                  <div className="flex items-center gap-sm">
                    {theatre.status === 'CLEANING' && (
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleReleaseTheatre(theatre.id)}
                        disabled={actionLoading}
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                          cleaning_services
                        </span>
                        Release Cleaned
                      </button>
                    )}
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleOpenTheatre(theatre)}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                        tune
                      </span>
                      Manage Theatre & Slots
                    </button>
                  </div>
                </div>

                {/* Slots List for this theatre */}
                <div>
                  <h4
                    className="text-label-sm"
                    style={{
                      textTransform: 'uppercase',
                      color: 'var(--outline)',
                      letterSpacing: '0.04em',
                      marginBottom: 'var(--space-xs)',
                    }}
                  >
                    Scheduled Operating Slots ({theatreSlots.length})
                  </h4>

                  {theatreSlots.length === 0 ? (
                    <div
                      style={{
                        padding: 'var(--space-md)',
                        backgroundColor: 'var(--surface-container-low)',
                        borderRadius: 'var(--radius-md)',
                        color: 'var(--outline)',
                        fontSize: '13px',
                      }}
                    >
                      No slots currently scheduled for this theatre. Click &ldquo;Manage Theatre &amp; Slots&rdquo; to add a session.
                    </div>
                  ) : (
                    <div className="table-container">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Slot ID</th>
                            <th>Status</th>
                            <th>Start Time (UTC)</th>
                            <th>End Time (UTC)</th>
                            <th>Duration</th>
                            <th>Linked Surgery</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {theatreSlots.map((slot) => (
                            <tr key={slot.id}>
                              <td className="font-tabular" style={{ fontWeight: 600 }}>
                                #{slot.id}
                              </td>
                              <td>
                                <StatusBadge status={slot.status} />
                              </td>
                              <td className="font-tabular">
                                {new Date(slot.startTime).toLocaleString([], {
                                  month: 'short',
                                  day: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })}
                              </td>
                              <td className="font-tabular">
                                {new Date(slot.endTime).toLocaleString([], {
                                  month: 'short',
                                  day: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })}
                              </td>
                              <td className="font-tabular">{slot.durationMinutes} mins</td>
                              <td>
                                {slot.surgeryId ? (
                                  <span className="badge badge-occupied">Surgery #{slot.surgeryId}</span>
                                ) : (
                                  <span style={{ color: 'var(--outline)', fontSize: '12px' }}>Unassigned</span>
                                )}
                              </td>
                              <td>
                                <div className="flex items-center gap-xs">
                                  {slot.status === 'AVAILABLE' && (
                                    <>
                                      <button
                                        className="btn btn-outline btn-sm"
                                        style={{ fontSize: '11px', padding: '2px 6px' }}
                                        onClick={() => handleCheckSlotMatches(slot.id)}
                                        disabled={matchingSlotId === slot.id}
                                      >
                                        {matchingSlotId === slot.id ? 'Checking...' : 'Check Matches'}
                                      </button>
                                      <button
                                        className="btn btn-outline btn-sm"
                                        style={{ fontSize: '11px', padding: '2px 6px', color: 'var(--color-error)' }}
                                        onClick={() => handleCancelSlot(slot.id)}
                                      >
                                        Cancel
                                      </button>
                                    </>
                                  )}
                                </div>
                                {/* On-demand candidate preview under row */}
                                {slotMatches[slot.id] && (
                                  <div
                                    style={{
                                      marginTop: '4px',
                                      padding: '4px 8px',
                                      backgroundColor: 'var(--surface-container-low)',
                                      borderRadius: 'var(--radius-sm)',
                                      fontSize: '11px',
                                    }}
                                  >
                                    {slotMatches[slot.id].candidates.length === 0 ? (
                                      <span style={{ color: 'var(--outline)' }}>No waiting surgeries eligible</span>
                                    ) : (
                                      <span style={{ color: 'var(--primary)', fontWeight: 600 }}>
                                        {slotMatches[slot.id].candidates.length} candidate(s) ready: Top Priority #
                                        {slotMatches[slot.id].candidates[0].priority} (Surgery #
                                        {slotMatches[slot.id].candidates[0].surgeryId})
                                      </span>
                                    )}
                                  </div>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* SidePanel for Managing Theatre & Adding Slots */}
      <SidePanel
        isOpen={activeTheatre !== null}
        onClose={handleClosePanel}
        title={activeTheatre ? activeTheatre.name : ''}
        subtitle={activeTheatre ? `Theatre ID #${activeTheatre.id}` : undefined}
      >
        {activeTheatre && (
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

            {/* Current status card */}
            <div className="card" style={{ padding: 'var(--space-md)', backgroundColor: 'var(--surface-container-low)' }}>
              <div className="flex items-center justify-between">
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Current Status:
                </span>
                <StatusBadge status={activeTheatre.status} />
              </div>
              <div className="flex items-center justify-between" style={{ marginTop: 'var(--space-xs)' }}>
                <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                  Department:
                </span>
                <span className="text-label-md">{getDeptName(activeTheatre.departmentId)}</span>
              </div>
            </div>

            {/* Status control */}
            <div className="card" style={{ padding: 'var(--space-md)' }}>
              <h4 className="text-label-lg" style={{ fontWeight: 600, marginBottom: 'var(--space-sm)' }}>
                Theatre Status Actions
              </h4>
              <div className="flex items-center gap-xs" style={{ flexWrap: 'wrap' }}>
                {activeTheatre.status !== 'AVAILABLE' && (
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={actionLoading}
                    onClick={() => handleUpdateTheatreStatus(activeTheatre.id, 'AVAILABLE')}
                  >
                    Set AVAILABLE
                  </button>
                )}
                {activeTheatre.status !== 'CLEANING' && (
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={actionLoading}
                    onClick={() => handleUpdateTheatreStatus(activeTheatre.id, 'CLEANING')}
                  >
                    Set CLEANING
                  </button>
                )}
                {activeTheatre.status !== 'UNAVAILABLE' && (
                  <button
                    className="btn btn-outline btn-sm"
                    disabled={actionLoading}
                    onClick={() => handleUpdateTheatreStatus(activeTheatre.id, 'UNAVAILABLE')}
                  >
                    Set UNAVAILABLE
                  </button>
                )}
              </div>
            </div>

            {/* Add Slot form */}
            <div className="card" style={{ padding: 'var(--space-md)' }}>
              <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-sm)' }}>
                <h4 className="text-label-lg" style={{ fontWeight: 600 }}>
                  Create Operating Slot
                </h4>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => setShowSlotForm(!showSlotForm)}
                >
                  {showSlotForm ? 'Cancel' : '+ New Slot'}
                </button>
              </div>

              {showSlotForm && (
                <form onSubmit={handleCreateSlot} className="flex flex-col gap-sm">
                  <div className="flex flex-col gap-xs">
                    <label className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                      Slot Start Time (Local):
                    </label>
                    <input
                      type="datetime-local"
                      className="input-text"
                      required
                      value={slotStartTime}
                      onChange={(e) => setSlotStartTime(e.target.value)}
                    />
                  </div>

                  <div className="flex flex-col gap-xs">
                    <label className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
                      Slot End Time (Local):
                    </label>
                    <input
                      type="datetime-local"
                      className="input-text"
                      required
                      value={slotEndTime}
                      onChange={(e) => setSlotEndTime(e.target.value)}
                    />
                  </div>

                  <p className="text-label-sm" style={{ color: 'var(--outline)' }}>
                    Slot duration must be between 15 mins and 24 hours. The engine auto-matches waiting surgeries when the slot is created.
                  </p>

                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={actionLoading}
                    style={{ marginTop: 'var(--space-xs)' }}
                  >
                    {actionLoading ? 'Creating Slot...' : 'Schedule Slot & Auto-Match'}
                  </button>
                </form>
              )}
            </div>
          </div>
        )}
      </SidePanel>
    </div>
  );
};
