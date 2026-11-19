"""Claims added or corrected after reviewing github.com/alercebroker/usecases (2026-11-19): TAP_UPLOAD, stamp
retention, solar-system objects over REST, legacy ztf.* schema, retired services, TAP naming quirks."""
import time

import numpy as np
import pandas as pd
import pytest
import requests

from conftest import API, LSST_SN, am

T = 60


# ---------------- TAP_UPLOAD (tap/index.md rule 6, tap/gotchas.md, crossmatch/index.md) ----------------
@pytest.mark.offline
def test_upload_helper_refuses_oid_column():
    with pytest.raises(ValueError, match="objectid"):
        am.tap_upload_query("SELECT 1", {"t": pd.DataFrame({"oid": [1]})})


@pytest.fixture(scope="module")
def recent_lsst():
    return am.tap_query("SELECT TOP 300 oid, meanra, meandec FROM alerce_tap.object WHERE sid = 1 "
                        "ORDER BY lastmjd DESC", maxrec=300, cache=False)


@pytest.mark.live
def test_id_upload_join_works_and_is_fast(recent_lsst):
    t0 = time.time()
    df = am.tap_upload_query("SELECT p.oid FROM alerce_tap.probability AS p JOIN tap_upload.ids AS u "
                             "ON p.oid = u.objectid WHERE p.sid = 1 AND p.ranking = 1",
                             {"ids": pd.DataFrame({"objectid": recent_lsst.oid.astype("int64")})})
    assert df.oid.nunique() > 250 and time.time() - t0 < 30


@pytest.mark.live
def test_upload_column_named_oid_fails_with_fdw_message(recent_lsst):
    """Claim (tap/gotchas.md): an uploaded column named oid gives the 'FDW upload-join is disabled' error."""
    from astropy.table import Table
    with pytest.raises(Exception, match="FDW|direct execution path"):
        am.tap_service().search("SELECT p.oid FROM alerce_tap.probability AS p JOIN tap_upload.ids AS u "
                                "ON p.oid = u.oid WHERE p.sid = 1",
                                uploads={"ids": Table({"oid": np.array(recent_lsst.oid[:10], dtype=np.int64)})})


@pytest.mark.live
def test_spatial_upload_crossmatch_is_fast(recent_lsst):
    """Claim (crossmatch/index.md): your own positions -> ALeRCE objects at any size, ~seconds per few hundred."""
    t0 = time.time()
    x = am.upload_crossmatch(recent_lsst.meanra, recent_lsst.meandec, 2.0, sid=1)
    assert time.time() - t0 < 60 and x.src.nunique() == len(recent_lsst) and (x.sid == 1).all()


# ---------------- TAP quirks ----------------
@pytest.mark.live
def test_star_join_duplicates_get_underscore_suffix():
    d = am.tap_query("SELECT TOP 1 det.*, l.* FROM alerce_tap.detection AS det JOIN alerce_tap.lsst_detection AS l "
                     "ON det.oid = l.oid AND det.sid = l.sid AND det.measurement_id = l.measurement_id "
                     f"WHERE det.oid = {LSST_SN} AND det.sid = 1", maxrec=1, cache=False)
    assert {"oid_", "sid_", "measurement_id_"} <= set(d.columns) and "psfflux" in d.columns


@pytest.mark.live
def test_quoted_oid_literals_and_distance_shorthand():
    q = am.tap_query(f"SELECT oid FROM alerce_tap.object WHERE sid = 1 AND oid IN ('{LSST_SN}')", cache=False)
    assert len(q) == 1
    q = am.tap_query("SELECT oid FROM alerce_tap.object WHERE sid = 1 AND "
                     "DISTANCE(149.92864, 0.41843, meanra, meandec) < 0.001", cache=False)
    assert LSST_SN in set(q.oid)


# ---------------- stamps retention (api/stamps.md) ----------------
@pytest.mark.live
def test_lsst_stamps_kept_for_months():
    oid = 313853496686280764  # AT 2025agtf, first detected Dec 2025
    raw = am.api_lightcurve_raw(oid, "lsst", cache=False)
    first = min((d for d in raw["detections"] if d.get("has_stamp")), key=lambda d: d["mjd"])
    assert am.now_mjd() - first["mjd"] > 250
    r = requests.get(f"{API}/stamps_api/stamp", params=dict(oid=oid, measurement_id=first["measurement_id"],
                     survey_id="lsst", stamp_type="cutoutScience", file_format="fits", is_compressed="false"),
                     timeout=T)
    assert r.ok


@pytest.mark.live
def test_ztf_stamps_beyond_first_alert():
    raw = am.api_lightcurve_raw("ZTF17aabhbva", "ztf", cache=False)
    last = max((d for d in raw["detections"] if d.get("has_stamp")), key=lambda d: d["mjd"])
    first = min(raw["detections"], key=lambda d: d["mjd"])
    assert last["mjd"] - first["mjd"] > 1000
    r = requests.get("https://avro.alerce.online/get_stamp", params=dict(oid="ZTF17aabhbva", candid=last["measurement_id"],
                     type="science", format="fits"), timeout=T)
    assert r.ok


# ---------------- solar-system objects (science/solar-system.md) ----------------
@pytest.fixture(scope="module")
def ss():
    o = am.tap_query("SELECT TOP 1 oid FROM alerce_tap.object WHERE sid = 2 ORDER BY lastmjd DESC", maxrec=1, cache=False)
    oid = int(o.oid.iloc[0])
    m = am.tap_query(f"SELECT TOP 1 measurement_id FROM alerce_tap.lsst_detection WHERE oid = {oid} AND sid = 2",
                     maxrec=1, cache=False)
    return oid, int(m.measurement_id.iloc[0])


@pytest.mark.live
def test_sid2_rest_object_404_but_stamps_work(ss):
    oid, mid = ss
    assert requests.get(f"{API}/object_api/object", params=dict(oid=oid, survey_id="lsst"), timeout=T).status_code == 404
    r = requests.get(f"{API}/stamps_api/stamp", params=dict(oid=oid, measurement_id=mid, survey_id="lsst",
                     stamp_type="cutoutScience", file_format="fits", is_compressed="false"), timeout=T)
    assert r.ok


@pytest.mark.live
def test_sid2_has_probability_rows(ss):
    p = am.tap_query(f"SELECT classifier_id FROM alerce_tap.probability WHERE oid = {ss[0]} AND sid = 2", cache=False)
    assert len(p) > 0


# ---------------- legacy schema and retired services ----------------
@pytest.mark.live
def test_legacy_ztf_schema_is_live_with_16_tables():
    t = am.tap_query("SELECT table_name FROM TAP_SCHEMA.tables WHERE schema_name = 'ztf'", cache=False)
    assert len(t) == 16, sorted(t.table_name)
    last = am.tap_query("SELECT TOP 1 lastmjd FROM ztf.object ORDER BY lastmjd DESC", maxrec=1, cache=False)
    assert am.now_mjd() - float(last.lastmjd.iloc[0]) < 30


@pytest.mark.live
def test_legacy_schema_keeps_several_classifier_generations():
    p = am.tap_query("SELECT DISTINCT classifier_name FROM ztf.probability WHERE oid = 'ZTF26aaonmha'", cache=False)
    names = set(p.classifier_name)
    assert {"lc_classifier", "lc_classifier_BHRF_forced_phot", "stamp_classifier"} <= names


@pytest.mark.live
def test_forecast_api_is_gone():
    r = requests.get("https://api.alerce.online/forecast/v1/parametric/sn", params=dict(oid="ZTF26aaonmha", mjd=61200),
                     timeout=T)
    assert r.status_code == 404, "the forecast API answers again: update api/legacy-ztf.md and science/supernovae.md"
