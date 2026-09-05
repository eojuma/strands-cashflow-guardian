"use client"

import type { PendingAction } from "@/lib/api"

const STATUS_STYLES: Record<string, string> = {
  approved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  edited: "bg-brand-50 text-brand-700 ring-brand-200",
  rejected: "bg-red-50 text-red-700 ring-red-200",
  executed: "bg-slate-100 text-slate-600 ring-slate-200",
}

export default function ActivityLog({ entries }: { entries: PendingAction[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold">Activity Log</h2>

      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">
          Nothing resolved yet — approvals and rejections will appear here with
          the agent&apos;s reasoning.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {entries.map((entry) => (
            <li key={entry.action_id} className="flex items-start gap-4 py-3">
              <span
                className={`mt-0.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
                  STATUS_STYLES[entry.status] ?? "bg-slate-100 text-slate-600 ring-slate-200"
                }`}
              >
                {entry.status}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm">
                  <span className="font-medium">{entry.client_name ?? entry.client_id}</span>{" "}
                  <span className="text-slate-500">
                    — {entry.action_type}
                    {entry.escalation_tier ? ` · ${entry.escalation_tier}` : ""}
                  </span>
                </p>
                <p className="mt-0.5 truncate text-xs text-slate-500">
                  {entry.agent_reasoning}
                </p>
              </div>
              {entry.resolved_at && (
                <span className="shrink-0 text-xs text-slate-400">
                  {new Date(entry.resolved_at).toLocaleString()}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
