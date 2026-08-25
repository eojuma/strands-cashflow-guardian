export type Client = { client_id: string; name: string; email: string; billing_rate: number; payment_history?: { status: string }[] };
export type Action = { action_id: string; client_id: string; action_type: string; drafted_content: string; agent_reasoning: string; status: string };

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
