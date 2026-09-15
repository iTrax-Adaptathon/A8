import { apiFetch, ApiResponse } from './client';
import {
  CapacityMetrics,
  Department,
  Bed,
  BedStatusUpdate,
  BedRelease,
  BedReleaseResponse,
  Theatre,
  TheatreStatusUpdate,
  TheatreRelease,
  TheatreReleaseResponse,
  TheatreSlot,
  TheatreSlotCreate,
  TheatreSlotCreateResponse,
  Surgery,
  Staff,
  StaffStatusUpdate,
  StaffAssignment,
  StaffAssignmentReleaseResponse,
  Patient,
  PatientCreate,
  PatientAdmit,
  PatientTransfer,
  PatientDischarge,
  WaitlistEntry,
  MatchResult,
  MatchConfirm,
  AutoAssignment,
  FlowEvent,
  BedStatus,
  BedType,
  TheatreStatus,
  TheatreSlotStatus,
  StaffRole,
  StaffStatus,
  StaffAssignmentStatus,
  PatientStatus,
  WaitlistResourceType,
  WaitlistStatus,
  ResourceType,
  FlowEventType,
} from './types';

// Helper to build URL query strings
function buildQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.append(key, String(value));
    }
  }
  const str = search.toString();
  return str ? `?${str}` : '';
}

// ---------------------------------------------------------------------------
// 1. Capacity & Departments
// ---------------------------------------------------------------------------
export async function getCapacity(): Promise<CapacityMetrics> {
  const res = await apiFetch<CapacityMetrics>('/capacity');
  return res.data;
}

export async function getDepartments(): Promise<Department[]> {
  const res = await apiFetch<Department[]>('/departments');
  return res.data;
}

// ---------------------------------------------------------------------------
// 2. Beds
// ---------------------------------------------------------------------------
export interface GetBedsParams {
  departmentId?: number;
  status?: BedStatus;
  bedType?: BedType;
  includeInactive?: boolean;
  limit?: number;
  offset?: number;
}

export async function getBeds(params: GetBedsParams = {}): Promise<ApiResponse<Bed[]>> {
  const query = buildQuery({
    departmentId: params.departmentId,
    status: params.status,
    bedType: params.bedType,
    includeInactive: params.includeInactive,
    limit: params.limit,
    offset: params.offset,
  });
  return apiFetch<Bed[]>(`/beds${query}`);
}

export async function getAvailableBeds(departmentId?: number): Promise<Bed[]> {
  const query = buildQuery({ departmentId });
  const res = await apiFetch<Bed[]>(`/beds/available${query}`);
  return res.data;
}

export async function getBed(id: number): Promise<Bed> {
  const res = await apiFetch<Bed>(`/beds/${id}`);
  return res.data;
}

export async function updateBedStatus(id: number, payload: BedStatusUpdate): Promise<Bed> {
  const res = await apiFetch<Bed>(`/beds/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function releaseBed(id: number, payload: BedRelease = {}): Promise<BedReleaseResponse> {
  const res = await apiFetch<BedReleaseResponse>(`/beds/${id}/release`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.data;
}

// ---------------------------------------------------------------------------
// 3. Theatres & Slots
// ---------------------------------------------------------------------------
export interface GetTheatresParams {
  departmentId?: number;
  status?: TheatreStatus;
  includeInactive?: boolean;
  limit?: number;
  offset?: number;
}

export async function getTheatres(params: GetTheatresParams = {}): Promise<ApiResponse<Theatre[]>> {
  const query = buildQuery({
    departmentId: params.departmentId,
    status: params.status,
    includeInactive: params.includeInactive,
    limit: params.limit,
    offset: params.offset,
  });
  return apiFetch<Theatre[]>(`/theatres${query}`);
}

export async function updateTheatreStatus(id: number, payload: TheatreStatusUpdate): Promise<Theatre> {
  const res = await apiFetch<Theatre>(`/theatres/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function releaseTheatre(id: number, payload: TheatreRelease = {}): Promise<TheatreReleaseResponse> {
  const res = await apiFetch<TheatreReleaseResponse>(`/theatres/${id}/release`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.data;
}

export interface GetSlotsParams {
  theatreId?: number;
  status?: TheatreSlotStatus;
  surgeryId?: number;
  limit?: number;
  offset?: number;
}

export async function getTheatreSlots(params: GetSlotsParams = {}): Promise<ApiResponse<TheatreSlot[]>> {
  const query = buildQuery({
    theatreId: params.theatreId,
    status: params.status,
    surgeryId: params.surgeryId,
    limit: params.limit,
    offset: params.offset,
  });
  return apiFetch<TheatreSlot[]>(`/theatre-slots${query}`);
}

export async function createTheatreSlot(payload: TheatreSlotCreate): Promise<TheatreSlotCreateResponse> {
  const res = await apiFetch<TheatreSlotCreateResponse>('/theatre-slots', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function cancelTheatreSlot(id: number, notes?: string): Promise<TheatreSlot> {
  const res = await apiFetch<TheatreSlot>(`/theatre-slots/${id}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ notes: notes || '' }),
  });
  return res.data;
}

export async function getSurgeries(params: { status?: string; departmentId?: number; limit?: number } = {}): Promise<ApiResponse<Surgery[]>> {
  const query = buildQuery(params);
  return apiFetch<Surgery[]>(`/surgeries${query}`);
}

// ---------------------------------------------------------------------------
// 4. Staff & Assignments
// ---------------------------------------------------------------------------
export interface GetStaffParams {
  departmentId?: number;
  role?: StaffRole;
  status?: StaffStatus;
  includeInactive?: boolean;
  limit?: number;
  offset?: number;
}

export async function getStaff(params: GetStaffParams = {}): Promise<ApiResponse<Staff[]>> {
  const query = buildQuery({
    departmentId: params.departmentId,
    role: params.role,
    status: params.status,
    includeInactive: params.includeInactive,
    limit: params.limit,
    offset: params.offset,
  });
  return apiFetch<Staff[]>(`/staff${query}`);
}

export async function updateStaffStatus(id: number, payload: StaffStatusUpdate): Promise<Staff> {
  const res = await apiFetch<Staff>(`/staff/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function getStaffAssignments(params: { staffId?: number; status?: StaffAssignmentStatus } = {}): Promise<ApiResponse<StaffAssignment[]>> {
  const query = buildQuery(params);
  return apiFetch<StaffAssignment[]>(`/staff-assignments${query}`);
}

export async function releaseStaffAssignment(id: number, notes?: string): Promise<StaffAssignmentReleaseResponse> {
  const res = await apiFetch<StaffAssignmentReleaseResponse>(`/staff-assignments/${id}/release`, {
    method: 'POST',
    body: JSON.stringify({ notes: notes || '' }),
  });
  return res.data;
}

// ---------------------------------------------------------------------------
// 5. Patients
// ---------------------------------------------------------------------------
export interface GetPatientsParams {
  status?: PatientStatus;
  departmentId?: number;
  limit?: number;
  offset?: number;
}

export async function getPatients(params: GetPatientsParams = {}): Promise<ApiResponse<Patient[]>> {
  const query = buildQuery({
    status: params.status,
    departmentId: params.departmentId,
    limit: params.limit,
    offset: params.offset,
  });
  return apiFetch<Patient[]>(`/patients${query}`);
}

export async function getPatient(id: number): Promise<Patient> {
  const res = await apiFetch<Patient>(`/patients/${id}`);
  return res.data;
}

export async function createPatient(payload: PatientCreate): Promise<Patient> {
  const res = await apiFetch<Patient>('/patients', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function admitPatient(id: number, payload: PatientAdmit): Promise<Patient> {
  const res = await apiFetch<Patient>(`/patients/${id}/admit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function transferPatient(id: number, payload: PatientTransfer): Promise<Patient> {
  const res = await apiFetch<Patient>(`/patients/${id}/transfer`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function dischargePatient(id: number, payload: PatientDischarge = {}): Promise<Patient> {
  const res = await apiFetch<Patient>(`/patients/${id}/discharge`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function getPatientHistory(id: number, limit = 50, offset = 0): Promise<ApiResponse<FlowEvent[]>> {
  const query = buildQuery({ limit, offset });
  return apiFetch<FlowEvent[]>(`/patients/${id}/history${query}`);
}

// ---------------------------------------------------------------------------
// 6. Waitlist & Matching
// ---------------------------------------------------------------------------
export interface GetWaitlistParams {
  resourceType?: WaitlistResourceType;
  departmentId?: number;
  status?: WaitlistStatus | '';
  patientId?: number;
  limit?: number;
  offset?: number;
}

export async function getWaitlist(params: GetWaitlistParams = {}): Promise<ApiResponse<WaitlistEntry[]>> {
  const query = buildQuery({
    resourceType: params.resourceType,
    departmentId: params.departmentId,
    status: params.status,
    patientId: params.patientId,
    limit: params.limit,
    offset: params.offset,
  });
  return apiFetch<WaitlistEntry[]>(`/waitlist${query}`);
}

export async function cancelWaitlistEntry(id: number): Promise<WaitlistEntry> {
  const res = await apiFetch<WaitlistEntry>(`/waitlist/${id}`, {
    method: 'DELETE',
  });
  return res.data;
}

// GET /matches is on-demand for a single resource (BED, THEATRE_SLOT, or STAFF)
export async function getMatches(resourceType: ResourceType, resourceId: number): Promise<MatchResult> {
  const query = buildQuery({ resourceType, resourceId });
  const res = await apiFetch<MatchResult>(`/matches${query}`);
  return res.data;
}

export async function confirmMatch(payload: MatchConfirm): Promise<AutoAssignment> {
  const res = await apiFetch<AutoAssignment>('/matches/confirm', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.data;
}

// ---------------------------------------------------------------------------
// 7. Flow Events (Audit Log)
// ---------------------------------------------------------------------------
export interface GetFlowEventsParams {
  patientId?: number;
  resourceType?: ResourceType;
  resourceId?: number;
  eventType?: FlowEventType;
  departmentId?: number;
  limit?: number;
  offset?: number;
}

export async function getFlowEvents(params: GetFlowEventsParams = {}): Promise<ApiResponse<FlowEvent[]>> {
  const query = buildQuery({
    patientId: params.patientId,
    resourceType: params.resourceType,
    resourceId: params.resourceId,
    eventType: params.eventType,
    departmentId: params.departmentId,
    limit: params.limit,
    offset: params.offset,
  });
  return apiFetch<FlowEvent[]>(`/flow-events${query}`);
}
