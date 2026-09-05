"use client"

import { useCallback, useEffect, useState } from "react"
import {
  listActivityLog,
  listClients,
  listPendingActions,
  runScheduledCheck,
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data")
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function handleRunCheck() {
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

  async function handleResolved() {
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

      {error && (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error} — check that the API base URL is configured.
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
            onMilestoneComplete={refresh}
          />
        </div>
        <div className="lg:col-span-2">
          <ApprovalsPanel pending={pending} onResolved={handleResolved} />
        </div>
      </div>

      <div className="mt-6">
        <ActivityLog entries={activity} />
      </div>
    </main>
  )
}
