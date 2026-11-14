#!/usr/bin/env bash
# Replace the in-tree KernelSU-Next driver with SukiSU-Ultra, then optionally
# apply the SUSFS patch set.
#
# Why SukiSU and not the bundled KernelSU-Next: the SUSFS KernelSU patch is laid
# out for the SukiSU tree (kernel/core, kernel/hook, kernel/supercall, kernel/feature,
# kernel/policy, ...). Tested 2026-11-14 against SOVIET@16.0's bundled
# KernelSU-Next: 3 of 25 files applied. Against SukiSU main: 24 of 32 files applied
# cleanly and only 5 hunks needed fuzz. Same idea for the fs/ side: 17 of 21 files
# apply straight onto this 4.14 tree.
#
# usage: setup_sukisu.sh <kernel-dir> [swap|susfs]
set -euo pipefail

KDIR="${1:-kernel}"
MODE="${2:-swap}"
# Pinned so a CI run is reproducible; bump deliberately.
SUKISU_SHA="dae36db016079546b9fc028636a3326d09979777"
SUKISU_URL="https://github.com/ShirkNeko/SukiSU-Ultra.git"
WS="${GITHUB_WORKSPACE:-$PWD}"

echo "== SukiSU setup: mode=$MODE sha=$SUKISU_SHA =="

if [ ! -d "$KDIR/drivers/kernelsu" ]; then
  echo "FATAL: $KDIR/drivers/kernelsu does not exist; refusing to guess the layout" >&2
  exit 1
fi

rm -rf /tmp/sukisu && mkdir -p /tmp/sukisu
git -C /tmp/sukisu init -q
git -C /tmp/sukisu remote add origin "$SUKISU_URL"
git -C /tmp/sukisu fetch -q --depth 1 origin "$SUKISU_SHA"
git -C /tmp/sukisu checkout -q FETCH_HEAD
echo "-- SukiSU version --"
git -C /tmp/sukisu log -1 --format='%h %s'

echo "-- replacing $KDIR/drivers/kernelsu --"
rm -rf "$KDIR/drivers/kernelsu"
cp -a /tmp/sukisu/kernel "$KDIR/drivers/kernelsu"
rm -rf "$KDIR/drivers/kernelsu/.git" "$KDIR/drivers/kernelsu/.vscode"

# The bundled copy carried SOVIET's own Kbuild banner/version plumbing. Nothing
# downstream reads it, but keep the tree free of dangling includes.
find "$KDIR/drivers/kernelsu" -name '*.sh' -maxdepth 1 -delete 2>/dev/null || true

if [ "$MODE" = "susfs" ]; then
  for p in 10_susfs_ksu_gki.patch 50_susfs_kernel_4.14.patch; do
    echo "-- applying patches/$p --"
    # --forward + fuzz: the SukiSU snapshot has drifted slightly from the patch
    # base, and the 4.14 fs/ context differs from the patch's upstream. Rejects
    # are collected and printed instead of aborting, so one CI run reports the
    # whole picture. The build is expected to FAIL while rejects exist.
    ( cd "$KDIR" && patch -p1 --fuzz=3 --forward --no-backup-if-mismatch \
        -i "$WS/patches/$p" ) || true
  done

  # 50_add_susfs_in_kernel-4.14.patch only touches EXISTING files. The new
  # translation units and headers ship as loose files and have to be copied in by
  # hand -- README steps 4 and 5. Forgetting this is what broke run 43549271034:
  # fs/stat.o died on `linux/susfs_def.h: No such file or directory` while every
  # patch reported success, because a patch that adds an #include is "clean".
  echo "-- copying SUSFS companion sources (fs/*, include/linux/*) --"
  for f in fs/susfs.c fs/sus_su.c include/linux/susfs.h include/linux/susfs_def.h include/linux/sus_su.h; do
    if [ ! -f "$WS/patches/susfs_4.14/$f" ]; then
      echo "FATAL: missing $WS/patches/susfs_4.14/$f" >&2
      exit 1
    fi
    mkdir -p "$(dirname "$KDIR/$f")"
    cp -f "$WS/patches/susfs_4.14/$f" "$KDIR/$f"
  done
  ls -l "$KDIR/fs/susfs.c" "$KDIR/fs/sus_su.c" "$KDIR/include/linux/susfs_def.h"

  echo "-- reject files --"
  if find "$KDIR" -name '*.rej' -print -quit | grep -q .; then
    find "$KDIR" -name '*.rej' | sed "s|^$KDIR/||" | sort
    echo "REJECTS PRESENT: the tree is inconsistent, do not trust this build"
    # Continue anyway so the compile step reports the real error surface, but
    # mark the run so it is obvious nothing here should be flashed.
    echo "SUSFS_REJECTS=yes" >> "${GITHUB_ENV:-/dev/null}" 2>/dev/null || true
  else
    echo "no rejects"
  fi
fi

echo "-- resulting driver --"
ls "$KDIR/drivers/kernelsu" | tr '\n' ' '; echo
