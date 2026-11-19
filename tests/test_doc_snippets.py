"""Every ```python block in the skill whose first line is `# runnable` must run against the live services.
These are the end-to-end examples an agent copies (microlensing, solar system, AGN samples, ...)."""
import os
import re
import sys

import pytest

from conftest import SKILL, am


def runnable_snippets():
    out = []
    for d, _, files in os.walk(SKILL):
        for f in sorted(files):
            if f.endswith(".md"):
                rel = os.path.relpath(os.path.join(d, f), SKILL)
                text = open(os.path.join(d, f)).read()
                for i, block in enumerate(re.findall(r"```python\n(# runnable.*?)```", text, re.S)):
                    out.append(pytest.param(block, id=f"{rel}#{i}"))
    return out


SNIPPETS = runnable_snippets()


@pytest.mark.offline
def test_key_pages_have_runnable_examples():
    ids = {p.id.split("#")[0] for p in SNIPPETS}
    assert {"science/microlensing.md", "science/solar-system.md", "science/agn.md"} <= ids


@pytest.mark.live
@pytest.mark.parametrize("code", SNIPPETS)
def test_runnable_snippet(code, capsys):
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    exec(compile(code, "<snippet>", "exec"), {"__name__": "__snippet__"})


@pytest.mark.live
def test_get_features_many_matches_get_features():
    one = am.get_features("ZTF17aabhbva", 0, ["Multiband_period", "Amplitude"], wide=True)
    many = am.get_features_many(["ZTF17aabhbva", "ZTF20acyxpwi"], 0, ["Multiband_period", "Amplitude"])
    oid = am.ztf_name_to_oid("ZTF17aabhbva")
    assert len(many) == 2
    for col in one.columns:
        assert many.loc[oid, col] == pytest.approx(one.iloc[0][col])


@pytest.mark.offline
def test_stamp_size_wording():
    """LSST stamps: usually 30x30, sometimes larger (user-confirmed); no stale fixed 51x51 claim."""
    assert "51x51 pixels" not in am.get_stamps.__doc__ and "usually 30x30" in am.get_stamps.__doc__


@pytest.mark.offline
def test_no_hard_coded_catids_in_recipes():
    from conftest import skill_text
    sql = skill_text("tap/recipes.md")
    assert "x.catid = 0" not in sql and "x.catid = 1" not in sql
