#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

BASENAME=$(basename "$FILE_PATH")
BLOCKED=0

case "$BASENAME" in
  .env|.env.*|.envrc)
    BLOCKED=1 ;;
  *.pem|*.key|id_rsa|id_ed25519|*.p12|*.pfx)
    BLOCKED=1 ;;
  credentials|credentials.json|service-account.json|gcloud-key.json)
    BLOCKED=1 ;;
esac

case "$FILE_PATH" in
  */.git/*|*/.ssh/*|*/secrets/*|secrets/*)
    BLOCKED=1 ;;
esac

if [ "$BLOCKED" = "1" ]; then
  cat >&2 <<EOF
BLOCKED: Writes to sensitive file are forbidden by project policy.

Path: $FILE_PATH

To add an env var, update '.env.example' instead and ask the human to
copy the value into '.env' manually. Secret changes must be made by a
human outside Claude Code.
EOF
  exit 2
fi

exit 0
