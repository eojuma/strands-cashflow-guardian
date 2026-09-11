# CashflowGuardian — Devpost Submission

**Track:** Professional Agents · **Event:** AWS "Agents for Humans" Hackathon
**Live demo:** https://strands-cashflow-guardian.vercel.app
**Repo:** https://github.com/eojuma/strands-cashflow-guardian

---

## Inspiration

Freelancers and micro-agencies lose income three ways: unpaid scope creep,
milestones that pass without an invoice, and overdue invoices that feel too
awkward to chase.

- **55% of U.S. B2B invoiced sales are past due.** — Atradius, *Payment Practices Barometer – United States 2025*
- The average U.S. small business is owed about **$17,500** in unpaid invoices. — Intuit QuickBooks, *2025 US Small Business Late Payments Report*

Noticing that a "quick tweak" is unpaid scope, and wording a day-14 reminder
differently from a day-3 one, is real accountant judgment. Doing it consistently
is a tax on the freelancer's attention — exactly the repetitive, judgment-heavy
work an agent should own.

## What it does

CashflowGuardian is an autonomous financial-operations agent for freelancers. It
runs two specialists under one orchestrator:

- **Scope Creep Sentinel** — reads client emails, compares requests against the
  stored Statement of Work, and drafts a change-order invoice the moment a
  "quick tweak" turns out to be unpaid extra work. It explains *why* the request
  fell outside scope (what, how many hours, at what rate).
- **Invoice & Dunning Agent** — proposes an invoice the instant a milestone
  completes, then runs a tone-controlled escalation ladder (Day+3 friendly
  check-in → Day+7 formal notice → Day+14 work-pause warning) on anything that
  goes unpaid.
- **Orchestrator** — routes events to both specialists (Strands
  agents-as-tools) and owns the human-in-the-loop state machine.
- **Command Center dashboard** — Clients, Pending Approvals, and an Activity Log;
  every proposed action is **Approve / Edit / Reject**.

**The non-negotiable rule:** nothing externally visible — no email, no finalized
invoice — is sent until a human approves the exact persisted content. The
approval path never re-invokes the LLM, so what you approve is byte-for-byte what
goes out.

## How it works

- **Trigger:** EventBridge invokes the Orchestrator Lambda every 15 minutes; a
  separate HTTP API Lambda serves the dashboard's REST contract.
- **Orchestration:** the specialists are exposed as Strands tools via
  `Agent.as_tool()` (not `if/else` routing), and the low-level tools
  (`pdf_tool`, `gmail_tool`, `guardrails_config`) are LLM-invoked.
- **Memory:** DynamoDB holds `Clients` (SOW, billing rate, payment history, tone
  log, milestones) and `PendingActions` (proposals + status). The tone log
  prevents the same escalation tier from being sent twice.
- **Determinism where it matters:** tier selection, late-fee math, and tone
  guardrails are pure Python and unit-tested; the LLM adds judgment, the safety
  rails are code.
- **Security:** each Lambda has its own scoped IAM policy — no `dynamodb:*` /
  `bedrock:*` wildcards.
- **Architecture diagram:** [`demo/architecture-diagram.png`](../demo/architecture-diagram.png)
  (source mermaid in [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) §3).

## AWS services used

Amazon Bedrock (Claude), AWS Lambda, API Gateway (HTTP API), Amazon EventBridge,
Amazon DynamoDB, IAM, CloudWatch, and AWS SAM for deployment. Bedrock AgentCore
was evaluated as a stretch goal; the MVP uses Lambda + EventBridge with
already-scoped IAM (see ARCHITECTURE §10).

## Human-in-the-loop

Every action surfaces in **Pending Approvals** with its `agent_reasoning`.
Reject ends the flow with no external side effect; Approve/Edit sends the stored
(or edited) bytes. `agent_reasoning` is a first-class field so anyone can see
*why* the agent flagged something, not just *what* it produced. This is framed as
the product's core stance, not a checkbox.

## What's Next

- GitHub webhook for automatic milestone detection (replacing the manual trigger)
- Direct QuickBooks / Xero integration via MCP
- Multi-currency and cross-border VAT handling
- Live OpenTelemetry tracing streamed to the dashboard

## Try it

- **Live demo:** https://strands-cashflow-guardian.vercel.app
- **Local:** see the README "Getting Started" — Mode A (UI preview, zero setup),
  Mode B (full local backend on DynamoDB Local), or Mode C (deployed API).
- **Tests:** `python -m pytest -q` — 85 tests, no AWS credentials required (moto).

## Demo video

Narration and shot list: [`demo/video_script.md`](../demo/video_script.md).

## Built with

`strands-agents` · Amazon Bedrock · AWS Lambda · API Gateway · EventBridge ·
DynamoDB · AWS SAM · ReportLab · Gmail API · Next.js · React · Tailwind CSS ·
Python

## References

- Atradius, *Payment Practices Barometer – United States 2025* — 55% of U.S. B2B
  invoiced sales are past due. https://www.atradius.com
- Intuit QuickBooks, *2025 US Small Business Late Payments Report* — the average
  U.S. small business is owed about $17,500 in unpaid invoices.
  https://quickbooks.intuit.com
