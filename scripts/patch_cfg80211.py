#!/usr/bin/env python3
"""为 kernel 6.12 修正 AIC8800 驱动里两个 cfg80211 调用的参数个数。

6.12 起签名变为 (dev, addr, gfp)，旧代码只传了 (dev, addr)。
"""
import re
import sys


def count_top_commas(argstr: str) -> int:
    depth = 0
    commas = 0
    for ch in argstr:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            commas += 1
    return commas


def fix_call(src: str, fname: str) -> tuple[str, int]:
    pattern = re.compile(re.escape(fname) + r"\s*\(", re.S)
    out = []
    pos = 0
    fixed = 0
    for m in pattern.finditer(src):
        start = m.end()  # just after '('
        depth = 1
        i = start
        while i < len(src) and depth > 0:
            ch = src[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if depth != 0:
            continue
        args = src[start:i]
        out.append(src[pos:start])
        if count_top_commas(args) >= 2:
            out.append(args)          # already 3 args
        else:
            out.append(args + ", GFP_ATOMIC")
            fixed += 1
        pos = i
    out.append(src[pos:])
    return "".join(out), fixed


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: patch_cfg80211.py <file.c>")
        return 2
    path = sys.argv[1]
    src = open(path, encoding="utf-8", errors="surrogateescape").read()
    total = 0
    for fn in ("cfg80211_rx_spurious_frame", "cfg80211_rx_unexpected_4addr_frame"):
        src, n = fix_call(src, fn)
        print(f"patched {fn}: {n}")
        total += n
    open(path, "w", encoding="utf-8", errors="surrogateescape").write(src)
    print(f"TOTAL {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
