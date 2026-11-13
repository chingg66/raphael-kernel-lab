#!/usr/bin/env python3
"""Drop a stray duplicate declaration in block/mq-deadline.c.

SOVIET-ANDROID/kernel_xiaomi_raphael@16.0 carries a botched merge in
block/mq-deadline.c: __dd_dispatch_request() already receives
`struct deadline_data *dd` as its parameter, but the first statement of the
body re-declares `dd` from `hctx` -- a variable that does not exist in that
scope. Nobody noticed because raphael_defconfig clears
CONFIG_MQ_IOSCHED_DEADLINE, so the file was never compiled. Turning the
scheduler on (block/Kconfig.iosched defaults it to y) fails immediately:

    ../block/mq-deadline.c:200:24: error: redefinition of 'dd'
    ../block/mq-deadline.c:200:29: error: use of undeclared identifier 'hctx'

Now that we enable the scheduler on purpose, delete exactly that line. The
script is idempotent and fails loudly if the tree changes underneath it, so a
silent no-op can never be mistaken for a successful patch.
"""

import sys

PATH = "block/mq-deadline.c"
SIG = "static struct request *__dd_dispatch_request(struct deadline_data *dd)\n{\n"
STRAY = "\tstruct deadline_data *dd = hctx->queue->elevator->elevator_data;\n"


def main():
    try:
        with open(PATH, encoding="utf-8") as fh:
            src = fh.read()
    except OSError as exc:
        print(f"FATAL: cannot read {PATH}: {exc}")
        return 1

    if SIG + STRAY in src:
        with open(PATH, "w", encoding="utf-8") as fh:
            fh.write(src.replace(SIG + STRAY, SIG, 1))
        print(f"ok {PATH}: dropped the stray 'dd = hctx->...' re-declaration")
        return 0

    if SIG in src and STRAY not in src:
        print(f"ok {PATH}: already clean, nothing to do")
        return 0

    print(
        f"FATAL: {PATH}: expected signature/stray line not found. "
        "The tree changed -- re-check before trusting this patch."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
