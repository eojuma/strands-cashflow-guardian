"use client"

import { useState } from "react"
import { resolveAction, type PendingAction } from "@/lib/api"

const TYPE_LABELS: Record<string, string> = {
  invoice: "Invoice",
  change_order: "Change order",
  dunning_email: "Dunning email",
}

const TYPE_STYLES: Record<string, string> = {
  invoice: "bg-brand-50 text-brand-700 ring-brand-200",
  change_order: "bg-amber-50 text-amber-800 ring-amber-200",
  dunning_email: "bg-violet-50 text-violet-700 ring-violet-200",
}

function tierLabel(tier?: string | null): string {
  if (!tier) return ""
  const map: Record<string, string> = {
    day_3: "Day 3 · friendly check-in",
    day_7: "Day 7 · overdue notice",
    day_14: "Day 14 · final notice",
  }
  return map[tier] ?? tier
}

export default function ApprovalsPanel({
  pending,
  onResolved,
}: {
  pending: PendingAction[]
  onResolved: () => void
}) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  async function act(
    action: PendingAction,
    decision: "approved" | "edited" | "rejected",
  ) {
    setError(null)
    setBusy(action.action_id)
    try {
      const content =
        decision === "edited"
          ? editText || action.drafted_content
          : undefined
      await resolveAction(action.action_id, decision, content)
      setEditingId(null)
      onResolved()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resolve action")
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Pending Approvals</h2>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
          {pending.length}
        </span>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {pending.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center">
          <p className="font-medium text-slate-600">All caught up</p>
          <p className="mt-1 text-sm text-slate-500">
            No actions are waiting on your approval.
          </p>
        </div>
      ) : (
        <ul className="space-y-4">
          {pending.map((action) => (
            <li
              key={action.action_id}
              className="rounded-lg border border-slate-200 p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${
                    TYPE_STYLES[action.action_type] ?? "bg-slate-100 text-slate-600 ring-slate-200"
                  }`}
                >
                  {TYPE_LABELS[action.action_type] ?? action.action_type}
                </span>
                {action.escalation_tier && (
                  <span className="text-xs font-medium text-slate-500">
                    {tierLabel(action.escalation_tier)}
                  </span>
                )}
                <span className="ml-auto text-sm font-medium">
                  {action.client_name ?? action.client_id}
                </span>
              </div>

              <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900">
                <span className="font-semibold">Why: </span>
                {action.agent_reasoning}
              </p>

              {editingId === action.action_id ? (
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  rows={4}
                  className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
                />
              ) : (
                action.action_type === "dunning_email" && (
                  <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700">
                    {action.drafted_content}
                  </pre>
                )
              )}

              <div className="mt-3 flex gap-2">
                <button
                  disabled={busy !== null}
                  onClick={() => act(action, "approved")}
                  className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
                >
                  Approve
                </button>
                {editingId === action.action_id ? (
                  <button
                    disabled={busy !== null}
                    onClick={() => act(action, "edited")}
                    className="rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    Send edited
                  </button>
                ) : (
                  <button
                    disabled={busy !== null}
                    onClick={() => {
                      setEditingId(action.action_id)
                      setEditText(action.drafted_content)
                    }}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                  >
                    Edit
                  </button>
                )}
                <button
                  disabled={busy !== null}
                  onClick={() => act(action, "rejected")}
                  className="ml-auto rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-60"
                >
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
