"""Claims from the book's TAP Schema Explorer (tap/indexes-and-joins.md, tap/columns.md, tap/examples.md) and
science/solar-system.md."""
import os
import re
import subprocess
import sys
import tempfile

import pytest
import requests

from conftest import API, ROOT, am, skill_text
from snapshot import check_snapshot

BOOK_EXPLORER = os.path.join(ROOT.split("/alerce-skills")[0], "alerce-book", "explorer")


def example_queries():
    text = skill_text("tap/examples.md")
    sections = re.split(r"^### ", text, flags=re.M)[1:]
    out = []
    for sec in sections:
        title = sec.splitlines()[0]
        for i, (q, note) in enumerate(re.findall(r"```sql\n(.*?)```\n(→ [^\n]*)", sec, re.S)):
            n = int(re.search(r"→ (\d+) row", note).group(1)) if re.search(r"→ (\d+) row", note) else None
            out.append(pytest.param(q, n, id=f"{title.replace(' · ', '-')}-{i}"))
    return out


EXAMPLES = example_queries()


@pytest.mark.offline
def test_examples_md_has_all_69_queries():
    assert len(EXAMPLES) == 69


@pytest.mark.examples
@pytest.mark.live
@pytest.mark.parametrize("query,rows_then", EXAMPLES)
def test_example_query_runs(query, rows_then):
    """Every workflow query in tap/examples.md still runs; queries that returned rows in the snapshot still do
    (forced photometry of moving objects returns 0 rows by design)."""
    df = am.tap_query(query, maxrec=1000, cache=False)
    if rows_then:
        assert len(df) > 0, "returned rows in the book snapshot, none now"


@pytest.mark.offline
@pytest.mark.skipif(not os.path.isdir(BOOK_EXPLORER), reason="alerce-book/explorer not available")
def test_generated_files_match_book_source():
    """tap/{indexes-and-joins,columns,examples}.md are what tools/build_schema_refs.py makes from the book today.
    Fails when the book's daily refresh changed something: rerun the tool and review the diff."""
    with tempfile.TemporaryDirectory() as tmp:
        for d in ("alerce/tap", "tests/baselines"):
            os.makedirs(os.path.join(tmp, d))
        tool = open(os.path.join(ROOT, "tools", "build_schema_refs.py")).read()
        os.makedirs(os.path.join(tmp, "tools"))
        open(os.path.join(tmp, "tools", "build_schema_refs.py"), "w").write(tool)
        subprocess.run([sys.executable, os.path.join(tmp, "tools", "build_schema_refs.py"), BOOK_EXPLORER],
                       check=True, capture_output=True)
        undate = lambda s: re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", s)  # the book rebuilds daily; dates alone differ
        for f in ("indexes-and-joins.md", "columns.md", "examples.md"):
            fresh = open(os.path.join(tmp, "alerce", "tap", f)).read()
            assert undate(fresh) == undate(skill_text(f"tap/{f}")), \
                f"{f} is out of date with the book: run python tools/build_schema_refs.py and review the diff"


@pytest.mark.live
def test_columns_md_covers_every_live_column(tap_columns_live):
    """tap/columns.md documents every live alerce_tap column (else the book snapshot is stale)."""
    doc = skill_text("tap/columns.md")
    missing = []
    for t, g in tap_columns_live.groupby("table_name"):
        sec = doc.split(f"\n## {t.split('.', 1)[1]}\n", 1)
        if len(sec) < 2:
            missing.append(t)
            continue
        body = sec[1].split("\n## ", 1)[0]
        missing += [f"{t}.{c}" for c in g.column_name if f"| `{c}` |" not in body]
    assert not missing, missing[:30]


@pytest.mark.drift
@pytest.mark.live
def test_snapshot_tap_index_flags(update_baselines):
    """TAP_SCHEMA 'indexed' hints per table (a changed index usually changes which queries are fast)."""
    df = am.tap_query("SELECT table_name, column_name FROM TAP_SCHEMA.columns "
                      "WHERE table_name LIKE 'alerce_tap.%' AND indexed = 1", maxrec=10000)
    check_snapshot("tap_index_flags", {t: sorted(g.column_name) for t, g in df.groupby("table_name")},
                   update_baselines)


@pytest.mark.live
def test_indexed_filters_are_fast():
    """Claim (indexes-and-joins.md): per-oid filters and the hunter-style probability scan return quickly."""
    import time
    for q in ("SELECT * FROM alerce_tap.magstat WHERE oid = 36029005852662990 AND sid = 0",
              "SELECT TOP 20 oid, probability FROM alerce_tap.probability WHERE sid = 1 AND ranking = 1 "
              "ORDER BY probability DESC",
              "SELECT TOP 20 oid FROM alerce_tap.object WHERE sid = 1 ORDER BY lastmjd DESC"):
        t0 = time.time()
        am.tap_query(q, maxrec=100, cache=False)
        assert time.time() - t0 < 20, q


# ---------------- science/solar-system.md ----------------
@pytest.fixture(scope="module")
def ss_object():
    df = am.tap_query("SELECT TOP 1 o.oid, o.n_det FROM alerce_tap.object o WHERE o.sid = 2 ORDER BY o.lastmjd DESC",
                      maxrec=1, cache=False)
    assert not df.empty, "no sid = 2 objects"
    return int(df.oid.iloc[0])


@pytest.mark.live
def test_ss_objects_have_detections_geometry_no_forced(ss_object):
    det = am.tap_query(f"SELECT TOP 5 measurement_id FROM alerce_tap.lsst_detection WHERE oid = {ss_object} AND sid = 2")
    geo = am.tap_query(f"SELECT TOP 5 measurement_id, phaseangle FROM alerce_tap.lsst_ss_detection "
                       f"WHERE ssobjectid = {ss_object}")
    fp = am.tap_query(f"SELECT TOP 5 measurement_id FROM alerce_tap.forced_photometry WHERE oid = {ss_object} AND sid = 2")
    assert len(det) and len(geo) and fp.empty


@pytest.mark.live
def test_ss_objects_have_no_features(luts):
    """Claim: no feature names exist for sid = 2."""
    assert luts["feature_name"][luts["feature_name"].sid == 2].empty


@pytest.mark.live
def test_rest_api_does_not_serve_sid2(ss_object):
    """Claim: the multisurvey REST API serves sid 0 and 1 only (an ssObjectId is not found as an LSST object)."""
    r = requests.get(f"{API}/object_api/object", params=dict(oid=ss_object, survey_id="lsst"), timeout=60)
    assert r.status_code == 404 or int(r.json().get("sid", -1)) != 2


@pytest.mark.live
def test_mpc_orbits_neo_query():
    df = am.tap_query("SELECT TOP 5 ssobjectid, q, h FROM alerce_tap.lsst_mpc_orbits WHERE q < 1.3 ORDER BY h")
    assert len(df) and (df.q < 1.3).all()
