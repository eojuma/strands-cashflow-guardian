# CashflowGuardian — Build Guide (Hackathon Operating Plan)

> This is the "build guide" referenced throughout the GitHub issues and `architecture.md`. It maps the AWS **"Agents for Humans"** hackathon rules (the Devpost page) to concrete deliverables. The system design itself lives in [`architecture.md`](./architecture.md); this document is about *winning the submission*, section by section.
>
> Track: **Professional Agents**. Repo: `eojuma/strands-cashflow-guardian`.

## Table of Contents

- [1. Problem & Audience](#1-problem--audience)
- [2. Solution Summary & Track](#2-solution-summary--track)
- [3. Architecture Diagram](#3-architecture-diagram)
- [4. Tech Stack](#4-tech-stack)
- [5. Build Phases](#5-build-phases)
- [6. Judging Criteria ↔ Build Mapping](#6-judging-criteria--build-mapping)
- [7. Fatal-Flaw Prevention Checklist](#7-fatal-flaw-prevention-checklist)
- [8. Stretch-Goal Priority Order](#8-stretch-goal-priority-order)

---

## 1. Problem & Audience

- **Problem:** Freelancers lose income to three structural, repetitive bottlenecks:
  1. **Uncompensated scope creep** — "quick tweaks" requested over email that add up to unpaid hours because freelancers feel awkward raising a change-order invoice.
  2. **Invoicing friction** — milestones pass without an invoice going out promptly, purely from administrative fatigue.
  3. **Passive payment chasing** — over 50% of B2B invoices are paid past 30 days; freelancers lack the time (and emotional detachment) for multi-stage follow-ups.
- **Audience:** Solo freelancers and micro-agencies who bill hourly or per-milestone, run their client relationships over email, and have no dedicated accounts-receivable function.
- **Why it matters:** noticing scope creep and wording a day-14 reminder differently from a day-3 one is real accountant judgment. Doing it consistently is a tax on the freelancer's attention — exactly the kind of background, judgment-heavy work an agent should own, surfacing only when a real decision is needed.

## 2. Solution Summary & Track

- **Track:** Professional Agents.
- **Three agents:** Orchestrator (owns human-in-the-loop state machine), Scope Creep Sentinel (detects out-of-scope requests), Invoice & Dunning (milestone→invoice + escalation ladder).
- **The non-negotiable differentiator:** nothing externally visible — no email, no finalized invoice — is sent without explicit **Approve / Edit / Reject**. `agent_reasoning` is a first-class field so the dashboard can show *why* the agent flagged something, not just *what* it produced.

## 3. Architecture Diagram

The canonical diagram is the mermaid flowchart in `architecture.md` §3. This is also the source for the submission PNG (`demo/architecture-diagram.png`, Day 21).

It must show, at minimum:

- **Trigger** — EventBridge scheduled rule → Orchestrator.
- **Agents** — Orchestrator delegating (as Strands tools) to Scope Creep Sentinel and Invoice & Dunning.
- **Tools** — `pdf_tool`, `gmail_tool`, `guardrails_config`.
- **Memory** — DynamoDB `Clients` and `PendingActions` tables.
- **UI** — Next.js Command Center dashboard reading/writing both tables over a REST surface.

## 4. Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | Strands Agents SDK (Python) |
| LLM | Amazon Bedrock (Claude Haiku for classification, Claude Sonnet for drafting) |
| Memory | DynamoDB (`Clients`, `PendingActions`) |
| Document generation | ReportLab |
| Email | Gmail API |
| Deployment | AWS Lambda + EventBridge via SAM (`infra/template.yaml`) |
| Frontend | Next.js + Tailwind CSS |
| Tone guardrails | Constrained prompts + `guardrails_config` tone-check tool (optionally Bedrock Guardrails) |

## 5. Build Phases

Four GitHub milestones map one-to-one onto the four phases in `create_issues.sh`:

- **Phase 1: Foundation (Days 1-5)** — Bedrock + Strands hello-world, DynamoDB schema, orchestrator skeleton, PDF tool, Gmail tool.
- **Phase 2: Core Agent Logic (Days 6-13)** — escalation ladder + guardrails, Scope Creep Sentinel, human-in-the-loop state machine, one buffer day.
- **Phase 3: Product Experience (Days 14-18)** — dashboard, Lambda + EventBridge deploy, demo data, full dry run.
- **Phase 4: Demo & Submission (Days 19-23)** — video script/edit, architecture diagram, README/license/builder post, final submission.

## 6. Judging Criteria ↔ Build Mapping

The five criteria from the Devpost page, each mapped to the concrete deliverables that satisfy it and the issue that produces it:

1. **Technological Implementation** — *thorough, skillful use of Strands; non-trivial, working code; live demo / AgentCore strengthens it.*
   - Sub-agents exposed as Strands tools ("agents-as-tools"), not `if/else` routing — Day 3.
   - Low-level tools (`pdf_tool`, `gmail_tool`, `guardrails_config`) LLM-invoked via `@tool` — Day 4, Day 5.
   - Scoped IAM, no `dynamodb:*` / `bedrock:*` wildcards — Day 2, Day 16.
   - Deployed to Lambda + EventBridge, not localhost — Day 16.
   - Live demo link — stretch goal #1 (see §8).
   - (Optional) Bedrock AgentCore deployment — stretch goal #2.

2. **Design** — *complete, coherent product, not just a proof of concept.*
   - Single-page dashboard: Clients / Pending Approvals / Activity Log panels — Day 14-15.
   - Approve/Edit/Reject buttons mutate real backend state — Day 14-15.
   - Sensible empty states ("All caught up") — Day 14-15.

3. **Potential Impact** — *credible, specific case for a real audience, and the solution actually addresses it.*
   - Three seeded personas: on-time payer / late payer / scope-creep requester — Day 17.
   - At least one "agent correctly does nothing" scenario — proves judgment, not just triggers — Day 17.
   - Concrete numbers cited (18% revenue loss, 50%+ late payments).

4. **Creativity & Originality** — *creative, non-obvious use of Strands; genuine understanding of the problem space.*
   - Scope Creep Sentinel whose `agent_reasoning` surfaces the *why* ("~3 hours beyond the two-revision SOW limit"), not just the invoice — Day 8-10.
   - Tone-controlled escalation ladder that never sounds aggressive — Day 6-7.
   - Human-in-the-loop framed as the product's core stance, not a checkbox.

5. **Presentation** — *video demonstrates end-to-end; covers problem/who/why; easy to follow.*
   - 5-minute script: problem+number → Scope Sentinel → dunning escalation → dashboard → architecture/deployment → close — Day 19.
   - Say "memory", "orchestration", and "human-in-the-loop" aloud at least once each — Day 19.
   - Runtime under 5:00 — Day 20.

## 7. Fatal-Flaw Prevention Checklist

Every item below is a hard submission requirement from the Devpost page. None may be missing at the Day 23 final submission.

- [ ] **Text description** — what it does, who it's for, how it works (Devpost form).
- [ ] **Public repo URL** — repo must be public. *(Verified: repo is public.)*
- [ ] **Source code + assets + setup instructions** — a stranger can clone and run from the README alone.
- [ ] **MIT or Apache license visible in the About section** *(Verified: MIT detected.)*
- [ ] **README** — finalized.
- [ ] **Architecture diagram** — submitted and embedded in README.
- [ ] **Demo video ≤ 5:00** — shows the working project end-to-end AND covers problem / who it's for / why it matters.
- [ ] **AWS Builder ID** — provided with the submission.
- [ ] *(Optional, scores higher)* **Live demo link** — a running public URL.
- [ ] *(Bonus)* **builder.aws.com post** — published before deadline, with "Agents for Humans" in the title.

## 8. Stretch-Goal Priority Order

Only pull these forward **after** the Day 18 dry run is clean. Ordered by hackathon ROI (how much each moves the score for the effort):

1. **Live demo link** — a public Lambda Function URL or API Gateway in front of the MVP. Explicitly "scores higher on Technical Implementation"; highest ROI.
2. **Bedrock AgentCore deployment** — the rules call this a "smart architectural choice" that strengthens Technical Implementation; evaluate only if the SAM Lambda path is already stable.
3. **GitHub webhook** for automatic milestone-complete detection (replaces the manual dashboard trigger).
4. **QuickBooks / Xero via MCP** — extends the "money" story to real accounting systems.
5. **Multi-currency / cross-border VAT** — broadens the audience story.
6. **OpenTelemetry streaming** to the dashboard — the Activity Log + `agent_reasoning` already cover transparency; this is polish, not proof.
