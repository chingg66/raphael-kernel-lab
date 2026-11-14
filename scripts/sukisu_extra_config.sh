#!/usr/bin/env bash
# Print the extra Kconfig fragment needed by the SukiSU / SUSFS build to stdout.
# Kept out of the workflow file because GitHub rejects a single `run:` template
# over 21,000 characters, and the build step is already at the ceiling.
#
# usage: sukisu_extra_config.sh [true|false]   (arg = enable SUSFS)
set -euo pipefail
SUSFS="${1:-false}"

# SukiSU hooks through kprobes; the bundled KernelSU-Next used manual hooks
# (CONFIG_KSU_MANUAL_HOOK) precisely because this tree never enabled them.
cat <<'EOF'
CONFIG_KPROBES=y
EOF

if [ "$SUSFS" = "true" ]; then
  cat <<'EOF'
CONFIG_KSU_SUSFS=y
CONFIG_KSU_SUSFS_SUS_PATH=y
CONFIG_KSU_SUSFS_SUS_MOUNT=y
CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT=y
CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT=y
CONFIG_KSU_SUSFS_SUS_KSTAT=y
CONFIG_KSU_SUSFS_SPOOF_UNAME=y
CONFIG_KSU_SUSFS_ENABLE_LOG=y
CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS=y
CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG=y
CONFIG_KSU_SUSFS_OPEN_REDIRECT=y
CONFIG_KSU_SUSFS_SUS_MAP=y
CONFIG_KSU_SUSFS_TRY_UMOUNT=y
CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT=y
EOF
fi
