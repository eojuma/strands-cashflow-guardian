"use client"

import { useState } from "react"
import { markMilestoneComplete, type Client } from "@/lib/api"

function currency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value)
}

export default function ClientsPanel({
  clients,
  offline,
  onMilestoneComplete,
}: {
  clients: Client[]
  offline: boolean
  onMilestoneComplete: () => void
}) {
  const [open, setOpen] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [amount, setAmount] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (clients.length === 0) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Clients</h2>
        <p className="text-sm text-slate-500">
          No clients yet. Seed demo data to see personas here.
        </p>
      </section>
    )
  }

  async function submit(clientId: string) {
    setError(null)
    setSubmitting(true)
    try {
      await markMilestoneComplete(clientId, name, Number(amount))
      setOpen(null)
      setName("")
      setAmount("")
      onMilestoneComplete()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record milestone")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold">Clients</h2>
      <ul className="divide-y divide-slate-100">
        {clients.map((client) => (
          <li key={client.client_id} className="py-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium">{client.name}</p>
                  {client.uninvoiced_milestones > 0 && (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                      {client.uninvoiced_milestones} to invoice
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500">{client.email}</p>
              </div>
              <div className="text-right">
                <p className="font-semibold">
                  {currency(client.outstanding_balance)}
                </p>
                <p className="text-xs text-slate-500">
                  {client.open_invoices} open invoice
                  {client.open_invoices === 1 ? "" : "s"}
                </p>
              </div>
            </div>
            <div className="mt-2 flex justify-end">
              {!offline && (
                <button
                  onClick={() => setOpen(open === client.client_id ? null : client.client_id)}
                  className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  Mark milestone complete
                </button>
              )}
            </div>
            {open === client.client_id && (
              <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-3">
                <div className="flex gap-2">
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Milestone name (e.g. MVP launch)"
                    className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
                  />
                  <input
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="Amount"
                    type="number"
                    min="0"
                    step="0.01"
                    className="w-28 rounded-md border border-slate-300 px-2 py-1 text-sm"
                  />
                </div>
                {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
                <button
                  disabled={submitting || !name || !amount}
                  onClick={() => submit(client.client_id)}
                  className="mt-2 rounded-md bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Recording…" : "Record & propose invoice"}
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {offline && (
        <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-400">
          Seeded desk — connect the live API to record milestones and propose
          invoices.
        </p>
      )}
    </section>
  )
}
