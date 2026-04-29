#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

if [ -z "$FILE_PATH" ]; then exit 0; fi

case "$FILE_PATH" in
  *.py) ;;
  *) exit 0 ;;
esac

case "$FILE_PATH" in
  */tests/*|*/test_*|*_test.py) exit 0 ;;
esac

cd "$CLAUDE_PROJECT_DIR"

if ! OUTPUT=$(uv run mypy --follow-imports=silent --no-pretty --no-error-summary "$FILE_PATH" 2>&1); then
  cat >&2 <<EOF
TYPECHECK FAILED on $FILE_PATH

$OUTPUT

Fix the type errors above before continuing. If a type error is genuinely
spurious, add a narrow '# type: ignore[error-code]' comment with a brief
justification — never a bare '# type: ignore'.
EOF
  exit 2
fi

exit 0
