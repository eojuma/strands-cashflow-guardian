#!/usr/bin/env bash
set -euo pipefail

command -v sam >/dev/null 2>&1 || { echo "AWS SAM CLI is required: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"; exit 1; }

sam validate --template-file template.yaml --lint
sam build --template-file template.yaml
sam deploy --guided
