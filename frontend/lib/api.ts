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

// ---------------------------------------------------------------------------
// Seeded review desk (offline fallback)
//
// When no API is reachable the dashboard falls back to this static snapshot of
// the desk so demos, screenshots, and video recordings still work with zero
// infrastructure. It mirrors the persona data in scripts/seed_demo_data.py and
// the proposals a scheduled check would persist. Interactions here are local
// to the browser and are clearly labelled as such in the UI.
// ---------------------------------------------------------------------------

export interface SeededDesk {
  clients: Client[]
  pending: PendingAction[]
  activity: PendingAction[]
}

export const seededDesk: SeededDesk = {
  clients: [
    {
      client_id: "client_on_time",
      name: "Acme Goodpay",
      email: "accounts@acmegoodpay.example.com",
      billing_rate: 75,
      outstanding_balance: 0,
      open_invoices: 0,
      uninvoiced_milestones: 0,
    },
    {
      client_id: "client_late",
      name: "Northwind Traders",
      email: "accounts@northwind.example.com",
      billing_rate: 75,
      outstanding_balance: 1200,
      open_invoices: 1,
      uninvoiced_milestones: 0,
    },
    {
      client_id: "client_late14",
      name: "Beta Analytics",
      email: "finance@betaanalytics.example.com",
      billing_rate: 75,
      outstanding_balance: 3200,
      open_invoices: 1,
      uninvoiced_milestones: 0,
    },
    {
      client_id: "client_scope",
      name: "Lumen & Co",
      email: "hello@lumenco.example.com",
      billing_rate: 75,
      outstanding_balance: 0,
      open_invoices: 0,
      uninvoiced_milestones: 1,
    },
    {
      client_id: "client_clean",
      name: "Fern Studio",
      email: "billing@fernstudio.example.com",
      billing_rate: 75,
      outstanding_balance: 0,
      open_invoices: 0,
      uninvoiced_milestones: 0,
    },
  ],
  pending: [
    {
      action_id: "seed_day3_northwind",
      client_id: "client_late",
      client_name: "Northwind Traders",
      action_type: "dunning_email",
      escalation_tier: "day_3",
      drafted_content:
        "Subject: Friendly reminder — invoice inv_nw_002\n\nHi Northwind Traders,\n\nJust a friendly check-in on invoice inv_nw_002 ($1,200.00), which was due recently. No rush — could you let us know its status when you get a chance?\n\nThank you,\nCashflowGuardian",
      agent_reasoning:
        "Invoice inv_nw_002 is 6 days overdue; escalating to day_3 reminder (proposed, never auto-sent).",
      status: "pending",
      amount: 1200,
      created_at: "2026-09-03T09:00:00Z",
    },
    {
      action_id: "seed_day14_beta",
      client_id: "client_late14",
      client_name: "Beta Analytics",
      action_type: "dunning_email",
      escalation_tier: "day_14",
      drafted_content:
        "Subject: Final notice — invoice inv_ba_003\n\nHi Beta Analytics,\n\nWe have followed up twice on invoice inv_ba_003 ($3,200.00) and it remains outstanding. We value the work we do together, but we will need to pause further work until this is resolved.\n\nPlease reach out so we can sort this out together.\n\nThank you,\nCashflowGuardian",
      agent_reasoning:
        "Invoice inv_ba_003 is 20 days overdue; escalating to day_14 reminder (proposed, never auto-sent).",
      status: "pending",
      amount: 3200,
      created_at: "2026-09-03T09:00:00Z",
    },
    {
      action_id: "seed_invoice_lumen",
      client_id: "client_scope",
      client_name: "Lumen & Co",
      action_type: "invoice",
      drafted_content: "generated/invoice_lumen_mvp_launch.pdf",
      agent_reasoning:
        "Milestone 'MVP launch' completed; no invoice generated yet. Proposed invoice for $2,400.00 (PDF pending approval).",
      status: "pending",
      amount: 2400,
      due_date: "2026-09-17",
      milestone_name: "MVP launch",
      created_at: "2026-09-03T09:00:00Z",
    },
  ],
  activity: [
    {
      action_id: "seed_executed_acme",
      client_id: "client_on_time",
      client_name: "Acme Goodpay",
      action_type: "dunning_email",
      drafted_content: "",
      agent_reasoning:
        "Invoice inv_acme_001 was paid before the first reminder threshold.",
      status: "executed",
      created_at: "2026-09-01T08:30:00Z",
      resolved_at: "2026-09-01T08:30:00Z",
    },
  ],
}
