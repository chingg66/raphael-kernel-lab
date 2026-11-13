#!/usr/bin/env python3
"""Unlock selected read-only /proc/sys/vm tunables in the raphael 4.14 tree.

Why: this vendor tree registers a handful of sensitive VM sysctls with
`.mode = 0444` in kernel/sysctl.c.  procfs checks sysctl write permission with
test_perm(), which shifts the file mode by the *effective uid* and does NOT
honour CAP_DAC_OVERRIDE -- so even uid 0 gets EACCES.  Nothing in userspace can
change that; the table has to be rebuilt with 0644.

Only the entries we actually tune are touched; everything else keeps the
vendor's 0444 lockdown.

Idempotent: rerunning on an already-patched tree is a no-op.
Fails loudly (exit 1) if a target entry is missing, so a silent no-op can never
be mistaken for a successful patch.
"""

import re
import sys

TARGET = "kernel/sysctl.c"
NAMES = ["swappiness", "vfs_cache_pressure", "watermark_scale_factor"]

BLOCK = r"\{\s*\.procname\s*=\s*\"%s\"[\s\S]*?\n\s*\},"
MODE = re.compile(r"\.mode\s*=\s*(\d+)")


def main():
    try:
        with open(TARGET, "r", encoding="utf-8", errors="surrogateescape") as f:
            src = f.read()
    except OSError as e:
        print("FATAL: cannot read %s: %s" % (TARGET, e))
        return 1

    patched = []
    already = []
    missing = []

    for name in NAMES:
        rx = re.compile(BLOCK % re.escape(name))
        m = rx.search(src)
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
        new_block = MODE.sub(lambda mo: ".mode = 0644" if mo.group(1) == "0444" else mo.group(0), block, count=1)
        src = src[: m.start()] + new_block + src[m.end():]
        patched.append(name)

    print("sysctl unlock: patched=%s already=%s" % (patched, already))

    if missing:
        print("FATAL: could not find these vm_table entries in %s: %s" % (TARGET, missing))
        return 1

    # re-verify on the final buffer
    for name in NAMES:
        m = re.search(BLOCK % re.escape(name), src)
        if not m or not re.search(r"\.mode\s*=\s*0?644", m.group(0)):
            print("FATAL: %s is still not 0644 after patching" % name)
            return 1

    with open(TARGET, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(src)

    print("sysctl unlock: OK -- %s now 0644" % ", ".join(NAMES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
