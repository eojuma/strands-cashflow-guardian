import { Action } from "../../lib/api";
export function ActivityLog({ entries }: { entries: Action[] }) { return <section><h2>Activity log</h2>{entries.length === 0 ? <p>No activity yet.</p> : entries.map(e => <p key={e.action_id}><strong>{e.status}</strong> — {e.agent_reasoning}</p>)}</section>; }
