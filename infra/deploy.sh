#!/usr/bin/env bash
#
# One-command deploy wrapper around `sam build` + `sam deploy`.
#
# Prereqs (see README "Getting Started"):
#   - AWS CLI + SAM CLI installed (user-local install is fine)
#   - AWS credentials configured for the target account/region (uses ~/.aws)
#   - Bedrock model access enabled for anthropic.claude-3-5-sonnet-*
#
# Packaging is OFFLINE: scripts/build_lambda_package.py copies the runtime
# dependency closure from the project virtualenv into ../.lambda_build, so no
# container build and no PyPI access are required.
#
# Usage:
#   ./deploy.sh                     # package + deploy
#   SEND_MODE=live ./deploy.sh      # enable real Gmail sends on approval
#   STACK_NAME=my-stack ./deploy.sh # override the stack name
#   SAM=/path/to/sam ./deploy.sh    # use a specific SAM CLI
#
# The default SEND_MODE is "log" (no real email) for safe demos.
set -euo pipefail

cd "$(dirname "$0")"

STACK_NAME="${STACK_NAME:-cashflow-guardian}"
REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || echo us-east-1)}"
REPO_ROOT="$(cd .. && pwd)"

# Use the project virtualenv's Python (it has the runtime deps + `packaging`);
# fall back to python3 if .venv is missing.
PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="python3"

# Resolve the SAM CLI: explicit $SAM, a local venv, then PATH. This avoids the
# "sam: command not found" failure when SAM was installed into infra/venv.
SAM_BIN="${SAM:-}"
if [ -z "$SAM_BIN" ]; then
  for candidate in "$REPO_ROOT/infra/venv/bin/sam" "$REPO_ROOT/venv/bin/sam" "$REPO_ROOT/.venv/bin/sam"; do
    if [ -x "$candidate" ]; then SAM_BIN="$candidate"; break; fi
  done
fi
[ -n "$SAM_BIN" ] || SAM_BIN="$(command -v sam || true)"
if [ -z "$SAM_BIN" ]; then
  echo "SAM CLI not found. Install it, add it to PATH, or pass SAM=/path/to/sam ./deploy.sh" >&2
  exit 1
fi

echo "Deploying CashflowGuardian to ${REGION} (stack: ${STACK_NAME})"

# Stage the backend + runtime dependency closure into ../.lambda_build. The
# script deliberately leaves no requirements.txt so `sam build` only copies.
"$PYTHON" "$REPO_ROOT/scripts/build_lambda_package.py" "$REPO_ROOT/.lambda_build"
# No --use-container: there is nothing for the Python builder to install.
"$SAM_BIN" build \
  --template template.yaml \
  --region "${REGION}"

# sam's Python builder excludes "*.so" from the source it copies (its
# EXCLUDED_FILES list assumes a container will compile extensions). That silently
# strips the prebuilt binary extensions we staged (pydantic_core, reportlab,
# pillow, cryptography, ...), so overlay the staged package back to make the
# artifact match .lambda_build exactly.
for fn_dir in .aws-sam/build/*/; do
  [ -d "$fn_dir" ] && cp -a "$REPO_ROOT/.lambda_build/." "$fn_dir/"
done

EXTRA_ARGS=("$@")

"$SAM_BIN" deploy \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides "SendMode=${SEND_MODE:-log}" \
  ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}

echo
echo "Deploy complete. Endpoints:"
aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text
