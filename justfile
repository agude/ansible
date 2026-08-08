set dotenv-load := false

inventory := "inventory.yaml"

default:
    @just --list

sync:
    uv sync

# All read-only static checks. Ansible has no house formatter, so there is
# deliberately no `format` recipe.
lint:
    uv run yamllint -s .
    uv run ansible-lint

# Parse every play without touching a host.
syntax-check:
    uv run ansible-playbook site.yaml --syntax-check -i {{inventory}}

# Everything CI runs. `check` is reserved for the full gate across all repos;
# the playbook parse is `syntax-check`.
check: lint syntax-check

apply host="all" *ARGS="":
    uv run ansible-playbook site.yaml -i {{inventory}} --limit {{host}} {{ARGS}}

diff host="all" *ARGS="":
    uv run ansible-playbook site.yaml -i {{inventory}} --limit {{host}} --check --diff {{ARGS}}

hooks-install:
    @echo "Installing pre-commit hook..."
    @mkdir -p .git/hooks
    @cp bin/pre-commit.sh .git/hooks/pre-commit
    @chmod +x .git/hooks/pre-commit
    @echo "Pre-commit hook installed."
