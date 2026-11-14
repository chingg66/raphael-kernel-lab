#!/usr/bin/env python3
"""Unlock / extend selected /proc/sys/vm tunables in the raphael 4.14 tree.

Two separate problems, both fixed here:

1. READ-ONLY MODE.  vm_table[] registers swappiness / vfs_cache_pressure /
   watermark_scale_factor with `.mode = 0444`.  procfs checks sysctl writes in
   test_perm(), which shifts the file mode by the *effective uid* and never
   consults CAP_DAC_OVERRIDE -- so even uid 0 gets EACCES.  Userspace cannot fix
   this; the table has to be rebuilt with 0644.

2. SWAPPINESS CEILING.  swappiness is declared with `.extra2 = &one_hundred`,
   so proc_dointvec_minmax() rejects anything above 100 -- and 100 is already the
   default, leaving no headroom at all.  Point extra2 at a new
   `swappiness_max = 200` constant so the knob actually becomes adjustable.

Everything else keeps the vendor's 0444 lockdown.

Idempotent: rerunning on an already-patched tree is a no-op.
Fails loudly (exit 1) if a target entry disappears, so a silent no-op can never
be mistaken for a successful patch.
"""

import re
import sys

TARGET = "kernel/sysctl.c"
NAMES = ["swappiness", "vfs_cache_pressure", "watermark_scale_factor"]

BLOCK = r"\{\s*\.procname\s*=\s*\"%s\"[\s\S]*?\n\s*\},"
MODE = re.compile(r"\.mode\s*=\s*(\d+)")
DECL_ANCHOR = "static int one_hundred = 100;\n"
DECL = DECL_ANCHOR + "static int swappiness_max = 200;\n"
EXTRA2 = re.compile(r"\.extra2\s*=\s*&one_hundred")


def block_of(src, name):
    return re.compile(BLOCK % re.escape(name)).search(src)


def main():
    try:
        with open(TARGET, "r", encoding="utf-8", errors="surrogateescape") as f:
            src = f.read()
    except OSError as e:
        print("FATAL: cannot read %s: %s" % (TARGET, e))
        return 1

    patched, already, missing = [], [], []

    # --- 1. mode 0444 -> 0644 for the three entries -------------------------
    for name in NAMES:
        m = block_of(src, name)
        if not m:
            missing.append(name)
            continue
        block = m.group(0)
        modes = MODE.findall(block)
        if "0644" in modes or "644" in modes:
            already.append(name)
            continue
        if "0444" not in modes:
            missing.append(name)
            continue
        new_block = MODE.sub(
            lambda mo: ".mode = 0644" if mo.group(1) == "0444" else mo.group(0), block, count=1
        )
        src = src[: m.start()] + new_block + src[m.end():]
        patched.append(name)

    print("sysctl unlock: mode patched=%s already=%s" % (patched, already))

    # --- 2. swappiness ceiling 100 -> 200 -----------------------------------
    ceiling = "already"
    if "swappiness_max" not in src:
        if DECL_ANCHOR not in src:
            print("FATAL: anchor %r not found in %s" % (DECL_ANCHOR.strip(), TARGET))
            return 1
        src = src.replace(DECL_ANCHOR, DECL, 1)
        ceiling = "declared"
    else:
        ceiling = "declared-already"

    m = block_of(src, "swappiness")
    if not m:
        print("FATAL: swappiness entry vanished before extra2 fix")
        return 1
    block = m.group(0)
    if "swappiness_max" in block:
        ceiling += ", extra2-already"
    elif EXTRA2.search(block):
        new_block = EXTRA2.sub(".extra2 = &swappiness_max", block, count=1)
        src = src[: m.start()] + new_block + src[m.end():]
        ceiling += ", extra2-repointed"
    else:
        print("FATAL: swappiness .extra2 = &one_hundred not found")
        return 1
    print("sysctl unlock: swappiness ceiling -> 200 (%s)" % ceiling)

    # --- verify -------------------------------------------------------------
    if missing:
        print("FATAL: could not find these vm_table entries in %s: %s" % (TARGET, missing))
        return 1
    for name in NAMES:
        m = block_of(src, name)
        if not m or not re.search(r"\.mode\s*=\s*0?644", m.group(0)):
            print("FATAL: %s is still not 0644 after patching" % name)
            return 1
    sw = block_of(src, "swappiness").group(0)
    if "&swappiness_max" not in sw or "static int swappiness_max = 200;" not in src:
        print("FATAL: swappiness ceiling patch did not land")
        return 1

    with open(TARGET, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(src)

    print("sysctl unlock: OK -- %s 0644, swappiness max 200" % ", ".join(NAMES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
