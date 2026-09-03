#!/usr/bin/env bash
#
# One-command deploy wrapper around `sam deploy`.
#
# Prereqs (see README "Getting Started"):
#   - AWS CLI + SAM CLI installed (user-local install is fine)
#   - AWS credentials configured for the target account/region
#   - Bedrock model access enabled for anthropic.claude-3-5-sonnet-*
#
# Usage:
#   ./deploy.sh                 # guided first deploy (asks for stack name etc.)
#   ./deploy.sh --no-confirm    # re-deploy with saved settings (samconfig.toml)
#
# The default SEND_MODE is "log" (no real email) for safe demos. To enable real
# Gmail sends after a human approves, pass:
#   ./deploy.sh --parameter-overrides SendMode=live
set -euo pipefail

cd "$(dirname "$0")"

STACK_NAME="${STACK_NAME:-cashflow-guardian}"
REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || echo us-east-1)}"

echo "Deploying CashflowGuardian to ${REGION} (stack: ${STACK_NAME})"

sam build \
  --template template.yaml \
  --region "${REGION}"

EXTRA_ARGS=("$@")

sam deploy \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides "SendMode=${SEND_MODE:-log}" \
  "${EXTRA_ARGS[@]}"

echo
echo "Deploy complete. Endpoints:"
aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text
