#!/usr/bin/env python3
"""Structural check of the alerce skill: every referenced .md file exists, every .md file is reachable
from SKILL.md, SKILL.md has valid frontmatter and stays short.  Exit code 1 on any problem."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
problems = []

skill = open(os.path.join(ROOT, "SKILL.md")).read()
m = re.match(r"^---\nname: ([a-z0-9-]+)\ndescription: (.+?)\n---\n", skill, re.S)
if not m:
    problems.append("SKILL.md: bad frontmatter")
elif len(m.group(2)) > 1024:
    problems.append(f"SKILL.md: description too long ({len(m.group(2))} > 1024 chars)")
n_lines = skill.count("\n")
if n_lines > 150:
    problems.append(f"SKILL.md: {n_lines} lines (> 150)")

md_files = {os.path.relpath(os.path.join(d, f), ROOT)
            for d, _, fs in os.walk(ROOT) for f in fs if f.endswith(".md")}
reached = {"SKILL.md"}
ref_re = re.compile(r"`((?:\.\./)?[a-z_-]+(?:/[a-z_-]+)*\.md)(?:#[^`]*)?`")
for rel in sorted(md_files):
    text = open(os.path.join(ROOT, rel)).read()
    base = os.path.dirname(rel)
    for ref in ref_re.findall(text):
        # SKILL.md references are relative to the root; others relative to their own dir
        target = os.path.normpath(os.path.join(base, ref)) if rel != "SKILL.md" else os.path.normpath(ref)
        if target not in md_files:
            alt = os.path.normpath(ref)          # tolerate root-relative refs inside subfiles
            if alt in md_files:
                target = alt
            else:
                problems.append(f"{rel}: reference to missing {ref}")
                continue
        reached.add(target)
for orphan in sorted(md_files - reached):
    problems.append(f"{orphan}: not referenced from any other file")

for script in ("alerce_ms.py", "alerce_cli.py", "smoke_test.py"):
    if not os.path.exists(os.path.join(ROOT, "scripts", script)):
        problems.append(f"scripts/{script} missing")

print(f"{len(md_files)} markdown files, SKILL.md {n_lines} lines")
for p in problems:
    print("PROBLEM:", p)
print("OK" if not problems else f"{len(problems)} problem(s)")
sys.exit(1 if problems else 0)
