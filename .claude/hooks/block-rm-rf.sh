#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

BLOCKED_PATTERNS=(
  'rm[[:space:]]+(-[a-zA-Z]*[rRfF][a-zA-Z]*[[:space:]]+)+/'
  'rm[[:space:]]+-[a-zA-Z]*[rRfF][a-zA-Z]*[[:space:]]+~'
  'rm[[:space:]]+-[a-zA-Z]*[rRfF][a-zA-Z]*[[:space:]]+\$HOME'
  'rm[[:space:]]+-[a-zA-Z]*[rRfF][a-zA-Z]*[[:space:]]+\.\.?($|/)'
  ':\(\)\{[[:space:]]*:\|:&[[:space:]]*\};:'
  '>[[:space:]]*/dev/sd[a-z]'
  'mkfs\.'
  'dd[[:space:]]+.*of=/dev/'
  'DROP[[:space:]]+(TABLE|DATABASE|SCHEMA)'
  'TRUNCATE[[:space:]]+TABLE'
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qiE "$pattern"; then
    cat >&2 <<EOF
BLOCKED: Destructive command detected.

Command: $COMMAND
Matched pattern: $pattern

Destructive operations against the filesystem or databases are forbidden
in automated sessions. Use 'git rm' or remove specific paths individually.
To drop tables, ask the human operator to run that command manually.
EOF
    exit 2
  fi
done

if echo "$COMMAND" | grep -qE 'rm[[:space:]]+-[a-zA-Z]*[rRfF]'; then
  echo "WARNING: This command uses 'rm -rf'. Verify the path is correct and bounded to the project." >&2
fi

exit 0
