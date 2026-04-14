# Machine Setup

Ansible playbooks for provisioning personal Linux machines.

Ansible gets machines to the point where dotfiles and self-registering
repos can take over. It handles what they can't: packages, users, SSH.

## Machines

| Host | Group | Profile | Purpose |
|---|---|---|---|
| einstein | desktops | default | Ubuntu desktop |
| dirac | desktops | default | Ubuntu laptop (ex-Mac) |
| kaon | pis | server | Raspberry Pi (base setup, then GitOps) |
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
| livepatch | all | Ubuntu Pro + kernel live patching |
| uv | all | Python package manager (pinned version from GitHub releases) |
| claude_code | all | Claude Code CLI (native installer, no Node.js) |
| desktop | desktops | Desktop-specific packages |
| cleanup | desktops | Enable empty-downloads systemd service |
| pi | pis | Docker for GitOps container management |

## Synology

The Synology NAS is in the inventory but has no playbook role. Set up
manually:

```bash
ssh synology
git clone https://github.com/agude/dotfiles.git ~/.dotfiles
~/.dotfiles/install.sh --profile synology
```
