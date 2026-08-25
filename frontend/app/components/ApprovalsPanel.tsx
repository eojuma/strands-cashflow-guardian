import { Action } from "../../lib/api";
export function ApprovalsPanel({ actions, onResolve }: { actions: Action[]; onResolve: (id: string, decision: string) => void }) {
  return <section><h2>Pending approvals</h2>{actions.length === 0 ? <p>All caught up — no actions need review.</p> : actions.map(a => <article key={a.action_id} style={{ background: "white", padding: 16, marginBottom: 8, borderRadius: 8 }}><strong>{a.action_type}</strong><p>{a.agent_reasoning}</p><button onClick={() => onResolve(a.action_id, "approved")}>Approve</button>{" "}<button onClick={() => onResolve(a.action_id, "rejected")}>Reject</button></article>)}</section>;
}
