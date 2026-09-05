# CashflowGuardian

**An autonomous AI financial operations agent for freelancers, built on the AWS Strands Agents SDK.**

Built for the [AWS "Agents for Humans" Hackathon](https://agentsforhumans.devpost.com/) — Professional Agents Track.

> Freelancers lose income two ways: unbilled scope creep, and invoices that sit unpaid — over 50% of B2B invoices are paid past 30 days. CashflowGuardian catches both, autonomously, and only asks a human to weigh in when a real decision needs making.

---

## What It Does

CashflowGuardian runs two specialist agents under one orchestrator:

- **Scope Creep Sentinel** — reads client emails, compares requests against the stored Statement of Work, and drafts a change-order invoice the moment a "quick tweak" turns out to be unpaid extra work.
- **Invoice & Dunning Agent** — generates an invoice the instant a milestone completes, then runs a tone-controlled escalation ladder (Day+3 → Day+7 → Day+14) on anything that goes unpaid.

Every externally-visible action — every email sent, every invoice finalized — pauses for explicit human approval first. Nothing is autonomous in the sense of "unsupervised." It's autonomous in the sense of "you don't have to remember to do it."

Full system design: see [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md). Hackathon operating plan (judging criteria, fatal-flaw checklist, stretch goals): [`docs/BUILD_GUIDE.md`](./docs/BUILD_GUIDE.md).

---

## Why This Matters

A freelancer's real accountant would notice a request creeping outside scope, and would know exactly how firmly to word a payment reminder on day 14 versus day 3. CashflowGuardian is built to make that same judgment call, consistently, without the freelancer having to be the one to bring it up.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | [Strands Agents SDK](https://github.com/strands-agents) (Python) |
| LLM | Amazon Bedrock (Claude Haiku for classification, Claude Sonnet for drafting) |
| Memory | Strands Memory backed by DynamoDB |
| Document generation | ReportLab |
| Email | Gmail API |
| Deployment | AWS Lambda + EventBridge, defined via SAM (`infra/template.yaml`) |
| Frontend | Next.js + Tailwind CSS |
| Tone guardrails | Constrained system prompts + a `guardrails_config` tone-check tool (optionally backed by Amazon Bedrock Guardrails) |

---

## Project Structure

```
strands-cashflow-guardian/
├── docs/                # Architecture reference + build guide
├── agents/              # Orchestrator + specialist agents + tools
├── memory/              # DynamoDB schema and Strands Memory adapter
├── lambda_handlers/     # Lambda entry points: scheduled check + dashboard REST API
├── infra/               # SAM template, deploy script, IAM policies
├── frontend/            # Next.js Command Center dashboard
├── scripts/             # Demo-data seeding + local API server
├── tests/               # Unit tests per agent + handler tests
└── demo/                # Video script and architecture diagram assets
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ (for the frontend)
- An AWS account with Bedrock model access enabled for Claude
- AWS CLI and SAM CLI (user-local install is fine — no root required)
- A Gmail account for sandboxed testing (not your primary inbox)

### 1. Clone and set up the environment

```bash
git clone https://github.com/eojuma/strands-cashflow-guardian.git
cd strands-cashflow-guardian
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with your AWS region, Bedrock model ID, and Gmail OAuth credentials. Never commit `.env`.

### 2. Request Bedrock model access

In the AWS Console, go to Bedrock → Model access, and request access to the Claude models used in this project. This can take a few minutes to be approved.

### 3. Set up Gmail API credentials

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the Gmail API.
3. Create OAuth client credentials (Desktop app type).
4. Download the credentials JSON and reference its path in `.env`.
5. Run the local auth flow once to generate a token (see `agents/tools/gmail_tool.py` for the first-run script).

> For demos and dry runs you can skip Gmail entirely: set `CASHFLOW_SEND_MODE=log`
> in `.env` and approved sends are logged instead of emailed.

### 4a. Local dry run (no AWS compute needed)

```bash
python scripts/seed_demo_data.py     # personas into DynamoDB (or DynamoDB Local)
python scripts/serve_api.py          # REST API on http://localhost:8000
```

Then in a second terminal:

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev                          # dashboard on http://localhost:3000
```

The dashboard proxies `/api/*` to `localhost:8000` in dev. Use **Run scheduled
check** to trigger a pass instantly (the deployed EventBridge rule does this
automatically every 15 minutes), then **Approve / Edit / Reject** actions.

### 4b. Deploy infrastructure

```bash
cd infra
./deploy.sh                          # `sam deploy`; see script for options
```

This provisions DynamoDB tables, the scheduled Orchestrator Lambda (EventBridge),
and the dashboard REST API via AWS SAM. It does **not** deploy the frontend —
host it on Vercel or Amplify and point `NEXT_PUBLIC_API_BASE_URL` at the printed
API endpoint.

### 5. Run the frontend (against a deployed API)

```bash
cd frontend
# set NEXT_PUBLIC_API_BASE_URL to the API endpoint printed by deploy.sh
npm install
npm run dev                          # or: npm run build && npm start
```

Open `http://localhost:3000` to view the Command Center dashboard.

---

## Running Tests

```bash
pytest tests/
```

---

## Human-in-the-Loop Design

No agent in this system sends an email, finalizes an invoice, or takes any other externally-visible action without first appearing in the dashboard's **Pending Approvals** panel for a human to **Approve**, **Edit**, or **Reject**. This is a hard architectural constraint, not a configurable setting — see `docs/ARCHITECTURE.md` §7 for how the state machine enforces it.

---

## What's Next

- GitHub webhook integration for automatic milestone detection (replacing the manual trigger)
- Direct QuickBooks / Xero integration via MCP
- Multi-currency and cross-border VAT handling
- Live OpenTelemetry tracing streamed to the dashboard

---

## License

Licensed under the MIT License. See [`LICENSE`](./LICENSE) for details.

---

## Hackathon Submission

- **Track:** Professional Agents
- **Event:** AWS "Agents for Humans" Hackathon
- Architecture diagram: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- Demo video: _link added at submission_