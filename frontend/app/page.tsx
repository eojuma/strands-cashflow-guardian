"use client"

import { useCallback, useEffect, useState } from "react"
import {
  listActivityLog,
  listClients,
  listPendingActions,
  resolveAction,
  runScheduledCheck,
  seededDesk,
  type Client,
  type PendingAction,
  type ScheduledCheckSummary,
} from "@/lib/api"
import ClientsPanel from "@/app/components/ClientsPanel"
import ApprovalsPanel from "@/app/components/ApprovalsPanel"
import ActivityLog from "@/app/components/ActivityLog"

export default function Dashboard() {
  const [clients, setClients] = useState<Client[]>([])
  const [pending, setPending] = useState<PendingAction[]>([])
  const [activity, setActivity] = useState<PendingAction[]>([])
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const [offline, setOffline] = useState(false)

  const showSeededDesk = useCallback(() => {
    setOffline(true)
    setClients(seededDesk.clients)
    setPending(seededDesk.pending)
    setActivity(seededDesk.activity)
  }, [])

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [c, p, a] = await Promise.all([
        listClients(),
        listPendingActions(),
        listActivityLog(),
      ])
      setClients(c)
      setPending(p)
      setActivity(a)
      setOffline(false)
    } catch (err) {
      // No reachable API: fall back to the static seeded review desk so the
      // dashboard still demos well with zero infrastructure.
      showSeededDesk()
      setError(err instanceof Error ? err.message : "Failed to load data")
    }
  }, [showSeededDesk])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function handleRunCheck() {
    if (offline) {
      setNotice(
        "Seeded desk is a static snapshot — connect the live API to run a real scheduled check.",
      )
      return
    }
    setChecking(true)
    setError(null)
    try {
      const summary: ScheduledCheckSummary = await runScheduledCheck()
      setNotice(
        summary.proposals_persisted === 0
          ? "Scheduled check ran — all caught up."
          : `Scheduled check ran — ${summary.proposals_persisted} new proposal(s): ${Object.entries(
              summary.by_type,
            )
              .map(([k, v]) => `${v} ${k}`)
              .join(", ")}.`,
      )
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scheduled check failed")
    } finally {
      setChecking(false)
    }
  }

  async function handleResolve(
    action: PendingAction,
    decision: "approved" | "edited" | "rejected",
    editedContent?: string,
  ) {
    if (offline) {
      const updated: PendingAction = {
        ...action,
        status: decision === "rejected" ? "rejected" : "executed",
        drafted_content: editedContent || action.drafted_content,
        resolved_at: new Date().toISOString(),
      }
      setPending((current) =>
        current.filter((item) => item.action_id !== action.action_id),
      )
      setActivity((current) => [updated, ...current])
      setNotice(
        decision === "rejected"
          ? "Rejected — nothing was sent (seeded desk, local only)."
          : "Approved in the seeded desk — connect the live API to send for real.",
      )
      return
    }
    await resolveAction(action.action_id, decision, editedContent)
    await refresh()
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            CashflowGuardian Command Center
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Nothing is sent until you approve it. Every action here is a
            proposal.
          </p>
        </div>
        <button
          onClick={handleRunCheck}
          disabled={checking}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {checking ? "Checking…" : "Run scheduled check"}
        </button>
      </header>

      {offline && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span>
            Live API unavailable — showing the <strong>seeded review desk</strong>.
            Approvals here are local to this browser and are not persisted or
            sent.
          </span>
          <button
            onClick={refresh}
            className="rounded-md border border-amber-300 bg-white px-3 py-1 text-xs font-medium text-amber-800 hover:bg-amber-100"
          >
            Try live data
          </button>
        </div>
      )}
      {error && (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-6 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {notice}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <ClientsPanel
            clients={clients}
            offline={offline}
            onMilestoneComplete={refresh}
          />
        </div>
        <div className="lg:col-span-2">
          <ApprovalsPanel
            pending={pending}
            offline={offline}
            onResolve={handleResolve}
          />
        </div>
      </div>

      <div className="mt-6">
        <ActivityLog entries={activity} />
      </div>
    </main>
  )
}
