set dotenv-load := false

inventory := "inventory.yaml"

default:
    @just --list

sync:
    uv sync

lint:
    uv run yamllint -s .
    uv run ansible-lint

check:
    uv run ansible-playbook site.yaml --syntax-check -i {{inventory}}

apply host="all" *ARGS="":
    uv run ansible-playbook site.yaml -i {{inventory}} --limit {{host}} {{ARGS}}

diff host="all" *ARGS="":
    uv run ansible-playbook site.yaml -i {{inventory}} --limit {{host}} --check --diff {{ARGS}}
