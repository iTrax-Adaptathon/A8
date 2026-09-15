// Domain Enums matching backend app.domain.enums

export type PatientStatus = 'REGISTERED' | 'ADMITTED' | 'TRANSFERRED' | 'DISCHARGED';

export type BedStatus = 'AVAILABLE' | 'OCCUPIED' | 'CLEANING' | 'MAINTENANCE';

export type BedType = 'GENERAL' | 'ICU' | 'EMERGENCY' | 'PEDIATRIC' | 'SURGICAL';

export type TheatreStatus = 'AVAILABLE' | 'IN_USE' | 'CLEANING' | 'UNAVAILABLE';

export type TheatreSlotStatus = 'AVAILABLE' | 'BOOKED' | 'COMPLETED' | 'CANCELLED';

export type SurgeryStatus = 'WAITING' | 'SCHEDULED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';

export type StaffRole = 'SURGEON' | 'ANAESTHETIST' | 'DOCTOR' | 'NURSE' | 'PORTER';

export type StaffStatus = 'AVAILABLE' | 'ASSIGNED' | 'OFF_DUTY';

export type StaffAssignmentType = 'SURGERY' | 'PATIENT';

export type StaffAssignmentStatus = 'ACTIVE' | 'RELEASED';

export type WaitlistResourceType = 'BED' | 'THEATRE' | 'STAFF';

export type WaitlistStatus = 'WAITING' | 'FULFILLED' | 'CANCELLED';

export type ResourceType =
  | 'PATIENT'
  | 'BED'
  | 'DEPARTMENT'
  | 'THEATRE'
  | 'THEATRE_SLOT'
  | 'SURGERY'
  | 'STAFF'
  | 'STAFF_ASSIGNMENT'
  | 'WAITLIST_ENTRY';

export type EventSource = 'MANUAL' | 'AUTO_MATCH' | 'SYSTEM' | 'SEED';

export type FlowEventType =
  | 'ADMISSION'
  | 'TRANSFER'
  | 'DISCHARGE'
  | 'BED_ASSIGNMENT'
  | 'BED_RELEASE'
  | 'RESOURCE_CREATED'
  | 'RESOURCE_DEACTIVATED'
  | 'BED_STATUS_CHANGE'
  | 'THEATRE_STATUS_CHANGE'
  | 'THEATRE_SLOT_CREATED'
  | 'THEATRE_SLOT_BOOKED'
  | 'THEATRE_SLOT_RELEASED'
  | 'THEATRE_SLOT_CANCELLED'
  | 'THEATRE_SLOT_COMPLETED'
  | 'SURGERY_CREATED'
  | 'SURGERY_SCHEDULED'
  | 'SURGERY_UNSCHEDULED'
  | 'SURGERY_STARTED'
  | 'SURGERY_COMPLETED'
  | 'SURGERY_CANCELLED'
  | 'STAFF_STATUS_CHANGE'
  | 'STAFF_ASSIGNED'
  | 'STAFF_RELEASED'
  | 'WAITLIST_ADDED'
  | 'WAITLIST_REMOVED'
  | 'WAITLIST_FULFILLED'
  | 'MATCH_IDENTIFIED'
  | 'ASSIGNMENT_REJECTED';

export type CapacityAlertLevel = 'NORMAL' | 'HIGH_UTILIZATION' | 'CRITICAL_CAPACITY';

// Capacity Schemas
export interface DepartmentUtilization {
  departmentId: number;
  departmentName: string;
  departmentCode: string;
  totalBeds: number;
  occupiedBeds: number;
  availableBeds: number;
  cleaningBeds: number;
  maintenanceBeds: number;
  occupancyPercentage: number;
  alertLevel: CapacityAlertLevel;
}

export interface BedCapacity {
  total: number;
  available: number;
  occupied: number;
  cleaning: number;
  maintenance: number;
}

export interface TheatreCapacity {
  total: number;
  available: number;
  inUse: number;
  cleaning: number;
  unavailable: number;
  bookedSlots: number;
  availableSlots: number;
  nextAvailableSlot: string | null;
}

export interface StaffCapacity {
  total: number;
  available: number;
  assigned: number;
  offDuty: number;
}

export interface QueueCapacity {
  waitingForBeds: number;
  waitingForTheatres: number;
  waitingForStaff: number;
}

export interface CapacityMetrics {
  totalBeds: number;
  occupiedBeds: number;
  availableBeds: number;
  overallOccupancyPercentage: number;
  overallAlertLevel: CapacityAlertLevel;
  departmentMetrics: DepartmentUtilization[];
  highUtilizationDepartments: string[];
  criticalCapacityDepartments: string[];
  beds: BedCapacity;
  theatres: TheatreCapacity;
  staff: StaffCapacity;
  queues: QueueCapacity;
  generatedAt: string;
}

// Department
export interface Department {
  id: number;
  name: string;
  code: string;
  totalBeds: number;
  occupiedBeds: number;
  isActive: boolean;
  createdAt?: string;
}

// Bed Schemas
export interface Bed {
  id: number;
  bedNumber: string;
  bedType: BedType;
  departmentId: number;
  status: BedStatus;
  currentPatientId?: number | null;
  isActive: boolean;
  createdAt?: string;
}

export interface BedStatusUpdate {
  newStatus: BedStatus;
  notes?: string;
  autoAssign?: boolean;
}

export interface BedRelease {
  notes?: string;
  autoAssign?: boolean;
}

export interface AutoAssignment {
  resourceType: ResourceType;
  resourceId: number;
  matched: boolean;
  waitlistEntryId?: number | null;
  patientId?: number | null;
  surgeryId?: number | null;
  reason?: string | null;
  candidatesEvaluated: number;
  rejections: Array<Record<string, unknown>>;
}

export interface BedReleaseResponse {
  bed: Bed;
  autoAssignment?: AutoAssignment | null;
}

// Patient Schemas
export interface Patient {
  id: number;
  name: string;
  age: number;
  gender: string;
  medicalRecordNumber: string;
  currentStatus: PatientStatus;
  currentDepartmentId?: number | null;
  currentBedId?: number | null;
  admittedAt?: string | null;
  dischargedAt?: string | null;
  createdAt?: string;
}

export interface PatientCreate {
  name: string;
  age: number;
  gender: string;
  medicalRecordNumber: string;
}

export interface PatientAdmit {
  departmentId: number;
  bedId: number;
  notes?: string;
}

export interface PatientTransfer {
  targetDepartmentId: number;
  targetBedId: number;
  notes?: string;
}

export interface PatientDischarge {
  notes?: string;
}

// Theatre Schemas
export interface Theatre {
  id: number;
  name: string;
  departmentId: number;
  status: TheatreStatus;
  isActive: boolean;
  createdAt?: string;
}

export interface TheatreStatusUpdate {
  newStatus: TheatreStatus;
  notes?: string;
  autoAssign?: boolean;
}

export interface TheatreRelease {
  notes?: string;
  autoAssign?: boolean;
}

export interface TheatreReleaseResponse {
  theatre: Theatre;
  autoAssignments: AutoAssignment[];
}

export interface TheatreSlot {
  id: number;
  theatreId: number;
  startTime: string;
  endTime: string;
  durationMinutes: number;
  status: TheatreSlotStatus;
  surgeryId?: number | null;
  createdAt?: string;
}

export interface TheatreSlotCreate {
  theatreId: number;
  startTime: string;
  endTime: string;
  autoAssign?: boolean;
}

export interface TheatreSlotCreateResponse {
  slot: TheatreSlot;
  autoAssignment?: AutoAssignment | null;
}

// Surgery Schemas
export interface Surgery {
  id: number;
  patientId: number;
  departmentId: number;
  procedureName: string;
  durationMinutes: number;
  priority: number;
  status: SurgeryStatus;
  theatreId?: number | null;
  slotId?: number | null;
  requiredStaffRole?: StaffRole | null;
  createdAt?: string;
  scheduledAt?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
}

export interface SurgerySchedule {
  slotId: number;
  notes?: string;
}

export interface SurgeryAction {
  notes?: string;
  autoAssign?: boolean;
}

export interface SurgeryActionResponse {
  surgery: Surgery;
  autoAssignments: AutoAssignment[];
}

// Staff Schemas
export interface Staff {
  id: number;
  name: string;
  role: StaffRole;
  departmentId: number;
  shiftStart: string;
  shiftEnd: string;
  status: StaffStatus;
  isActive: boolean;
  createdAt?: string;
}

export interface StaffStatusUpdate {
  newStatus: StaffStatus;
  notes?: string;
  autoAssign?: boolean;
}

export interface StaffAssign {
  assignmentType: StaffAssignmentType;
  surgeryId?: number | null;
  patientId?: number | null;
  requiredRole?: StaffRole | null;
  notes?: string;
}

export interface StaffAssignment {
  id: number;
  staffId: number;
  assignmentType: StaffAssignmentType;
  surgeryId?: number | null;
  patientId?: number | null;
  departmentId: number;
  startTime: string;
  endTime?: string | null;
  status: StaffAssignmentStatus;
  releasedAt?: string | null;
}

export interface StaffAssignmentRelease {
  notes?: string;
  autoAssign?: boolean;
}

export interface StaffAssignmentReleaseResponse {
  assignment: StaffAssignment;
  autoAssignment?: AutoAssignment | null;
}

// Waitlist Schemas
export interface WaitlistEntry {
  id: number;
  patientId: number;
  resourceType: WaitlistResourceType;
  departmentId: number;
  priority: number;
  requestedAt: string;
  status: WaitlistStatus;
  reason: string;
  surgeryId?: number | null;
  requiredBedType?: BedType | null;
  requiredStaffRole?: StaffRole | null;
  fulfilledAt?: string | null;
  fulfilledResourceId?: number | null;
}

export interface WaitlistCreate {
  patientId: number;
  resourceType: WaitlistResourceType;
  departmentId: number;
  priority?: number;
  reason?: string;
  requiredBedType?: BedType;
  requiredStaffRole?: StaffRole;
  surgeryId?: number;
}

// Matching Schemas
export interface MatchCandidate {
  rank: number;
  waitlistEntryId: number;
  patientId: number;
  surgeryId?: number | null;
  priority: number;
  requestedAt: string;
  reason: string;
}

export interface MatchResult {
  resourceType: ResourceType;
  resourceId: number;
  resourceAvailable: boolean;
  departmentId?: number | null;
  candidates: MatchCandidate[];
}

export interface MatchConfirm {
  resourceType: ResourceType; // BED | THEATRE_SLOT | STAFF
  resourceId: number;
  waitlistEntryId: number;
  notes?: string;
}

// Flow Event Schemas
export interface FlowEvent {
  id: number;
  eventType: FlowEventType;
  patientId?: number | null;
  fromDepartmentId?: number | null;
  toDepartmentId?: number | null;
  fromBedId?: number | null;
  toBedId?: number | null;
  timestamp: string;
  notes: string;
  resourceType?: ResourceType | null;
  resourceId?: number | null;
  departmentId?: number | null;
  previousState?: string | null;
  newState?: string | null;
  actorId: string;
  actorName: string;
  source: EventSource;
  metadata?: Record<string, unknown>;
}

// Realtime WebSocket Message
export interface RealtimeMessage {
  type: string;
  resourceType: string;
  resourceId?: number | null;
  patientId?: number | null;
  departmentId?: number | null;
  previousState?: string | null;
  newState?: string | null;
  actorId: string;
  source: string;
  timestamp: string;
}
