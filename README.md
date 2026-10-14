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

## LLM tools

LLM tools are controlled by the enable flags in `group_vars/all.yaml`:

```yaml
claude_code_enabled: true
codex_enabled: true
opencode_enabled: false
ollama_enabled: true
```

Override these variables in a group or host vars file to select a different
set of tools for specific machines. Ollama remains limited to `einstein`.

## Roles

| Role | Applied to | Purpose |
|---|---|---|
| common | all | SSH, packages, apt config, dotfiles + Knowledge + Wiki |
| livepatch | all | Ubuntu Pro + kernel live patching |
| uv | all | Python package manager (pinned version from GitHub releases) |
| claude_code | all, when enabled | Claude Code CLI (native installer, no Node.js) |
| codex | all, when enabled | OpenAI Codex CLI |
| opencode | all, when enabled | OpenCode coding agent (native installer) |
| ollama | einstein, when enabled | Local LLM inference service and models |
| desktop | desktops | Desktop-specific packages |
| cleanup | desktops | Enable empty-downloads systemd service |
| pi | pis | Docker for GitOps container management |
| tailscale | pis; desktops, when enabled | Tailscale subnet router and exit node (pis) or client (desktops) |

## NAS client mounts

Einstein and Dirac use the same five CIFS shares and mount policy, defined
in `group_vars/desktops.yaml` and `roles/desktop/defaults/main.yaml`:

| Mount point | NAS share |
|---|---|
| `~/synology` | `homes/agude` |
| `~/Documents` | `homes/agude/Documents` |
| `/mnt/synology/backups` | `backups` |
| `/mnt/synology/media` | `media` |
| `/mnt/synology/games` | `games` |

Systemd mounts each share on first access. `nofail` allows boot to continue
when the NAS is unavailable, and `x-systemd.mount-timeout=10s` limits new
mount attempts. After 60 seconds of inactivity, systemd attempts to unmount
the share; busy shares stay mounted. CIFS `soft` returns errors after network
retries rather than retrying indefinitely. The 10-second limit applies to
the mount command, not ongoing file operations.

The same NAS IP is used on the home LAN and through a VPN with a route to
the home LAN. If the NAS cannot be reached, access fails; accessing the path
again retries once connectivity is restored. No network dispatcher hook is
needed. Ansible removes the earlier `90-synology-mounts` retry hook.

Ansible writes fstab entries without contacting the NAS and starts the
automount units for shares that are not already mounted. Existing mounts
stay active; reboot after applying to migrate them to the shared policy.
On Einstein, this also switches `backups` and `media` from NFS4 to CIFS.

Before applying, check that the NAS paths contain no local files that would
be hidden by a mount. To apply only the NAS configuration on Einstein:

```bash
just apply einstein -c local -K --tags nas
```

On Dirac, run `just apply dirac -c local -K --tags nas` instead.

## Synology

The Synology NAS is in the inventory but has no playbook role. Set up
manually:

```bash
ssh synology
git clone https://github.com/agude/dotfiles.git ~/.dotfiles
~/.dotfiles/install.sh --profile synology
```
