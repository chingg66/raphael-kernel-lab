#!/usr/bin/env python3
"""Hook ksu_handle_stat() into the 64-bit newfstatat syscall.

SOVIET@16.0 does patch fs/stat.c for KernelSU, but only inside fstatat64 --
the 32-bit compat entry point. arm64 userspace calls newfstatat (syscall 79),
which has no hook at all.

That single omission explains the whole "KernelSU is running but `su` does not
exist" puzzle: shells and libc resolve a command with stat() *before* they
execve() it. execve() is hooked (fs/exec.c, do_execve), but the lookup fails
first with ENOENT, so the shell never gets as far as execve and prints
"inaccessible or not found". Meanwhile the driver looks perfectly healthy:
allowlist loads `com.android.shell uid: 2000 allow: 1` with root profile
u:r:ksu:s0, the manager gets its fd, dmesg shows the full KernelSU IOCTL table.

Fix: insert the same call newfstatat needs, idempotently.

Anchor is the first
    SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,
block followed by its `error = vfs_fstatat(dfd, filename, &stat, flag);`.
If the anchor is missing we exit 1 -- a silent no-op here is indistinguishable
from "the theory was wrong", and that has burned this project before.
"""
import pathlib
import sys

HOOK = """#ifdef CONFIG_KSU
	ksu_handle_stat(&dfd, &filename, &flag);
#endif
"""
SIG = "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,"
ANCHOR = "\terror = vfs_fstatat(dfd, filename, &stat, flag);"


def main() -> int:
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "fs/stat.c")
    if not path.is_file():
        print(f"FATAL: {path} not found", file=sys.stderr)
        return 1
    src = path.read_text()

    sig_at = src.find(SIG)
    if sig_at < 0:
        print(f"FATAL: {SIG!r} not found in {path}", file=sys.stderr)
        return 1

    anchor_at = src.find(ANCHOR, sig_at)
    if anchor_at < 0:
        print(f"FATAL: anchor {ANCHOR.strip()!r} not found after newfstatat",
              file=sys.stderr)
        return 1

    between = src[sig_at:anchor_at]
    if "ksu_handle_stat" in between:
        print(f"ok: newfstatat already hooked in {path}")
        return 0

    line_start = src.rfind("\n", 0, anchor_at) + 1
    out = src[:line_start] + HOOK + src[line_start:]
    path.write_text(out)

    check = path.read_text()
    sig2 = check.find(SIG)
    anchor2 = check.find(ANCHOR, sig2)
    if "ksu_handle_stat(&dfd, &filename, &flag);" not in check[sig2:anchor2]:
        print("FATAL: insertion did not take", file=sys.stderr)
        return 1
    print(f"patched: newfstatat now calls ksu_handle_stat ({path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
