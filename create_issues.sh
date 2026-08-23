#!/usr/bin/env bash
set -e

REPO="eojuma/strands-cashflow-guardian"

echo "Ensuring labels exist (safe to re-run)..."
labels=(
  "phase-1:0E8A16" "phase-2:FBCA04" "phase-3:1D76DB" "phase-4:5319E7"
  "agent-logic:D93F0B" "infra:C5DEF5" "frontend:BFD4F2" "docs:0075CA"
  "orchestrator:5319E7" "scope-sentinel:FF6B6B" "invoice-dunning:FFA07A" "memory:008672"
  "blocker:B60205" "buffer-day:EEEEEE" "stretch-goal:C2E0C6"
  "demo-video:F9D0C4" "submission-blocker:E11D21"
)
for entry in "${labels[@]}"; do
  name="${entry%%:*}"
  color="${entry##*:}"
  gh label create "$name" --color "$color" --repo "$REPO" 2>/dev/null || true
done

echo "Creating issues..."

# ---------- PHASE 1: FOUNDATION ----------

gh issue create --repo "$REPO" \
  --title "Day 1: AWS + Bedrock setup, Strands hello-world agent" \
  --milestone "Phase 1: Foundation" \
  --label "phase-1,infra" \
  --body "## Goal
Get the AWS account, Bedrock model access, and a minimal Strands agent running locally before touching any real logic.

## Tasks
- Confirm AWS account has Bedrock model access enabled for Claude (Haiku + Sonnet)
- Set up Python virtualenv (no sudo): \`python -m venv .venv && source .venv/bin/activate\`
- Install Strands Agents SDK and confirm a trivial agent responds to a hardcoded prompt
- Document AWS credentials setup in README (do NOT commit real keys)

## Files Affected
- \`requirements.txt\` (new — pin strands-agents, boto3 versions)
- \`.env.example\` (new — placeholder AWS_REGION, BEDROCK_MODEL_ID)
- \`agents/orchestrator.py\` (new — bare skeleton, single hardcoded call)
- \`README.md\` (add: local setup steps, Bedrock access request steps)

## Acceptance Criteria
- [ ] \`python agents/orchestrator.py\` runs locally and returns a real Bedrock-generated response
- [ ] No AWS credentials committed anywhere in the repo
- [ ] README setup steps are followable by someone who has never touched this repo"

gh issue create --repo "$REPO" \
  --title "Day 2: Design DynamoDB schema for Strands Memory" \
  --milestone "Phase 1: Foundation" \
  --label "phase-1,memory,infra" \
  --body "## Goal
Define the persistent memory schema before any agent logic depends on it — this is the project's core technical differentiator, so get the shape right early.

## Tasks
- Design DynamoDB table(s): per-client record with SOW terms, billing rate, payment history, tone/escalation log
- Provision tables via SAM template (not manually in console, so it's reproducible)
- Write the Strands Memory <-> DynamoDB adapter

## Files Affected
- \`memory/schema.py\` (new — table + attribute definitions)
- \`memory/dynamo_client.py\` (new — read/write adapter used by all agents)
- \`infra/template.yaml\` (new — DynamoDB resource definition)
- \`infra/iam-policies/lambda-execution-role.json\` (new — DynamoDB read/write permissions)

## Acceptance Criteria
- [ ] Table schema documented with example item (one fake client record)
- [ ] Can write and read a test record from a local script against the deployed table
- [ ] IAM policy scoped to only the actions/tables actually needed (not \`*\`)"

gh issue create --repo "$REPO" \
  --title "Day 3: Orchestrator skeleton + Invoice/Dunning agent stub" \
  --milestone "Phase 1: Foundation" \
  --label "phase-1,orchestrator,invoice-dunning,agent-logic" \
  --body "## Goal
Stand up the multi-agent orchestration shape early, even with fake data, so integration risk is front-loaded rather than discovered on day 15.

## Tasks
- Build Orchestrator agent that can delegate to a sub-agent
- Build Invoice & Dunning agent as a stub — accepts a hardcoded fake milestone-complete event, returns a fake invoice object (no PDF/email yet)
- Confirm delegation actually happens (Orchestrator calls sub-agent as a tool, not just inline function call)

## Files Affected
- \`agents/orchestrator.py\` (extend skeleton with delegation logic)
- \`agents/invoice_dunning.py\` (new — stub agent)
- \`agents/tools/__init__.py\` (new — shared tool registration pattern)

## Acceptance Criteria
- [ ] Orchestrator receives a fake trigger and correctly routes it to Invoice/Dunning agent
- [ ] Delegation uses Strands' native multi-agent pattern (agents-as-tools), not manual if/else routing
- [ ] Output is logged clearly enough to demo 'orchestration' later without extra work"

gh issue create --repo "$REPO" \
  --title "Day 4: Wire PDF generation as a Strands tool" \
  --milestone "Phase 1: Foundation" \
  --label "phase-1,invoice-dunning,agent-logic" \
  --body "## Goal
Replace the fake invoice object from Day 3 with a real generated PDF.

## Tasks
- Implement ReportLab-based invoice generator
- Register it as a Strands \`@tool\` callable by the Invoice/Dunning agent
- Generate one real invoice PDF from fake client data end-to-end

## Files Affected
- \`agents/tools/pdf_tool.py\` (new)
- \`agents/invoice_dunning.py\` (update — call pdf_tool instead of returning fake object)
- \`tests/test_invoice_dunning.py\` (new — basic smoke test)

## Acceptance Criteria
- [ ] Running the agent produces an actual .pdf file with correct client name, amount, due date
- [ ] Tool is invoked by the LLM agent (not called directly by application code) — this matters for 'Technological Implementation' scoring"

gh issue create --repo "$REPO" \
  --title "Day 5: Wire Gmail API as a Strands tool (read + send)" \
  --milestone "Phase 1: Foundation" \
  --label "phase-1,agent-logic,blocker" \
  --body "## Goal
Get real email read/send working — this is the highest-risk integration in Phase 1 (OAuth setup is historically fiddly), so it's flagged as a blocker and should not slip past today.

## Tasks
- Set up Gmail API OAuth credentials (test/sandbox inbox, not personal primary inbox)
- Implement read-scope tool (fetch recent emails) and send-scope tool
- Register both as Strands \`@tool\`s
- Send one real test email triggered by the agent

## Files Affected
- \`agents/tools/gmail_tool.py\` (new)
- \`.env.example\` (add Gmail OAuth client ID/secret placeholders)
- \`README.md\` (document exact OAuth setup steps — future-you will need this before the demo)

## Acceptance Criteria
- [ ] Agent can read a real email from the test inbox
- [ ] Agent can send a real email visible in the test inbox's Sent folder
- [ ] OAuth setup steps documented well enough to redo from scratch in under 15 minutes if credentials expire"

# ---------- PHASE 2: CORE AGENT LOGIC ----------

gh issue create --repo "$REPO" \
  --title "Days 6-7: Build escalation ladder with Bedrock Guardrails" \
  --milestone "Phase 2: Core Agent Logic" \
  --label "phase-2,invoice-dunning,agent-logic" \
  --body "## Goal
Implement the Day+3 / Day+7 / Day+14 dunning escalation logic with tone constraints, so the agent never sounds unprofessional or aggressive.

## Tasks
- Implement due-date tracking and escalation state transitions
- Day+3: friendly check-in email
- Day+7: formal overdue notice with auto-calculated late fee
- Day+14: work-pause warning — requires explicit human approval before sending (do not auto-send)
- Apply Bedrock Guardrails (or strict system-prompt constraint) so tone stays professional at every stage
- Test against 3 synthetic client scenarios: pays on time, pays late, never pays

## Files Affected
- \`agents/invoice_dunning.py\` (add escalation state machine)
- \`agents/tools/guardrails_config.py\` (new — tone policy definition)
- \`tests/test_invoice_dunning.py\` (extend — 3 scenario tests)

## Acceptance Criteria
- [ ] All 3 synthetic scenarios produce correct, distinct agent behavior
- [ ] Day+14 email is NEVER auto-sent without a human approval step
- [ ] A test where the agent tries an aggressive tone is caught and rewritten by guardrails"

gh issue create --repo "$REPO" \
  --title "Days 8-10: Build Scope Creep Sentinel agent" \
  --milestone "Phase 2: Core Agent Logic" \
  --label "phase-2,scope-sentinel,agent-logic" \
  --body "## Goal
This is the project's creativity centerpiece — give it real, undistracted build time, not leftover hours.

## Tasks
- Parse inbound client emails for new/changed requests
- Compare parsed request against SOW terms stored in memory
- When a request is out-of-scope, calculate estimated extra billable hours
- Draft a change-order invoice (reuse pdf_tool from Day 4)
- Ensure the agent explains its reasoning (why this was flagged as out-of-scope), not just the output — this needs to be visible for the demo later

## Files Affected
- \`agents/scope_sentinel.py\` (new)
- \`memory/schema.py\` (extend — ensure SOW terms are queryable per client)
- \`tests/test_scope_sentinel.py\` (new)

## Acceptance Criteria
- [ ] A test 'quick tweak' email correctly triggers a change-order draft
- [ ] A test email that IS within original scope correctly triggers no action
- [ ] Agent's reasoning trace is logged in a human-readable way (not just final output)"

gh issue create --repo "$REPO" \
  --title "Days 11-12: Orchestrator human-in-the-loop state machine" \
  --milestone "Phase 2: Core Agent Logic" \
  --label "phase-2,orchestrator,agent-logic" \
  --body "## Goal
Tie both sub-agents together under the Orchestrator with a proper approve/edit/reject pause point before any externally-visible action.

## Tasks
- Define pending-action state (proposed action + status: pending/approved/edited/rejected)
- Persist pending actions in DynamoDB so the dashboard (Phase 3) can read/write them
- Ensure Orchestrator pauses execution at every external-facing action (send email, generate invoice) until approval status changes

## Files Affected
- \`agents/orchestrator.py\` (add state machine logic)
- \`memory/dynamo_client.py\` (add pending-action read/write methods)
- \`tests/test_orchestrator.py\` (new)

## Acceptance Criteria
- [ ] No email or invoice is sent/finalized without a corresponding 'approved' state
- [ ] Rejecting an action correctly halts it with no side effects
- [ ] Editing a drafted action before approval actually changes what gets sent"

gh issue create --repo "$REPO" \
  --title "Day 13: Buffer day — absorb Phase 2 slippage" \
  --milestone "Phase 2: Core Agent Logic" \
  --label "phase-2,buffer-day" \
  --body "## Goal
Deliberate slack day. Do not start Phase 3 work here even if ahead of schedule — use this to harden whatever in Days 6-12 is shakiest.

## Tasks
- Re-run all Phase 2 tests together, not just individually
- Fix any integration gaps between Scope Sentinel, Invoice/Dunning, and Orchestrator
- If genuinely ahead of schedule, use remaining time to write docstrings/comments — do not start Phase 3

## Files Affected
- Whichever files from Days 6-12 need fixes (\`agents/*.py\`, \`tests/*.py\`)

## Acceptance Criteria
- [ ] All Phase 2 tests pass together in one run, not just in isolation
- [ ] No unresolved TODOs left in agent files before moving to Phase 3"

# ---------- PHASE 3: PRODUCT EXPERIENCE ----------

gh issue create --repo "$REPO" \
  --title "Days 14-15: Build Command Center dashboard" \
  --milestone "Phase 3: Product Experience" \
  --label "phase-3,frontend" \
  --body "## Goal
Build the single-page dashboard that makes this look like a product, not a script — Clients panel, Pending Approvals panel, Activity/Reasoning Log panel.

## Tasks
- Clients panel: list of clients with SOW summary and payment status
- Pending Approvals panel: queue of agent-proposed actions with Approve/Edit/Reject buttons
- Activity Log panel: human-readable reasoning trace ('Agent flagged X because Y')
- Wire panels to read/write against the pending-action state from Days 11-12

## Files Affected
- \`frontend/app/page.tsx\` (new)
- \`frontend/app/components/ClientsPanel.tsx\` (new)
- \`frontend/app/components/ApprovalsPanel.tsx\` (new)
- \`frontend/app/components/ActivityLog.tsx\` (new)

## Acceptance Criteria
- [ ] Approve/Edit/Reject buttons actually change backend state (not just UI-only)
- [ ] Reasoning log is understandable to someone who has never seen the codebase
- [ ] No panel requires reading code to understand what it's showing"

gh issue create --repo "$REPO" \
  --title "Day 16: Deploy to Lambda + EventBridge" \
  --milestone "Phase 3: Product Experience" \
  --label "phase-3,infra,submission-blocker" \
  --body "## Goal
Move off localhost. This directly strengthens the Technical Implementation score per hackathon rules (AgentCore/Lambda deployment explicitly called out).

## Tasks
- Package each agent as a Lambda handler
- Set up EventBridge scheduled trigger (e.g. every 15 min poll for due-date checks)
- Confirm full end-to-end flow works in deployed environment, not just locally

## Files Affected
- \`infra/template.yaml\` (extend — Lambda functions, EventBridge rule)
- \`infra/deploy.sh\` (new — one-command deploy script)
- \`lambda_handlers/orchestrator_handler.py\` (new)
- \`lambda_handlers/scope_sentinel_handler.py\` (new)
- \`lambda_handlers/invoice_dunning_handler.py\` (new)

## Acceptance Criteria
- [ ] Full flow (trigger -> agent reasoning -> pending action -> dashboard) works with agents running in Lambda, not local Python
- [ ] Redeploying from scratch via \`deploy.sh\` works without manual console steps"

gh issue create --repo "$REPO" \
  --title "Day 17: Seed realistic demo data" \
  --milestone "Phase 3: Product Experience" \
  --label "phase-3,docs" \
  --body "## Goal
Create 3-5 synthetic client relationships that make the demo video convincing and varied.

## Tasks
- One client who pays on time (proves the agent correctly does nothing)
- One client who pays late (triggers full escalation ladder)
- One client who requests scope creep (triggers Scope Sentinel)
- Seed all data into DynamoDB via script, not manual console entry

## Files Affected
- \`scripts/seed_demo_data.py\` (new)

## Acceptance Criteria
- [ ] Running the script once produces a clean, reproducible demo state
- [ ] Includes at least one 'agent correctly does nothing' scenario — this matters for judging (proves judgment, not just triggers)"

gh issue create --repo "$REPO" \
  --title "Day 18: Full end-to-end dry run" \
  --milestone "Phase 3: Product Experience" \
  --label "phase-3,blocker" \
  --body "## Goal
Run the entire system start to finish exactly as it will be demoed, and fix whatever breaks — before Phase 4 burns time on video editing around a broken feature.

## Tasks
- Run through all 3 seeded client scenarios end-to-end in the deployed environment
- Confirm dashboard reflects real state changes live
- Fix any breakage found

## Files Affected
- Any files across \`agents/\`, \`lambda_handlers/\`, \`frontend/\` needing fixes

## Acceptance Criteria
- [ ] All 3 demo scenarios run cleanly without manual intervention beyond the intended approve/reject clicks
- [ ] No console errors or silent failures during the dry run"

# ---------- PHASE 4: DEMO & SUBMISSION ----------

gh issue create --repo "$REPO" \
  --title "Day 19: Write demo video script + record raw footage" \
  --milestone "Phase 4: Demo & Submission" \
  --label "phase-4,demo-video" \
  --body "## Goal
Script the 5-minute demo to hit every judging criterion explicitly (see build guide Section 6).

## Tasks
- Finalize script: problem+number -> Scope Sentinel -> dunning escalation -> dashboard -> architecture/deployment -> close
- Record raw screen footage for each scenario from the seeded demo data

## Files Affected
- \`demo/video_script.md\` (new)

## Acceptance Criteria
- [ ] Script explicitly names 'memory', 'orchestration', and 'human-in-the-loop' out loud at least once each
- [ ] Raw footage covers all 3 demo scenarios without needing a retake"

gh issue create --repo "$REPO" \
  --title "Day 20: Edit and finalize demo video" \
  --milestone "Phase 4: Demo & Submission" \
  --label "phase-4,demo-video,submission-blocker" \
  --body "## Goal
Produce the final submittable video, under the 5-minute hard limit.

## Tasks
- Edit raw footage per script
- Add voiceover or captions
- Confirm runtime is under 5:00

## Files Affected
- N/A (video file hosted externally per submission requirements, not committed to repo)

## Acceptance Criteria
- [ ] Final video is under 5 minutes
- [ ] Covers problem, audience, and why-it-matters explicitly per hackathon submission rules"

gh issue create --repo "$REPO" \
  --title "Day 21: Create architecture diagram" \
  --milestone "Phase 4: Demo & Submission" \
  --label "phase-4,docs,submission-blocker" \
  --body "## Goal
Produce the required architecture diagram, based on the build guide's Section 3 diagram.

## Tasks
- Clean, presentable version of the multi-agent + memory + tools architecture
- Embed in README

## Files Affected
- \`demo/architecture-diagram.png\` (new)
- \`README.md\` (embed diagram)

## Acceptance Criteria
- [ ] Diagram clearly shows Orchestrator, both sub-agents, memory layer, and tools
- [ ] Understandable without reading the code"

gh issue create --repo "$REPO" \
  --title "Day 22: Finalize README, license, and builder.aws.com post" \
  --milestone "Phase 4: Demo & Submission" \
  --label "phase-4,docs,submission-blocker" \
  --body "## Goal
Meet every explicit submission requirement in the hackathon rules — this issue exists specifically to prevent last-day scrambling on non-code requirements.

## Tasks
- Write full README: what it does, setup instructions, architecture summary
- Confirm LICENSE file (MIT or Apache) is visible in the About section on GitHub
- Write and publish builder.aws.com post with 'Agents for Humans' in the title (bonus points)

## Files Affected
- \`README.md\` (finalize)
- \`LICENSE\` (new — confirm MIT or Apache)

## Acceptance Criteria
- [ ] A stranger could clone the repo and run it using only the README
- [ ] License is visible in GitHub's repo sidebar, not just as a file
- [ ] builder.aws.com post is live and public before the deadline"

gh issue create --repo "$REPO" \
  --title "Day 23: Final submission" \
  --milestone "Phase 4: Demo & Submission" \
  --label "phase-4,submission-blocker,buffer-day" \
  --body "## Goal
Submit on Devpost with buffer time for upload issues — do not submit exactly at the deadline.

## Tasks
- Verify all submission requirements are met: repo URL, license, README, architecture diagram, demo video, AWS Builder ID
- Submit via Devpost
- Confirm submission is visible/correct after submitting

## Files Affected
- N/A

## Acceptance Criteria
- [ ] All items in the Fatal-Flaw Prevention Checklist (build guide Section 7) are checked off
- [ ] Submission confirmed visible on Devpost, not just 'submitted' with no confirmation"

echo "All issues created. Run 'gh issue list --repo $REPO' to verify."
