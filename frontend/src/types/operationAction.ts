export type OperationActionStatus = 'OPEN' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED'
export type OperationActionPriority = 'LOW' | 'MEDIUM' | 'HIGH'
export type OperationActionSourceType = 'ANOMALY' | 'QUALITY' | 'SCORE' | 'MANUAL'
export type OperationActionEventType = 'CREATE' | 'ASSIGN' | 'STATUS_CHANGE' | 'COMMENT' | 'CLOSE'

export interface ActionUser { user_id: number; username: string; display_name: string | null; role_code: 'ADMINISTRATOR' | 'USER' }
export interface ActionSource { source_id: number; source_type: OperationActionSourceType; source_reference_id: number | null; source_evidence_summary: string; source_analysis_as_of: string | null; source_algorithm_version: string | null; created_at: string }
export interface ActionHistory { history_id: number; event_type: OperationActionEventType; old_status: OperationActionStatus | null; new_status: OperationActionStatus | null; operator_user_id: number; comment: string | null; created_at: string }
export interface OperationAction { action_id: number; drama_id: number | null; title: string; description: string | null; priority: OperationActionPriority; status: OperationActionStatus; assignee_user: ActionUser | null; creator_user: ActionUser; due_date: string | null; created_at: string; updated_at: string; sources: ActionSource[]; history: ActionHistory[] }
export interface OperationActionPage { page: number; page_size: number; total: number; items: OperationAction[] }
export interface OperationActionStatistics { total: number; OPEN: number; IN_PROGRESS: number; COMPLETED: number; CANCELLED: number }
export interface ActionSourceRequest { source_type: OperationActionSourceType; source_reference_id?: number; source_evidence_summary: string; source_analysis_as_of?: string; source_algorithm_version?: string }
export interface CreateActionRequest { title: string; description?: string; priority: OperationActionPriority; drama_id?: number; assignee_user_id?: number; due_date?: string; source?: ActionSourceRequest }
export interface ActionQuery { status?: OperationActionStatus; priority?: OperationActionPriority; assignee_user_id?: number; drama_id?: number; page?: number; page_size?: number }
