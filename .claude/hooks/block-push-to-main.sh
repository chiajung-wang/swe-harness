#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if ! echo "$COMMAND" | grep -qE '^[[:space:]]*git[[:space:]]+push'; then
  exit 0
fi

PROTECTED='(^|[[:space:]])(origin[[:space:]]+)?(main|master)([[:space:]]|$)'
HEAD_PUSH='git[[:space:]]+push[[:space:]]+(--force[[:space:]]+|-f[[:space:]]+)?(origin[[:space:]]+)?HEAD'

if echo "$COMMAND" | grep -qE "$PROTECTED" \
   || echo "$COMMAND" | grep -qE "$HEAD_PUSH"; then
  cat >&2 <<EOF
BLOCKED: Direct push to main/master is forbidden by project policy.

Workflow:
  1. git checkout -b feature/<short-name>
  2. Make commits on the feature branch
  3. git push origin feature/<short-name>
  4. Open a PR for review

If this push is genuinely intentional, the human operator must run it
manually outside Claude Code.
EOF
  exit 2
fi

exit 0
