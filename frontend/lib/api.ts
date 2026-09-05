export interface Client {
  client_id: string
  name: string
  email: string
  billing_rate: number
  outstanding_balance: number
  open_invoices: number
  uninvoiced_milestones: number
  updated_at?: string
}

export type ActionType = "invoice" | "change_order" | "dunning_email"
export type ActionStatus =
  | "pending"
  | "approved"
  | "edited"
  | "rejected"
  | "executed"

export interface PendingAction {
  action_id: string
  client_id: string
  client_name?: string
  action_type: ActionType
  escalation_tier?: string | null
  drafted_content: string
  agent_reasoning: string
  status: ActionStatus
  amount?: number
  due_date?: string
  milestone_name?: string
  created_at?: string
  resolved_at?: string | null
}

export interface ScheduledCheckSummary {
  clients_checked: number
  skipped_scope_scan?: boolean
  proposals_persisted: number
  by_type: Record<string, number>
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "/api"

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  const body = await response.json()
  if (!response.ok) {
    throw new Error((body as { error?: string }).error ?? `HTTP ${response.status}`)
  }
  return body as T
}

export function listClients(): Promise<Client[]> {
  return request<Client[]>("/clients")
}

export function listPendingActions(): Promise<PendingAction[]> {
  return request<PendingAction[]>("/actions/pending")
}

export function listActivityLog(): Promise<PendingAction[]> {
  return request<PendingAction[]>("/activity-log")
}

export function resolveAction(
  actionId: string,
  decision: "approved" | "edited" | "rejected",
  editedContent?: string,
): Promise<PendingAction> {
  return request<PendingAction>(`/actions/${actionId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ decision, edited_content: editedContent }),
  })
}

export function markMilestoneComplete(
  clientId: string,
  name: string,
  amount: number,
): Promise<PendingAction | { note: string }> {
  return request<PendingAction | { note: string }>(
    `/clients/${clientId}/milestone-complete`,
    {
      method: "POST",
      body: JSON.stringify({ name, amount }),
    },
  )
}

export function runScheduledCheck(): Promise<ScheduledCheckSummary> {
  return request<ScheduledCheckSummary>("/run-scheduled-check", {
    method: "POST",
    body: JSON.stringify({}),
  })
}
