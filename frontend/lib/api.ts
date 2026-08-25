export type Client = { client_id: string; name: string; email: string; billing_rate: number; overdue_days?: number; payment_history?: { status: string }[] };
export type Action = { action_id: string; client_id: string; action_type: string; drafted_content: string; agent_reasoning: string; status: string };

export const demoClients: Client[] = [
  { client_id: "demo_on_time", name: "Northstar Studio", email: "maya@northstar.example", billing_rate: 95, payment_history: [{ status: "paid" }] },
  { client_id: "demo_late", name: "Marcus Chen", email: "marcus@chen.example", billing_rate: 85, overdue_days: 8, payment_history: [{ status: "unpaid" }] },
  { client_id: "demo_scope", name: "Aster House", email: "hello@aster.example", billing_rate: 75, payment_history: [{ status: "paid" }] },
];
export const demoActions: Action[] = [
  { action_id: "demo_day7", client_id: "demo_late", action_type: "dunning_email", drafted_content: "Subject: Overdue invoice #0231\n\nHi Marcus,\n\nInvoice #0231 is now 8 days past due. Please arrange payment at your convenience.", agent_reasoning: "Invoice #0231 passed the 7-day threshold; no prior day_7 notice has been sent.", status: "pending" },
  { action_id: "demo_scope", client_id: "demo_scope", action_type: "change_order", drafted_content: "Change order: dark mode toggle", agent_reasoning: "Dark mode toggle is not listed in the SOW; estimated 3 hours at $75.00/hr = $225.00.", status: "pending" },
];
export const demoActivity: Action[] = [{ action_id: "demo_paid", client_id: "demo_on_time", action_type: "dunning_email", drafted_content: "", agent_reasoning: "Invoice #0218 was paid before the first reminder threshold.", status: "executed" }];

const base = process.env.NEXT_PUBLIC_API_URL || "";
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, { ...options, headers: { "content-type": "application/json", ...(options?.headers || {}) } });
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return response.json();
}
export const api = {
  clients: () => request<Client[]>("/clients"),
  pending: () => request<Action[]>("/actions/pending"),
  activity: () => request<Action[]>("/activity-log"),
  resolve: (id: string, decision: string, edited_content?: string) => request<Action>(`/actions/${id}/resolve`, { method: "POST", body: JSON.stringify({ decision, edited_content }) }),
};
