#!/usr/bin/env python3
"""
Inspect an exported functional-coverage XML and list uncovered bins.

    python3 show_coverage.py [coverage_functional.xml]

Useful for debugging a run after the fact without re-simulating: the XML
records every bin and its hit count, so bins with hits="0" are exactly the
scenarios the stimulus never produced.
"""

import sys
import xml.etree.ElementTree as ET

path = sys.argv[1] if len(sys.argv) > 1 else "coverage_functional.xml"
root = ET.parse(path).getroot()

print(f"{'coverpoint':<22} {'cov%':>7}  bins")
print("-" * 60)
missing_total = 0
for cp in root:
    name = cp.get("abs_name", cp.tag)
    pct = float(cp.get("cover_percentage", "0"))
    size = cp.get("size")
    cov = cp.get("coverage")
    missing = [b.get("bin") for b in cp if b.get("hits") == "0"]
    thin = [
        (b.get("bin"), int(b.get("hits", 0)))
        for b in cp
        if 0 < int(b.get("hits", 0)) < 5
    ]
    flag = f"   <-- {len(missing)} MISSING" if missing else ""
    print(f"{name:<22} {pct:6.2f}%  ({cov}/{size}){flag}")
    for b in missing:
        print(f"      MISSING : {b}")
        missing_total += 1
    for b, h in thin:
        print(f"      thin    : {b}  (only {h} hit{'s' if h > 1 else ''})")

print("-" * 60)
print(
    f"TOTAL {float(root.get('cover_percentage', 0)):.2f}%  "
    f"({missing_total} uncovered bin(s))"
)
