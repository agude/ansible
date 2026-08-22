# AGENTS.md

This file provides guidance to AI coding agents. CLAUDE.md and Gemini.md are symlinks to this file.

## Commands

```bash
just sync              # Install Python deps via uv
just lint              # yamllint + ansible-lint
just lint              # yamllint + ansible-lint (read-only)
just syntax-check      # Parse every play without touching a host
just check             # Everything CI runs: lint + syntax-check
just apply <host>      # Run playbook (host: einstein, dirac, kaon, synology, or "all")
just diff <host>       # Dry run with diff output
```

Run `just sync` before first use (installs Python deps and Ansible collections into `./collections`).

## Architecture

Ansible provisions personal Linux machines to the point where dotfiles and self-registering repos take over.

**Inventory groups**: desktops (einstein, dirac), pis (kaon), nas (synology)

**Playbook structure** (`site.yaml`):
- Play 1: `all:!nas` → common, livepatch, uv, claude_code, codex, opencode
- Play 2: `desktops` → czkawka, desktop, goose, cleanup
- Play 3: `pis` → pi
- Play 4: `nas` → synology (with Python interpreter detection)

**Variable precedence**: `group_vars/all.yaml` → `group_vars/<group>.yaml` → inventory host vars

**SSH key pattern**: `pubkeys/` contains cross-machine public keys named `<source>_to_<target>.pub`. The common role's `ssh-authorize.yaml` task distributes these.

## Vault

Secrets are encrypted with ansible-vault. The vault password file `.vault_pass.txt` is gitignored but required for linting (CI injects it from secrets).

Encrypt a new value:

```bash
uv run ansible-vault encrypt_string 'PASSWORD' --name 'smb_password'
```

## Role conventions

- Tasks split into logical files imported by `tasks/main.yaml`
- Use `become: true` for privilege escalation
- Use `no_log: true` for tasks handling secrets
- Use FQCN for all modules (e.g., `ansible.builtin.apt`, not `apt`)
- **Variables must carry the role name as a prefix** — ansible-lint enforces
  this. `desktop_nvidia_check`, not `nvidia_check`.
- Shell commands containing pipes need an explicit `set -o pipefail`, or use a
  pattern that avoids the need (`grep -q` returns 0/1 directly).

### Modernizing an older role

Checklist, applied when migrating a role written before these conventions:

- FQCN everywhere (`ansible.builtin.*`, `community.general.*`)
- `with_items` → `loop`
- Inline `k=v` argument form → block form
- `mode:` as a quoted string, not a bare octal
- Lowercase truthy values
- `meta/main.yml` carrying `role_name` / `namespace` and a minimum ansible
  version (2.14+)

## Debugging a failed run

Resume from a specific task rather than rerunning the whole play:

```bash
just apply einstein -c local -K --start-at-task "desktop : Remove Firefox snap"
```

The task name format is `"role : Task Name"` — role prefix, spaces around the
colon. Getting the spacing wrong silently matches nothing.

## Host-specific notes

### synology (DSM)

DSM is not a normal Linux: no apt, no systemd, no `os-release`, busybox
userland, and DSM itself owns sshd, hostname, and timezone through the GUI. The
`synology` role therefore does the minimum that is safe to automate — bind-mount
scripts, dotfiles install, pubkey authorization — and prints DSM Task Scheduler
instructions on change rather than trying to create those entries. Task
Scheduler entries are DB-backed and stay manual by design.

**Target Python must be 3.9+.** ansible-core 2.17+ hard-requires it, and DSM
7.3 ships only 3.8. No `ansible_python_interpreter` override works around this
— the requirement is enforced inside every module's bootstrap, not by
interpreter discovery. Install Synology's "Python 3.9" package from Package
Center; it creates `/usr/local/bin/python3.9`. The role probes
`/usr/local/bin/python3.{9,10,11,12,13}` with `raw` before gathering facts and
fails with install instructions if none is found. Probing the
`/usr/local/bin/python3.X` symlinks rather than versioned package paths keeps it
working across future Python package bumps.

Other DSM constraints: no `script` binary, so the dotfiles profile must be
server-style with no TTY wrapper or interactive prompts. `become_user` works for
user-owned paths under `/volume1/homes/`, but pubkey authorization needs sudo.

### desktops (einstein, dirac)

NVIDIA support is auto-detected with `lspci | grep -qi nvidia`, which
conditionally includes `nvidia.yaml` and runs `ubuntu-drivers autoinstall`. No
inventory variables are needed. Note that an RTX 5060 (Blackwell) requires
driver 595 or newer; driver 580 predates Blackwell and will not work.

NAS home shares are mounted over CIFS with `ansible.posix.mount`. **Check that
the target path is already a mount point before running:** if
`/home/agude/Documents` holds local files and the NAS mounts over it, those
files are shadowed — still on disk, but inaccessible until unmount.
