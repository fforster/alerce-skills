"""Tiny snapshot helper for drift tests.

check_snapshot(name, data, update) compares JSON-serialisable `data` with tests/baselines/<name>.json.
* --update-baselines (or a missing baseline): write the file and pass.
* otherwise: fail with a readable diff of what was added, removed or changed.
"""
from __future__ import annotations

import json
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baselines")


def _norm(x):
    return json.loads(json.dumps(x, sort_keys=True, default=str))


def _diff(old, new, path="", out=None, limit=60):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old) - set(new)):
            out.append(f"- removed {path}/{k}")
        for k in sorted(set(new) - set(old)):
            out.append(f"+ added   {path}/{k} = {json.dumps(new[k])[:120]}")
        for k in sorted(set(old) & set(new)):
            _diff(old[k], new[k], f"{path}/{k}", out, limit)
    elif isinstance(old, list) and isinstance(new, list) and all(isinstance(v, (str, int, float)) for v in old + new):
        for v in sorted(set(map(str, old)) - set(map(str, new))):
            out.append(f"- removed {path}: {v}")
        for v in sorted(set(map(str, new)) - set(map(str, old))):
            out.append(f"+ added   {path}: {v}")
        if not out and old != new:
            out.append(f"~ reordered {path}")
    elif old != new:
        out.append(f"~ changed {path}: {json.dumps(old)[:120]} -> {json.dumps(new)[:120]}")
    return out


def check_snapshot(name: str, data, update: bool = False):
    os.makedirs(BASE, exist_ok=True)
    path = os.path.join(BASE, f"{name}.json")
    new = _norm(data)
    if update or not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(new, f, indent=1, sort_keys=True)
            f.write("\n")
        return
    with open(path) as f:
        old = json.load(f)
    diff = _diff(old, new)
    assert not diff, (f"ALeRCE changed since baseline {name}.json "
                      f"(update the skill, then run: pytest -m drift --update-baselines):\n  " + "\n  ".join(diff))
