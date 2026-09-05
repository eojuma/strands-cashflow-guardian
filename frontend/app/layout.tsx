import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "CashflowGuardian — Command Center",
  description:
    "Autonomous AI cash-flow agent for freelancers. Approve, edit, or reject every action before anything reaches a client.",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-100 text-slate-900">
        {children}
      </body>
    </html>
  )
}
