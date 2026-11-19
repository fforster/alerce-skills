"""Drift detection: compare the live state of ALeRCE with tests/baselines/*.json, and the skill docs with the
live lists.  A failure means ALeRCE changed (or the docs are stale): read the diff, update the skill files, then
`pytest -m drift --update-baselines`."""
import re

import pytest
import requests

from conftest import API, skill_text, am
from snapshot import check_snapshot

pytestmark = [pytest.mark.drift, pytest.mark.live]
SERVICES = ["object", "lightcurve", "probability", "features", "magstat", "crossmatch", "stamps", "classifier", "aladin"]


# ---------------- snapshots ----------------
def test_snapshot_classifiers(luts, update_baselines):
    c = luts["classifier"].sort_values("classifier_id")
    check_snapshot("classifiers", {str(r.classifier_id): [r.classifier_name, r.classifier_version, int(r.tid)]
                                   for r in c.itertuples()}, update_baselines)


def test_snapshot_taxonomy(luts, update_baselines):
    t = luts["taxonomy"].merge(luts["classifier"][["classifier_id", "classifier_name"]], on="classifier_id")
    data = {n: {r.class_name: int(r.class_id) for r in g.itertuples()} for n, g in t.groupby("classifier_name")}
    check_snapshot("taxonomy", data, update_baselines)


def test_snapshot_bands_and_surveys(luts, update_baselines):
    data = {"band": {f"{r.sid}:{r.band}": r.band_name for r in luts["band"].itertuples()},
            "sid": {str(r.sid): r.survey_name for r in luts["sid"].itertuples()},
            "catalog": {str(r.catid): r.catalog_name for r in luts["catalog"].itertuples()}}
    check_snapshot("luts", data, update_baselines)


def test_snapshot_tap_columns(tap_columns_live, update_baselines):
    data = {t: sorted(g.column_name) for t, g in tap_columns_live.groupby("table_name")}
    check_snapshot("tap_columns", data, update_baselines)


def test_snapshot_feature_names(luts, update_baselines):
    f = luts["feature_name"]
    check_snapshot("feature_names", {str(s): sorted(g.feature_name) for s, g in f.groupby("sid")}, update_baselines)


def _openapi(name):
    spec = requests.get(f"{API}/{name}_api/openapi.json", timeout=60).json()
    paths = {}
    for p, ops in spec["paths"].items():
        for m, op in ops.items():
            paths[f"{m.upper()} {p}"] = sorted(
                prm["name"] + ("*" if prm.get("required") else "") for prm in op.get("parameters", []))
    return spec["info"]["version"], paths


@pytest.fixture(scope="module")
def openapi_all():
    return {n: _openapi(n) for n in SERVICES}


def test_snapshot_rest_endpoints(openapi_all, update_baselines):
    """Endpoints and parameters (required marked *) of every multisurvey API service."""
    check_snapshot("rest_endpoints", {n: paths for n, (_, paths) in openapi_all.items()}, update_baselines)


def test_snapshot_rest_versions(openapi_all, update_baselines):
    check_snapshot("rest_versions", {n: v for n, (v, _) in openapi_all.items()}, update_baselines)


def test_snapshot_legacy_ztf_classifiers(update_baselines):
    rows = requests.get("https://api.alerce.online/ztf/v1/classifiers", timeout=60).json()
    check_snapshot("legacy_ztf_classifiers", sorted({r["classifier_name"] for r in rows}), update_baselines)


def test_snapshot_lightcurve_fields(ztf_sn_bundle, lsst_sn_bundle, update_baselines):
    data = {f"{s}:{k}": sorted(b[k][0]) for s, b in (("ztf", ztf_sn_bundle), ("lsst", lsst_sn_bundle))
            for k in ("detections", "forced_photometry") if b[k]}
    check_snapshot("lightcurve_fields", data, update_baselines)


# ---------------- docs vs live ----------------
def test_docs_name_every_live_classifier(luts):
    """classifiers/index.md mentions every live classifier (new classifiers need documenting)."""
    doc = skill_text("classifiers/index.md")
    missing = [n for n in luts["classifier"].classifier_name if n not in doc]
    assert not missing, f"classifiers not documented in classifiers/index.md: {missing}"


def test_docs_classifier_versions_match(luts):
    """The version written next to each classifier in the classifiers table is the live one."""
    doc = skill_text("classifiers/index.md")
    for r in luts["classifier"].itertuples():
        m = re.search(rf"`{re.escape(r.classifier_name)}` \| ([0-9.]+) \|", doc)
        if m:
            assert m.group(1) == r.classifier_version, (r.classifier_name, m.group(1), r.classifier_version)


def test_docs_name_every_tap_table(tap_tables_live):
    """tap/schema.md mentions every alerce_tap table, and no table that doesn't exist."""
    doc = skill_text("tap/schema.md")
    live = {t.split(".", 1)[1] for t in tap_tables_live.table_name}
    missing = sorted(t for t in live if f"`{t}`" not in doc)
    assert not missing, f"tables missing from tap/schema.md: {missing}"
    current = doc.split("## Legacy schema", 1)[0]  # the legacy ztf.* section has its own tables
    documented = set(re.findall(r"^\| `([a-z0-9_]+)`", current, re.M))
    assert not (documented - live), f"documented but not live: {documented - live}"


def test_docs_columns_exist(tap_columns_live):
    """Every column the recipes use (x.<col>, d.<col>, ...) in tap/recipes.md exists in some alerce_tap table."""
    doc = skill_text("tap/recipes.md") + skill_text("hunter/candidate-search.md")
    sql = "\n".join(re.findall(r"```sql\n(.*?)```", doc, re.S))
    assert sql
    live = set(tap_columns_live.column_name)
    upload_aliases = set(re.findall(r"tap_upload\.\w+\s+AS\s+(\w+)", sql, re.I))  # columns of uploaded tables
    used = {c for a, c in re.findall(r"\b([a-z]{1,2})\.([a-z_][a-z0-9_]*)\b", sql) if a not in upload_aliases}
    unknown = sorted(c for c in used if c not in live and c not in {"oid", "sid"})
    assert not unknown, f"columns used in recipes but not in TAP: {unknown}"


def test_docs_rest_endpoints_exist(openapi_all):
    """Every `<name>_api/<path>` written in the api docs is a live endpoint."""
    live = {f"{n}_api{p.split(' ', 1)[1]}" for n, (_, paths) in openapi_all.items() for p in paths}
    doc = skill_text("api/index.md") + skill_text("api/multisurvey.md") + skill_text("SKILL.md")
    used = set(re.findall(r"\b([a-z]+_api/[a-z_/\-]+[a-z])\b", doc))
    missing = sorted(u for u in used if "/" + u.split("/", 1)[1] not in {p.split("_api", 1)[1] for p in live}
                     or not any(l.startswith(u) for l in live))
    assert not missing, f"endpoints in docs but not live: {missing}"


def test_docs_feature_names_exist(luts):
    """Feature names written in backticks in tap/schema.md and science/*.md exist (wildcards ignored)."""
    names = set(luts["feature_name"].feature_name)
    doc = "".join(skill_text(f) for f in ("tap/schema.md", "science/agn.md", "science/variable-stars.md"))
    cands = set(re.findall(r"`([A-Za-z][A-Za-z0-9_\-/]*)`", doc))
    looks_like_feature = {c for c in cands if re.match(r"^(GP_|SPM_|SF_ML|Multiband|Period_|PPE|ExcessVar|Pvar|"
                                                       r"Harmonics_|fleet_|TDE_|ulens_|MHPS_|IAR_|Amplitude)", c)
                          and "*" not in c and ".." not in c and "/" not in c[c.find("_"):]}
    unknown = sorted(c for c in looks_like_feature if c not in names and not c.endswith("_"))
    assert not unknown, f"feature names in docs but not in feature_name_lut: {unknown}"
