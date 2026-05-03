/**
 * E2E テスト共通ヘルパー
 *
 * シードデータ定数（SQLite 直挿入済み）を参照するだけ。
 * テスト実行前に backend コンテナ内で seed スクリプトが実行済みであること前提。
 */

export const EMPIRE_ID = "00000000-0000-0000-0000-000000000001";
export const ROOM_ID = "e2e00000-0000-0000-0000-000000000031";

export const TASK_PENDING_ID = "e2e00000-0000-0000-0000-000000000051";
export const TASK_INPROG_ID = "e2e00000-0000-0000-0000-000000000052";
export const TASK_DONE_ID = "e2e00000-0000-0000-0000-000000000053";
export const TASK_REVIEW_ID = "e2e00000-0000-0000-0000-000000000054"; // AWAITING_EXTERNAL_REVIEW (gate for 404 test)
export const TASK_APPROVE_ID = "e2e00000-0000-0000-0000-000000000055"; // Gate 承認テスト用
export const TASK_REJECT_ID = "e2e00000-0000-0000-0000-000000000056"; // Gate 差し戻しテスト用

export const GATE_REVIEW_ID = "e2e00000-0000-0000-0000-000000000071"; // task_review に紐付く
export const GATE_APPROVE_ID = "e2e00000-0000-0000-0000-000000000072"; // 承認テスト用（TC-E2E-CD-005）
export const GATE_REJECT_ID = "e2e00000-0000-0000-0000-000000000073"; // 差し戻しテスト用（TC-E2E-CD-006）

export const API_BASE = "http://localhost:8000";
