"""Live claims about the REST APIs: api/index.md, api/multisurvey.md, api/legacy-ztf.md, api/stamps.md."""
import gzip
import io

import numpy as np
import pytest
import requests

from conftest import API, LSST_SN, ZTF_SN, am

pytestmark = pytest.mark.live
T = 60


def get(url, **params):
    return requests.get(url, params=params, timeout=T)


# ---------------- multisurvey: object_api ----------------
def test_object_record_fields(ztf_sn_object):
    """Claim: object_api/object returns position, first/last MJD, n_det, n_forced, n_non_det; ZTF oid is the name."""
    for k in ("oid", "sid", "meanra", "meandec", "firstmjd", "lastmjd", "n_det", "n_forced", "n_non_det"):
        assert k in ztf_sn_object
    assert ztf_sn_object["oid"] == ZTF_SN and ztf_sn_object["sid"] == 0


def test_object_lsst_oid_is_integer():
    """Claim: the LSST oid comes back as an (18-digit) integer."""
    r = get(f"{API}/object_api/object", oid=LSST_SN, survey_id="lsst").json()
    assert r["oid"] == LSST_SN and r["sid"] == 1 and LSST_SN > 2 ** 53


def test_object_has_no_probabilities(ztf_sn_object):
    """Claim: probabilities are NOT in the object record."""
    assert "probability" not in ztf_sn_object and "class_name" not in ztf_sn_object


def test_object_404_shape():
    """Claim: missing object -> 404 {"detail": "Object ... not found ..."}."""
    r = get(f"{API}/object_api/object", oid=1, survey_id="lsst")
    assert r.status_code == 404 and "not found" in r.json()["detail"]


def test_survey_id_validation_422():
    """Claim: survey_id other than ztf|lsst -> 422 "Input should be 'ztf' or 'lsst'"."""
    r = get(f"{API}/object_api/object", oid=1, survey_id="atlas")
    assert r.status_code == 422 and "'ztf' or 'lsst'" in r.text


# ---------------- multisurvey: list_objects ----------------
def test_list_objects_without_survey_id_is_ztf_only():
    """Claim: without survey_id, list_objects searches ZTF only."""
    items = get(f"{API}/object_api/list_objects", page_size=20, count="false").json()["items"]
    assert items and {i["sid"] for i in items} == {0}


def test_list_objects_response_shape_and_dotted_version():
    """Claim: {next, has_next, current_page, items}; classifier_version is a dotted string here."""
    r = get(f"{API}/object_api/list_objects", survey_id="lsst", classifier="stamp_classifier_rubin_beta_20260421",
            class_name="SN", probability=0.9, page_size=3, count="false").json()
    for k in ("next", "has_next", "current_page", "items"):
        assert k in r
    assert r["items"] and all(isinstance(i["classifier_version"], str) and "." in i["classifier_version"]
                              for i in r["items"])


def test_list_objects_radius_is_arcsec_and_rows_per_classifier(ztf_sn_object):
    """Claims: list_objects radius is in ARCSEC; without `classifier` there is one row per (object, classifier)."""
    r = get(f"{API}/object_api/list_objects", survey_id="lsst", ra=ztf_sn_object["meanra"],
            dec=ztf_sn_object["meandec"], radius=3, page_size=20).json()["items"]
    oids = [i["oid"] for i in r]
    assert LSST_SN in oids, "a 3-unit radius found nothing: radius may no longer be arcsec"
    assert oids.count(LSST_SN) > 1, "no duplicate rows per classifier any more: drop the dedup advice"


def test_list_objects_helper_dedups():
    df = am.list_objects("lsst", max_pages=1, page_size=10, ra=149.92864, dec=0.41843, radius=3)
    assert df.oid.is_unique and LSST_SN in set(df.oid)


# ---------------- multisurvey: lightcurve_api ----------------
def test_lightcurve_bundle_keys(ztf_sn_bundle, lsst_sn_bundle):
    """Claim: one /lightcurve call returns detections + non_detections + forced_photometry, for both surveys."""
    for b in (ztf_sn_bundle, lsst_sn_bundle):
        assert set(b) >= {"detections", "non_detections", "forced_photometry"}
        assert b["detections"] and b["forced_photometry"]


def test_lsst_has_no_non_detections(lsst_sn_bundle):
    """Claim: LSST non_detections is always []."""
    assert lsst_sn_bundle["non_detections"] == []


def test_ztf_has_non_detections(ztf_sn_bundle):
    assert ztf_sn_bundle["non_detections"] and "diffmaglim" in ztf_sn_bundle["non_detections"][0]


@pytest.mark.parametrize("field", ["band", "band_map", "mjd", "measurement_id", "psfFlux", "psfFluxErr",
                                   "scienceFlux", "scienceFluxErr", "reliability", "has_stamp", "isNegative", "snr"])
def test_lsst_detection_fields(lsst_sn_bundle, field):
    """Claim (api/multisurvey.md): LSST detection rows carry these camelCase fields."""
    assert field in lsst_sn_bundle["detections"][0]


@pytest.mark.parametrize("field", ["band", "band_map", "mjd", "measurement_id", "pid", "isdiffpos", "magpsf",
                                   "sigmapsf", "magpsf_corr", "sigmapsf_corr_ext", "corrected", "rb", "drb",
                                   "distnr", "diffmaglim", "has_stamp"])
def test_ztf_detection_fields(ztf_sn_bundle, field):
    assert field in ztf_sn_bundle["detections"][0]


@pytest.mark.parametrize("field", ["mag", "e_mag", "mag_corr", "e_mag_corr", "e_mag_corr_ext", "isdiffpos",
                                   "corrected", "field", "rcid", "magzpsci", "diffmaglim"])
def test_ztf_forced_fields(ztf_sn_bundle, field):
    assert field in ztf_sn_bundle["forced_photometry"][0]


def test_lightcurve_multi_oid_drops_missing():
    """Claim: with several oids, missing ones are silently left out (no 404)."""
    r = requests.get(f"{API}/lightcurve_api/detections", params=[("survey_id", "ztf"), ("oid", ZTF_SN),
                                                                  ("oid", "ZTF99zzzzzzz")], timeout=T)
    assert r.status_code == 200 and {d["oid"] for d in r.json()} == {ZTF_SN}


def test_conesearch_radius_is_degrees_and_covers_both_surveys(ztf_sn_object):
    """Claim: conesearch/objects_by_coordinates takes radius in DEGREES and returns both surveys."""
    r = get(f"{API}/lightcurve_api/conesearch/objects_by_coordinates", ra=ztf_sn_object["meanra"],
            dec=ztf_sn_object["meandec"], radius=2 / 3600, neighbors=10).json()
    assert {x["survey_id"] for x in r} == {"ztf", "lsst"}
    assert {"objectId", "survey_id", "ra", "dec"} <= set(r[0])


# ---------------- multisurvey: probability / classifier / magstat / crossmatch ----------------
def test_probability_version_is_int_of_digits(luts):
    """Claim: probability_api classifier_version is an int of the dotted version's digits (2.0.2 -> 202)."""
    rows = get(f"{API}/probability_api/probability", oid=LSST_SN, survey_id="lsst").json()
    assert isinstance(rows, list) and rows
    dotted = dict(zip(luts["classifier"].classifier_name, luts["classifier"].classifier_version))
    for r in rows:
        assert isinstance(r["classifier_version"], int)
        if r["classifier_name"] in dotted:
            assert str(r["classifier_version"]) == dotted[r["classifier_name"]].replace(".", "")


def test_classifier_api_shape():
    rows = get(f"{API}/classifier_api/classifiers", survey_id="lsst").json()
    assert {"classifier_name", "classifier_version", "classes", "classifier_id", "survey_id"} <= set(rows[0])


def test_magstats_ztf_per_band():
    """Claim: magstat_api returns per-band stats for ZTF (band, ndet, magmean, magmin, ...)."""
    rows = get(f"{API}/magstat_api/magstats", oid=ZTF_SN, survey_id="ztf").json()
    assert {r["band"] for r in rows} <= {1, 2, 3} and {"ndet", "magmean", "magmin", "corrected"} <= set(rows[0])


def test_magstats_lsst_is_dia_object_summary():
    """Claim (corrected): for LSST, magstat_api returns ONE row of per-band diaObject flux summaries (nJy)."""
    rows = get(f"{API}/magstat_api/magstats", oid=LSST_SN, survey_id="lsst").json()
    assert len(rows) == 1 and "g_psfFluxMean" in rows[0] and "band" not in rows[0]


def test_crossmatch_api_shape():
    """Claim: crossmatch_api returns [{catalog: {col: {unit, value}}}]."""
    rows = get(f"{API}/crossmatch_api/crossmatch", oid=ZTF_SN, survey_id="ztf").json()
    (cat, cols), = rows[0].items()
    col = next(iter(cols.values()))
    assert set(col) == {"unit", "value"}


# ---------------- stamps (api/stamps.md) ----------------
def _first_stamp(bundle):
    return next(d["measurement_id"] for d in bundle["detections"] if d.get("has_stamp"))


def test_ztf_stamp_is_gzip_fits_63px_without_wcs(ztf_sn_bundle):
    """Claims: avro.alerce.online stamps are gzip FITS, 63x63, no WCS."""
    from astropy.io import fits
    r = get("https://avro.alerce.online/get_stamp", oid=ZTF_SN, candid=_first_stamp(ztf_sn_bundle),
            type="science", format="fits")
    assert r.ok and r.content[:2] == b"\x1f\x8b"
    h = fits.open(io.BytesIO(gzip.decompress(r.content)))[0]
    assert h.data.shape == (63, 63)
    assert "CD1_1" not in h.header and "CTYPE1" not in h.header


def test_lsst_stamp_fits_with_wcs(lsst_sn_bundle):
    """Claims: LSST stamps_api returns FITS with a WCS (CD matrix), rotated, 0.2"/pix, variable size."""
    from astropy.io import fits
    r = get(f"{API}/stamps_api/stamp", oid=LSST_SN, measurement_id=_first_stamp(lsst_sn_bundle),
            survey_id="lsst", stamp_type="cutoutScience", file_format="fits", is_compressed="false")
    assert r.ok
    content = gzip.decompress(r.content) if r.content[:2] == b"\x1f\x8b" else r.content
    h = fits.open(io.BytesIO(content))[0].header
    cd = am._cd_matrix(h)
    assert cd is not None
    scale = np.sqrt(abs(np.linalg.det(cd))) * 3600
    assert scale == pytest.approx(0.2, abs=0.02)


def test_lsst_stamps_avro_400(lsst_sn_bundle):
    """Claim: /stamps_api/avro returns 400 for LSST."""
    r = get(f"{API}/stamps_api/avro", oid=LSST_SN, measurement_id=_first_stamp(lsst_sn_bundle), survey_id="lsst")
    assert r.status_code == 400


# ---------------- legacy ZTF API (api/legacy-ztf.md) ----------------
L = "https://api.alerce.online/ztf/v1"


def test_legacy_bare_path_308():
    """Claim: bare paths answer 308 to the trailing-slash form."""
    r = requests.get(f"{L}/objects", params=dict(oid=ZTF_SN), timeout=T, allow_redirects=False)
    assert r.status_code == 308 and r.headers["location"].split("?")[0].endswith("/objects/")


def test_legacy_ndethist_is_string():
    """Claim: legacy object record has ndethist as a STRING."""
    r = get(f"{L}/objects/{ZTF_SN}").json()
    assert isinstance(r["ndethist"], str) and "ndet" in r


def test_legacy_dotted_version_filter_returns_nothing():
    """Claim (corrected): a dotted classifier_version (1.0.4) silently returns 0 rows; only the legacy
    spelling (stamp_classifier_1.0.4) matches."""
    p = dict(oid=ZTF_SN, classifier="stamp_classifier", page_size=5)
    assert len(get(f"{L}/objects/", **p, classifier_version="1.0.4").json()["items"]) == 0
    assert len(get(f"{L}/objects/", **p, classifier_version="stamp_classifier_1.0.4").json()["items"]) == 1


def test_legacy_features_all_versions():
    """Claim: /features is a flat [{name, value, fid, version}] list over several extractor versions."""
    rows = get(f"{L}/objects/{ZTF_SN}/features").json()
    assert {"name", "value", "fid", "version"} <= set(rows[0])
    assert len({r["version"] for r in rows}) > 1


def test_legacy_v2_lightcurve_has_forced():
    r = get(f"https://api.alerce.online/v2/lightcurve/lightcurve/{ZTF_SN}", survey_id="ztf").json()
    assert "forced_photometry" in r and "e_mag_corr_ext" in r["forced_photometry"][0]


def test_ztf_dr_light_curve_shape(ztf_sn_object):
    """Claim: ZTF DR API -> list of {filterid, fieldid, rcid, nepochs, hmjd[], mag[], magerr[]}; radius arcsec."""
    rows = get("https://api.alerce.online/ztf/dr/v1/light_curve/", ra=ztf_sn_object["meanra"],
               dec=ztf_sn_object["meandec"], radius=1.5).json()
    assert rows and {"filterid", "fieldid", "rcid", "nepochs", "hmjd", "mag", "magerr"} <= set(rows[0])
    assert {r["filterid"] for r in rows} <= {1, 2, 3}


def test_tns_bridge_returns_html_cells(ztf_sn_object):
    """Claim: TNS bridge returns HTML with id="type"/"name"/"redshift" cells."""
    r = get("https://api.alerce.online/v2/object_details/htmx/tns/", ra=ztf_sn_object["meanra"],
            dec=ztf_sn_object["meandec"])
    assert r.ok and "<" in r.text[:50]
    for cell in ('id="type"', 'id="name"', 'id="redshift"'):
        assert cell in r.text


def test_avro_info_ztf(ztf_sn_bundle):
    """Claim: get_avro_info returns {candidate, objectId, prv_candidates, ...} with xpos/ypos."""
    r = get("https://avro.alerce.online/get_avro_info", oid=ZTF_SN, candid=_first_stamp(ztf_sn_bundle)).json()
    assert {"candidate", "objectId", "prv_candidates"} <= set(r)
    assert {"xpos", "ypos"} <= set(r["candidate"])


# ---------------- multisurvey: features_api (found 2026-11-19) ----------------
def test_features_api_both_surveys():
    """Claim (api/multisurvey.md): features_api/features serves [{name, value, band, version}] for ZTF and LSST."""
    for oid, s in ((ZTF_SN, "ztf"), (LSST_SN, "lsst")):
        rows = get(f"{API}/features_api/features", oid=oid, survey_id=s).json()
        assert rows and set(rows[0]) == {"name", "value", "band", "version"}


def test_features_api_matches_tap():
    """REST and TAP give the same Multiband_period for the RR Lyrae (band 12)."""
    rest = am.api_features("ZTF17aabhbva", "ztf", "Multiband_period")
    tap = am.get_features("ZTF17aabhbva", 0, ["Multiband_period"])
    assert rest.band.iloc[0] == 12 and rest.band_name.iloc[0] == "gr"
    assert rest.value.iloc[0] == pytest.approx(tap.feature_value.iloc[0], rel=1e-6)
