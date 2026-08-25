"use client";
import { useEffect, useState } from "react";
import { api, Action, Client } from "../lib/api";
import { ClientsPanel } from "./components/ClientsPanel";
import { ApprovalsPanel } from "./components/ApprovalsPanel";
import { ActivityLog } from "./components/ActivityLog";

export default function Dashboard() {
  const [clients, setClients] = useState<Client[]>([]), [actions, setActions] = useState<Action[]>([]), [activity, setActivity] = useState<Action[]>([]), [error, setError] = useState("");
  const load = async () => { try { const [c, a, l] = await Promise.all([api.clients(), api.pending(), api.activity()]); setClients(c); setActions(a); setActivity(l); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Unable to load dashboard"); } };
  useEffect(() => { void load(); }, []);
  const resolve = async (id: string, decision: string) => { await api.resolve(id, decision); await load(); };
  return <main style={{ maxWidth: 1100, margin: "0 auto", padding: 32 }}><h1>CashflowGuardian Command Center</h1><p>Review every proposed client-facing action before it is sent.</p>{error && <p role="alert">{error}</p>}<div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24 }}><ClientsPanel clients={clients} /><ApprovalsPanel actions={actions} onResolve={resolve} /><ActivityLog entries={activity} /></div></main>;
}
