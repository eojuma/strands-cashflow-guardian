import { Client } from "../../lib/api";
export function ClientsPanel({ clients }: { clients: Client[] }) {
  return <section><h2>Clients</h2>{clients.length === 0 ? <p>No clients yet.</p> : clients.map(c => <article key={c.client_id} style={{ background: "white", padding: 16, marginBottom: 8, borderRadius: 8 }}><strong>{c.name}</strong><div>{c.email}</div><small>${c.billing_rate}/hr · {c.payment_history?.filter(i => i.status !== "paid").length || 0} open invoices</small></article>)}</section>;
}
