"""Live claims about TAP: tap/index.md, tap/schema.md, tap/recipes.md, tap/gotchas.md."""
import numpy as np
import pytest
import requests

from conftest import LSST_SN, TAP_SYNC, ZTF_QSO, ZTF_SN, ZTF_SN_OID, am

pytestmark = pytest.mark.live


def cols_of(tap_columns_live, table):
    return set(tap_columns_live[tap_columns_live.table_name == f"alerce_tap.{table}"].column_name)


def test_31_tables(tap_tables_live):
    """Claim: schema alerce_tap has 31 tables."""
    assert len(tap_tables_live) == 31


def test_sid_lut(luts):
    """Claim: sid 0 = ZTF, 1 = LSST DIA object, 2 = LSST SS object."""
    m = dict(zip(luts["sid"].sid, luts["sid"].survey_name))
    assert m[0] == "ZTF" and "DIA" in m[1] and "SS" in m[2]


def test_band_lut(luts):
    """Claim: ZTF 1 g 2 r 3 i; LSST 6 u 1 g 2 r 3 i 4 z 5 y with u first in band_order."""
    b = luts["band"]
    assert dict(zip(b[b.sid == 0].band, b[b.sid == 0].band_name)) == {1: "g", 2: "r", 3: "i"}
    lsst = b[b.sid == 1].sort_values("band_order")
    assert list(lsst.band_name) == list("ugrizy") and list(lsst.band) == [6, 1, 2, 3, 4, 5]


def test_rest_band_map_matches_lut(luts, lsst_sn_bundle, ztf_sn_bundle):
    """Claim: REST band_map agrees with the TAP band LUT."""
    for bundle, sid in ((lsst_sn_bundle, 1), (ztf_sn_bundle, 0)):
        b = luts["band"][luts["band"].sid == sid]
        assert {int(k): v for k, v in bundle["detections"][0]["band_map"].items()} == dict(zip(b.band, b.band_name))


def test_feature_value_not_value(tap_columns_live):
    """Claim: the feature column is feature_value (value is reserved)."""
    c = cols_of(tap_columns_live, "feature")
    assert "feature_value" in c and "value" not in c


def test_ztf_extension_tables_have_no_sid(tap_columns_live):
    """Claim: ztf_* tables have no sid column; lsst_detection/forced have sid."""
    for t in ("ztf_detection", "ztf_forced_photometry", "ztf_non_detection", "ztf_object", "ztf_ps1"):
        assert "sid" not in cols_of(tap_columns_live, t), t
    for t in ("lsst_detection", "lsst_forced_photometry"):
        assert "sid" in cols_of(tap_columns_live, t), t


def test_probability_version_int_vs_classifier_text(tap_columns_live):
    """Claim: probability.classifier_version is a small int; classifier.classifier_version is text."""
    c = tap_columns_live.set_index(["table_name", "column_name"]).datatype
    assert "short" in c[("alerce_tap.probability", "classifier_version")] or \
        "int" in c[("alerce_tap.probability", "classifier_version")]
    assert "char" in c[("alerce_tap.classifier", "classifier_version")]


def test_taxonomy_order_column(tap_columns_live):
    assert "taxonomy_order" in cols_of(tap_columns_live, "taxonomy")


def test_magstat_has_no_lsst_rows():
    """Claim: TAP magstat holds ZTF rows only (checked on the guiding LSST object)."""
    assert am.tap_query(f"SELECT oid FROM alerce_tap.magstat WHERE oid = {LSST_SN} AND sid = 1").empty
    assert not am.tap_query(f"SELECT oid FROM alerce_tap.magstat WHERE oid = {ZTF_SN_OID} AND sid = 0").empty


def test_lsst_ss_object_empty():
    """Claim: lsst_ss_object is currently empty (fails when it gets filled: update the docs)."""
    assert am.tap_query("SELECT TOP 1 oid FROM alerce_tap.lsst_ss_object").empty


def test_ztf_non_detections_only_in_ztf_table(tap_tables_live):
    """Claim: there is no LSST non-detection table."""
    names = set(tap_tables_live.table_name)
    assert "alerce_tap.ztf_non_detection" in names
    assert not [n for n in names if n.startswith("alerce_tap.lsst") and "non_det" in n]


def test_errors_are_votable_xml_even_for_json():
    """Claim: /tap/sync errors come back as VOTable XML even with FORMAT=json."""
    r = requests.get(TAP_SYNC, params=dict(REQUEST="doQuery", LANG="ADQL", FORMAT="json",
                                           QUERY="SELECT nonsense FROM alerce_tap.nothere"), timeout=60)
    assert not r.ok and "xml" in r.headers.get("content-type", "") and "VOTABLE" in r.text


def test_empty_in_list_is_syntax_error():
    """Claim: `IN ()` is an ADQL syntax error (guard empty oid lists)."""
    with pytest.raises(Exception):
        am.tap_query("SELECT oid FROM alerce_tap.object WHERE oid IN ()", cache=False)


def test_maxrec_truncates_without_error():
    """Claim (tap/gotchas.md): results are cut at maxrec WITHOUT an error. DaCHS returns maxrec+1 rows as an
    overflow marker; pyvo only emits a DALOverflowWarning; raw /sync gives no sign at all beyond the row count."""
    from pyvo.dal.exceptions import DALOverflowWarning
    with pytest.warns(DALOverflowWarning):
        t = am.tap_service().search("SELECT TOP 50 oid FROM alerce_tap.detection WHERE sid = 1 "
                                    f"AND oid = {LSST_SN}", maxrec=5).to_table()
    assert len(t) == 6
    r = requests.get(TAP_SYNC, params=dict(REQUEST="doQuery", LANG="ADQL", FORMAT="csv", MAXREC=5,
                                           QUERY=f"SELECT TOP 50 oid FROM alerce_tap.detection WHERE oid = {LSST_SN}"),
                     timeout=60)
    assert r.ok and len(r.text.strip().splitlines()) - 1 in (5, 6)


# ---- recipes (tap/recipes.md) ----
def test_cone_recipe_finds_both_surveys(ztf_sn_object):
    df = am.tap_cone(ztf_sn_object["meanra"], ztf_sn_object["meandec"], 2.0)
    assert {0, 1} <= set(df.sid) and df.sep_arcsec.max() < 2


def test_tap_and_rest_light_curves_agree():
    """Claim: get_lightcurve (TAP) and api_lightcurve (REST) give the same points and fluxes."""
    for oid, sid, s in ((ZTF_SN, 0, "ztf"), (LSST_SN, 1, "lsst")):
        t, r = am.get_lightcurve(oid, sid), am.api_lightcurve(oid, s)
        m = t.merge(r, on=["measurement_id", "kind"], suffixes=("_t", "_r"))
        assert len(m) == len(t) == len(r)
        for c in ("diff_flux", "sci_flux"):
            assert np.allclose(m[c + "_t"], m[c + "_r"], rtol=1e-4, equal_nan=True), (s, c)


def test_ztf_non_detection_recipe():
    df = am.get_ztf_non_detections(ZTF_SN)
    assert len(df) > 0 and df.diffmaglim.between(15, 23).all()


def test_xmatch_left_join_recipe_and_inner_join_pitfall():
    """Claims: LEFT JOIN recipe returns the AllWISE row; an inner join to both catalogs returns 0 rows."""
    df = am.get_xmatch(ZTF_QSO, 0)
    assert not df.empty and (df.catalog_name == "AllWISE").any()
    inner = am.tap_query(f"""SELECT x.oid FROM alerce_tap.xmatch x
        JOIN alerce_tap.allwise a ON a.oid_catalog = x.oid_catalog
        JOIN alerce_tap.gaiadr3_source g ON g.oid_catalog = x.oid_catalog
        WHERE x.oid = {am.ztf_name_to_oid(ZTF_QSO)} AND x.sid = 0""")
    assert inner.empty


def test_catalog_id_lut(luts):
    """Claim: catid 0 = AllWISE, 1 = Gaia DR3 (resolve by name; this documents the current mapping)."""
    m = dict(zip(luts["catalog"].catid, luts["catalog"].catalog_name))
    assert "allwise" in m[0].lower() and "gaia" in m[1].lower()


def test_feature_ids_differ_per_survey():
    """Claim: feature ids differ between surveys (always look up by sid)."""
    z, l = am.feature_ids(0, ["Multiband_period", "GP_DRW_tau", "SPM_A"]), am.feature_ids(1, ["Multiband_period",
                                                                                            "GP_DRW_tau", "SPM_A"])
    assert set(z) == set(l) and z != l


def test_multiband_period_band_codes():
    """Claim: ZTF Multiband_period uses band 12, LSST band 0."""
    z = am.get_features("ZTF17aabhbva", 0, ["Multiband_period"])
    l = am.get_features(313888627082919999, 1, ["Multiband_period"])
    assert set(z.band) == {12} and set(l.band) == {0}


def test_latest_mjd_is_cheap_and_recent():
    import time
    t0 = time.time()
    last = am.latest_mjd("ztf")
    assert time.time() - t0 < 30 and am.now_mjd() - last < 30, "ZTF data older than 30 days?"
