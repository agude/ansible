# Machine Setup

Ansible playbooks for provisioning personal Linux machines.

Ansible gets machines to the point where dotfiles and self-registering
repos can take over. It handles what they can't: packages, users, SSH.

## Machines

| Host | Group | Profile | Purpose |
|---|---|---|---|
| desktop | desktops | default | Ubuntu desktop |
| laptop | desktops | default | Ubuntu laptop |
| pi | pis | server | Raspberry Pi (base setup, then GitOps) |
| synology | nas | synology | Synology NAS (dotfiles only, not in playbook) |

## Usage

```bash
# Provision everything
ansible-playbook site.yaml

# Single machine
ansible-playbook site.yaml --limit desktop

# Dry run
ansible-playbook site.yaml --check
```

## Layers

```
Ansible        packages, SSH hardening, apt config, clone repos
    ↓
Dotfiles       shell, vim, git, coat-tree, OS services
    ↓
Knowledge      self-registers hooks + skills via scripts/install
Wiki           self-registers hooks + skills via scripts/install
```

## Roles

| Role | Applied to | Purpose |
|---|---|---|
| common | all | SSH, packages, apt config, dotfiles + Knowledge + Wiki |
| desktop | desktops | Desktop-specific packages |
| pi | pis | Docker for GitOps container management |
