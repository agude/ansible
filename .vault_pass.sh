#!/bin/sh
# Fetch the Ansible Vault password from 1Password.
#
# Requires the 1Password CLI (`op`) installed and signed in:
#   https://developer.1password.com/docs/cli/get-started/
#
# Update OP_REF to match the item you create in 1Password.

set -eu

OP_REF="op://Private/ansible-vault/password"

exec op read "$OP_REF"
