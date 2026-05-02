// API レスポンス型定義
// バックエンド Pydantic スキーマと 1:1 対応（詳細設計書 §確定 B 参照）

export type TaskStatus =
  | "PENDING"
  | "IN_PROGRESS"
  | "AWAITING_EXTERNAL_REVIEW"
  | "DONE"
  | "BLOCKED"
  | "CANCELLED";

export type GateDecision = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";

export interface DeliverableSnapshotResponse {
  id: string;
  body_markdown: string;
  acceptance_criteria: string;
  created_at: string;
}

export interface AuditEntryResponse {
  action: string;
  reviewer_id: string;
  comment: string | null;
  feedback_text: string | null;
  decided_at: string;
}

export interface GateDetailResponse {
  id: string;
  task_id: string;
  stage_id: string;
  decision: GateDecision;
  deliverable_snapshot: DeliverableSnapshotResponse;
  audit_trail: AuditEntryResponse[];
  required_gate_roles: string[];
  created_at: string;
}

export interface TaskResponse {
  id: string;
  status: TaskStatus;
  room_id: string;
  directive_id: string;
  current_stage_id: string;
  directive_text: string;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface RoomResponse {
  id: string;
  name: string;
  workflow_id: string;
}

export interface DirectiveWithTaskResponse {
  directive_id: string;
  task_id: string;
}

export interface ApiError {
  code: string;
  message: string;
  status: number;
}
