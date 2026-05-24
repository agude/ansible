#!/bin/bash
#
# Pre-commit hook: runs yamllint and ansible-lint on staged YAML files.
# Rejects the commit if lint fails.

STAGED_YAML_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(ya?ml)$' || true)

if [ -z "$STAGED_YAML_FILES" ]; then
  exit 0
fi

echo "---"
echo "Running ansible-lint on staged YAML files..."
echo "---"

just lint
LINT_EXIT=$?

if [ $LINT_EXIT -ne 0 ]; then
  echo "---"
  echo "❌ Lint failed. Please fix the errors above and try again."
  exit 1
fi

echo "✅ Lint passed."
exit 0
