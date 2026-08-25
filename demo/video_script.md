# CashflowGuardian demo video script

Target runtime: **4:35–4:50**. Keep the final export below 5:00.

## Recording checklist

- Seeded Command Center visible with three clients and two pending approvals.
- Browser zoom and terminal text readable at 1080p.
- Record clean clips separately; assemble them in the order below.
- Keep cursor movement deliberate. Pause briefly after each stamp interaction.
- Do not show real credentials, email addresses, account IDs, or `.env` contents.

## 0:00–0:35 — The problem and audience

**Screen:** Title card, then the Command Center masthead and three columns.

**Narration:**

> Freelancers do not only lose money by charging too little. They lose it when a quick client request becomes unpaid scope, when a completed milestone sits uninvoiced, and when an overdue invoice feels too awkward to chase. More than half of business invoices are paid late. CashflowGuardian is a financial operations agent for freelancers and micro-agencies that notices those moments, prepares the next action, and leaves the final decision with the human.

## 0:35–1:25 — Scope Creep Sentinel

**Screen:** Focus the Aster House client, then the pending change-order card. Hold on the reasoning text and `$225.00` amount.

**Narration:**

> Aster House asked for a dark mode toggle. The Scope Creep Sentinel compares that request with the client's stored Statement of Work in DynamoDB memory. Dark mode is not an agreed deliverable, so the agent estimates three additional hours at seventy-five dollars per hour and drafts a two-hundred-and-twenty-five-dollar change order. The important part is not only the document. The agent explains the judgment directly: what fell outside scope, the estimated effort, and the rate used.

**Action:** Click **Edit**, briefly show the inline draft, then cancel.

> The freelancer can edit the proposed message in place before making any commitment.

## 1:25–2:15 — Invoice and dunning escalation

**Screen:** Focus Marcus Chen's overdue client record and the Day+7 payment notice.

**Narration:**

> Marcus Chen's invoice is eight days overdue. The Invoice and Dunning agent selects the Day plus seven tier, checks the tone log so that tier has not already been sent, calculates the applicable fee, and passes the draft through a professional tone guardrail. Day plus three is a friendly check-in, Day plus seven is formal, and Day plus fourteen can warn that work will pause. The escalation changes with the situation, but aggression is never the goal.

**Action:** Click **Reject** on one seeded action and hold on the rust `DECLINED` stamp.

> If the judgment is wrong or the relationship needs a different approach, Reject ends the flow with no external side effect.

## 2:15–3:05 — Human-in-the-loop control

**Screen:** Click **Approve** on the remaining action. Hold on the green `APPROVED` stamp, then show the Activity Log.

**Narration:**

> This is CashflowGuardian's central human-in-the-loop rule. No email is sent and no invoice is finalized until the user approves or edits the exact persisted content. Approval is not a suggestion to the model. The deterministic execution path re-reads the stored status and sends the approved bytes without asking the LLM to rewrite them. The activity ledger records the outcome and the agent's reasoning for auditability.

## 3:05–3:35 — Milestone to invoice

**Screen:** Click **Mark milestone complete** for Northstar Studio. Show `Generating invoice…`, then the new invoice approval.

**Narration:**

> For invoicing, the freelancer marks a milestone complete. The system visibly generates the invoice and places it in Pending Approvals. It does not teleport directly to a sent document. The user stays in control at the same decision surface.

## 3:35–4:20 — Architecture and technical implementation

**Screen:** Show the architecture diagram, then briefly show the repository structure or selected source files.

**Narration:**

> Under the interface, EventBridge invokes an AWS Lambda orchestrator on a schedule. The orchestrator uses Strands agents-as-tools orchestration to delegate to the Scope Creep Sentinel and the Invoice and Dunning specialist. Those specialists call ReportLab PDF generation, Gmail tools, and deterministic tone guardrails. DynamoDB provides client and pending-action memory. A separate HTTP API connects the Next.js Command Center to the same approval state. The SAM template scopes DynamoDB access to these two tables and Bedrock access to the configured model rather than using wildcard permissions.

## 4:20–4:45 — Close

**Screen:** Return to the Command Center populated view, then show the calm empty Pending Approvals state.

**Narration:**

> CashflowGuardian gives freelancers the consistency of an accounts-receivable function without taking control away from them. It remembers what was agreed, notices when money is at risk, prepares a professional response, and asks the human only when a real decision is ready. It handles the remembering. The freelancer makes the call.

## Required phrase check

- **Memory:** spoken in the Scope Sentinel and architecture sections.
- **Orchestration:** spoken in the architecture section.
- **Human-in-the-loop:** spoken in the approval section.
- Problem, audience, and why it matters: covered in the opening and close.
- Three scenarios: scope creep, late payment, milestone completion.
