"""Live claims: classifiers/index.md, explorer/index.md, hunter/*.md, crossmatch/index.md, science/*.md."""
import pytest
import requests

from conftest import (LSST_QSO, LSST_RRL, LSST_SN, ZTF_QSO, ZTF_RRL, ZTF_SN, am)

T = 60


# ---------------- classifiers ----------------
@pytest.mark.live
@pytest.mark.parametrize("name,tid", [("stamp_classifier_rubin_beta_20260421", 1), ("stamp_classifier", 0),
                                      ("lc_classifier_BHRF_forced_phot", 0),
                                      ("stamp_sn_offnuclear_rubin_beta", 1)])
def test_documented_default_classifiers_exist(luts, name, tid):
    """Claim: the defaults named in the skill exist for the right survey (tid)."""
    c = luts["classifier"]
    assert ((c.classifier_name == name) & (c.tid == tid)).any()


@pytest.mark.live
def test_no_lsst_light_curve_classifier(luts):
    """Claim: there is no LSST light-curve classifier yet (fails when one appears: update the skill)."""
    c = luts["classifier"]
    assert not c[(c.tid == 1) & c.classifier_name.str.startswith("lc_")].shape[0]


@pytest.mark.live
def test_class_ids_are_per_classifier():
    """Claim: QSO is class 10 in the flat BHRF and 4 in the stochastic branch."""
    assert am.class_id("lc_classifier_BHRF_forced_phot", "QSO") != am.class_id(
        "lc_classifier_BHRF_forced_phot_stochastic", "QSO")


@pytest.mark.live
def test_bhrf_hierarchy_is_consistent():
    """Claim: P(class) ~ P_top(branch) x P_branch(class); the flat classifier agrees in ranking."""
    p = am.get_probabilities(ZTF_QSO, 0)
    get = lambda clf, cls: float(p[(p.classifier_name == clf) & (p.class_name == cls)].probability.iloc[0])
    prod = get("lc_classifier_BHRF_forced_phot_top", "Stochastic") * get("lc_classifier_BHRF_forced_phot_stochastic", "QSO")
    flat = get("lc_classifier_BHRF_forced_phot", "QSO")
    assert prod == pytest.approx(flat, abs=0.15)


@pytest.mark.live
def test_probability_lastmjd_present():
    p = am.get_probabilities(LSST_SN, 1)
    assert p.lastmjd.notna().all()


# ---------------- explorer ----------------
EXP = "https://explorer-experiment.alerce.online"


@pytest.mark.live
def test_explorer_health():
    assert requests.get(f"{EXP}/api/health", timeout=T).json() == {"status": "ok"}


@pytest.mark.live
def test_explorer_old_style_redirect():
    """Claim: /object/{oid} redirects (302) to /?survey=...&oid=..."""
    r = requests.get(f"{EXP}/object/{ZTF_SN}", timeout=T, allow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == f"/?survey=ztf&oid={ZTF_SN}"


@pytest.mark.live
@pytest.mark.parametrize("query", [dict(survey="ztf", oid=ZTF_SN), dict(survey="lsst", oid=str(LSST_SN)),
                                   dict(oid=ZTF_SN), dict(survey="lsst", oid=f"{LSST_RRL[0]},{LSST_RRL[1]}")])
def test_explorer_deep_links_load(query):
    r = requests.get(f"{EXP}/", params=query, timeout=T)
    assert r.ok and "<html" in r.text[:200].lower()


@pytest.mark.offline
def test_explorer_url_helpers():
    assert am.explorer_url(ZTF_SN, "ztf") == f"{EXP}/?survey=ztf&oid={ZTF_SN}"
    assert am.explorer_url(ZTF_SN, "ztf", site="alerce") == f"https://lsst.alerce.online/object/{ZTF_SN}?survey=ztf"


# ---------------- hunter ----------------
HUN = "https://hunter-experiment.alerce.online"


@pytest.mark.live
def test_hunter_health():
    r = requests.get(f"{HUN}/api/health", timeout=T).json()
    assert r["ok"] is True and {s["survey"] for s in r["surveys"]} == {"lsst", "ztf"}


@pytest.mark.live
def test_hunter_labels_shape():
    """Claim: /api/labels -> {count, labels:[{survey, oid, label, timestamp, author}]}, timestamp %Y%m%dT%H:%M:%SZ."""
    import re
    r = requests.get(f"{HUN}/api/labels", timeout=T).json()
    assert r["count"] == len(r["labels"]) > 0
    l0 = r["labels"][0]
    assert set(l0) >= {"survey", "oid", "label", "timestamp", "author"}
    assert {l["label"] for l in r["labels"]} <= {"Candidate", "Bogus"}
    assert re.fullmatch(r"\d{8}T\d\d:\d\d:\d\dZ", l0["timestamp"])


@pytest.mark.live
def test_hunter_candidates_recipe_runs():
    """The hunter search + enrichment run end to end (anchored at the latest epoch, so a stalled stream is OK)."""
    df = am.hunter_candidates("lsst", reference_mjd=am.latest_mjd("lsst"), max_days_since_first=7,
                              max_days_since_last=2, top=20)
    assert not df.empty and (df.n_neg == 0).all() and df.class_name.eq("SN").all()
    assert df.probability.is_monotonic_decreasing


# ---------------- crossmatch ----------------
@pytest.mark.live
def test_catshtm_crossmatch():
    d = am.catshtm_crossmatch(149.92867, 0.418448, 5)
    assert d and all("_units" in v for v in d.values())


@pytest.mark.live
def test_in_db_xmatch_scales_to_samples():
    """Claim (crossmatch/index.md): the in-DB xmatch serves hundreds of objects in ONE batched TAP query, fast."""
    import time
    s = am.tap_query("SELECT TOP 300 oid FROM alerce_tap.probability WHERE sid = 0 AND ranking = 1 "
                     "AND classifier_id = 5 AND class_id = 10 ORDER BY probability DESC", maxrec=300)
    ids = ", ".join(map(str, s.oid))
    t0 = time.time()
    x = am.tap_query(f"""SELECT x.oid, a.w1mpro - a.w2mpro AS w1_w2 FROM alerce_tap.xmatch AS x
        LEFT JOIN alerce_tap.allwise AS a ON x.catid = 0 AND a.oid_catalog = x.oid_catalog
        WHERE x.sid = 0 AND x.oid IN ({ids})""", maxrec=10000, cache=False)
    assert time.time() - t0 < 30 and x.oid.nunique() > 200


@pytest.mark.offline
def test_crossmatch_docs_separate_large_and_small_samples():
    """The sample-size guidance stays at the top of crossmatch/index.md and in the router, and the per-object helpers
    carry their cost warning."""
    from conftest import skill_text
    doc = skill_text("crossmatch/index.md")
    assert doc.index("Choose by sample size") < doc.index("Sources by need")
    assert "any size" in doc and "Never loop an external per-object service" in doc
    assert "Large samples: only the in-DB" in skill_text("SKILL.md")
    for f in (am.catalog_xmatch, am.catshtm_crossmatch, am.object_xmatch):
        assert "small samples" in f.__doc__ or "large sample" in f.__doc__, f.__name__


@pytest.mark.external
def test_dust_proxy():
    """Claim: dust proxy -> {ebv_sf11, ebv_sfd98}, SF11 = 0.86 x SFD98."""
    r = requests.get("https://dust-proxy.francisco-forster.workers.dev/", params=dict(ra=149.92867, dec=0.418448),
                     timeout=T).json()
    assert r["ebv_sf11"] == pytest.approx(0.86 * r["ebv_sfd98"], rel=0.02)


@pytest.mark.external
def test_simbad_tap_with_mirrors():
    df = am.simbad_query_region(149.92867, 0.418448, 36)
    assert "main_id" in df


@pytest.mark.external
def test_catalog_xmatch_finds_quasar_redshift():
    """Claim: the explorer recipe finds the quasar in AGN catalogs with z ~ 1.48."""
    obj = am.get_object(ZTF_QSO, "ztf")
    df = am.catalog_xmatch(obj["meanra"], obj["meandec"], cache=False)
    agn = df[df.category == "agn"]
    assert not agn.empty and (agn.z.dropna() - 1.48).abs().min() < 0.05


# ---------------- science (tutorial facts the playbooks rely on) ----------------
@pytest.mark.live
def test_sn_counterpart_within_2_arcsec(ztf_sn_object):
    df = am.find_counterparts(ztf_sn_object["meanra"], ztf_sn_object["meandec"], 2.0)
    lsst = df[df.survey == "lsst"]
    assert LSST_SN in set(lsst.oid) and lsst.sep_arcsec.min() < 0.5


@pytest.mark.live
def test_sn_lsst_has_negative_detections_with_nan_mag():
    """Claim (core/ids-and-units.md): many LSST detections of SN 2026gzf have negative flux -> NaN mag."""
    lc = am.api_lightcurve(LSST_SN, "lsst").query("kind == 'det'")
    neg = lc[lc.diff_flux < 0]
    assert len(neg) > 10 and neg.diff_mag.isna().all() and neg.diff_mag_err.notna().all()


@pytest.mark.live
def test_sn_bhrf_says_stripped_envelope():
    """Claim (science/supernovae.md): BHRF classifies SN 2026gzf as SESN (Ibc)."""
    p = am.api_probabilities(ZTF_SN, "ztf", "lc_classifier_BHRF_forced_phot")
    assert p[p.ranking == 1].class_name.iloc[0] in ("SESN", "SNIbc")


@pytest.mark.live
def test_quasar_wise_colour_and_class():
    """Claims (science/agn.md): W1-W2 > 0.8 and BHRF top class QSO."""
    x = am.get_xmatch(ZTF_QSO, 0)
    assert float(x.w1_w2.dropna().iloc[0]) > 0.8
    p = am.api_probabilities(ZTF_QSO, "ztf", "lc_classifier_BHRF_forced_phot")
    assert p[p.ranking == 1].class_name.iloc[0] == "QSO"


@pytest.mark.live
def test_quasar_lsst_counterpart_exists():
    obj = am.get_object(LSST_QSO, "lsst")
    assert obj["sid"] == 1


@pytest.mark.live
def test_rrl_period_and_lsst_alias():
    """Claims (science/variable-stars.md): ZTF period 0.4889 d; LSST Multiband_period ~2x (alias)."""
    z = am.get_features(ZTF_RRL, 0, ["Multiband_period"]).feature_value.iloc[0]
    assert z == pytest.approx(0.48888, abs=1e-3)
    l = [am.get_features(o, 1, ["Multiband_period"]).feature_value for o in LSST_RRL]
    vals = [v.iloc[0] for v in l if len(v)]
    assert any(v == pytest.approx(2 * z, rel=0.01) for v in vals)


@pytest.mark.live
def test_rrl_is_split_into_two_lsst_objects():
    """Claim: the RR Lyrae has two LSST diaObjects within ~2 arcsec."""
    obj = am.get_object(ZTF_RRL, "ztf")
    df = am.find_counterparts(obj["meanra"], obj["meandec"], 2.0)
    assert set(LSST_RRL) <= set(df[df.survey == "lsst"].oid)


@pytest.mark.live
def test_rrl_bhrf_top_class():
    p = am.api_probabilities(ZTF_RRL, "ztf", "lc_classifier_BHRF_forced_phot")
    assert p[p.ranking == 1].class_name.iloc[0] in ("RRLab", "RRLc")
