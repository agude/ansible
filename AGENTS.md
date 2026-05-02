# AGENTS.md

This file provides guidance to AI coding agents. CLAUDE.md and Gemini.md are symlinks to this file.

## Commands

```bash
just sync              # Install Python deps via uv
just lint              # yamllint + ansible-lint
just check             # Syntax check playbook
just apply <host>      # Run playbook (host: einstein, dirac, kaon, synology, or "all")
just diff <host>       # Dry run with diff output
```

Run `ansible-galaxy collection install -r requirements.yml` before first use.

## Architecture

Ansible provisions personal Linux machines to the point where dotfiles and self-registering repos take over.

**Inventory groups**: desktops (einstein, dirac), pis (kaon), nas (synology)

**Playbook structure** (`site.yaml`):
- Play 1: `all:!nas` → common, livepatch, uv, claude_code
- Play 2: `desktops` → desktop, cleanup
- Play 3: `pis` → pi
- Play 4: `nas` → synology (with Python interpreter detection)

**Variable precedence**: `group_vars/all.yaml` → `group_vars/<group>.yaml` → inventory host vars

**SSH key pattern**: `pubkeys/` contains cross-machine public keys named `<source>_to_<target>.pub`. The common role's `ssh-authorize.yaml` task distributes these.

## Vault

Secrets are encrypted with ansible-vault. The vault password file `.vault_pass.txt` is gitignored but required for linting (CI injects it from secrets).

## Role conventions

- Tasks split into logical files imported by `tasks/main.yaml`
- Use `become: true` for privilege escalation
- Use `no_log: true` for tasks handling secrets
- Use FQCN for all modules (e.g., `ansible.builtin.apt`, not `apt`)
