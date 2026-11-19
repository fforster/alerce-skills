"""Claims about the official Python client (client/index.md, client/reference.md)."""
import inspect
import warnings

import pytest
import requests

from conftest import LSST_QSO, LSST_SN, ZTF_QSO, ZTF_SN
from snapshot import check_snapshot

alerce_core = pytest.importorskip("alerce.core")
import alerce  # noqa: E402
from alerce import exceptions as aex  # noqa: E402

DOC_VERSION = "2.4.0"


@pytest.fixture(scope="module")
def ms():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return alerce_core.Alerce(ztf_backend="multisurvey")


@pytest.fixture(scope="module")
def legacy():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return alerce_core.Alerce()


# ---------------- offline: construction, dispatch, structure ----------------
@pytest.mark.offline
def test_installed_version_is_documented():
    from importlib.metadata import version
    assert version("alerce") == DOC_VERSION, "client version changed: re-explore and update client/*.md"


@pytest.mark.offline
def test_backend_validation():
    with pytest.raises(ValueError, match="ztf_backend"):
        alerce_core.Alerce(ztf_backend="nope")


@pytest.mark.offline
def test_survey_validation(ms):
    with pytest.raises(ValueError, match="survey must be one of"):
        ms.query_object("x", survey="atlas")


@pytest.mark.offline
def test_documented_sub_clients_have_sessions(ms):
    """reference.md's retry snippet relies on these attributes."""
    for name in ("multisurvey_client", "legacy_ztf_client", "multisurvey_stamps_client", "legacy_stamps_client"):
        assert isinstance(getattr(ms, name).session, requests.Session), name
    assert isinstance(ms.session, requests.Session)


@pytest.mark.offline
def test_exception_hierarchy():
    assert issubclass(aex.ParseError, aex.APIError) and issubclass(aex.ObjectNotFoundError, aex.APIError)
    assert not issubclass(aex.CandidError, aex.APIError)


@pytest.mark.offline
def test_no_load_config_from_file():
    assert not hasattr(alerce_core.Alerce, "load_config_from_file")
    assert hasattr(alerce_core.Alerce, "load_config_from_object")


@pytest.mark.offline
def test_query_objects_defaults_to_pandas_others_to_json():
    sig = lambda m: inspect.signature(getattr(alerce_core.Alerce, m)).parameters["format"].default
    assert sig("query_objects") == "pandas"
    assert sig("query_object") == sig("query_lightcurve") == "json"


@pytest.mark.offline
def test_unknown_kwarg_rejected_on_multisurvey(ms):
    with pytest.raises(ValueError, match="Invalid parameter: foo"):
        ms.query_objects(survey="lsst", foo=1)


@pytest.mark.drift
@pytest.mark.offline
def test_snapshot_public_api(update_baselines):
    methods = {n: str(inspect.signature(f)) for n, f in inspect.getmembers(alerce_core.Alerce, inspect.isfunction)
               if not n.startswith("_")}
    check_snapshot("client_public_api", methods, update_baselines)


@pytest.mark.drift
@pytest.mark.live
def test_documented_version_is_latest_on_pypi():
    latest = requests.get("https://pypi.org/pypi/alerce/json", timeout=30).json()["info"]["version"]
    assert latest == DOC_VERSION, f"alerce {latest} released: re-explore the client and update client/*.md"


# ---------------- live claims ----------------
@pytest.mark.live
def test_ms_query_objects_one_row_per_classifier(ms):
    df = ms.query_objects(survey="lsst", ra=149.92867, dec=0.418448, radius=5)
    assert LSST_SN in set(df.oid) and (df.oid == LSST_SN).sum() > 1


@pytest.mark.live
def test_ms_count_total_is_dropped(ms):
    r = ms.query_objects(survey="lsst", ra=149.92867, dec=0.418448, radius=5, count=True, format="json")
    assert isinstance(r, list)  # items only, no {"total": ...}


@pytest.mark.live
def test_legacy_count_total_available(legacy):
    r = legacy.query_objects(survey="ztf", oid=[ZTF_SN], count=True, format="json")
    assert isinstance(r, dict) and "total" in r and "items" in r


@pytest.mark.live
def test_lsst_ids_keep_precision(ms):
    o = ms.query_object(LSST_SN, survey="lsst")
    det = ms.query_detections(LSST_SN, survey="lsst", format="pandas")
    assert o["oid"] == LSST_SN and int(det.oid.iloc[0]) == LSST_SN and "band_name" in det


@pytest.mark.live
def test_legacy_candid_is_string(legacy):
    det = legacy.query_detections(ZTF_SN, survey="ztf", format="json")
    assert isinstance(det[0]["candid"], str)


@pytest.mark.live
def test_ms_probability_version_is_int(ms):
    p = ms.query_probabilities(LSST_SN, survey="lsst", format="json")
    assert all(isinstance(r["classifier_version"], int) for r in p)


@pytest.mark.live
def test_classifier_catalogues_differ_by_backend(ms, legacy):
    leg = {c["classifier_name"] for c in legacy.query_classifiers(survey="ztf")}
    msz = {c["classifier_name"] for c in ms.query_classifiers(survey="ztf")}
    assert "lc_classifier" in leg and "lc_classifier" not in msz and "lc_classifier_BHRF_forced_phot" in msz
    with pytest.raises(aex.ParseError, match="not found"):
        ms.query_objects(survey="ztf", classifier="lc_classifier", page_size=1)


@pytest.mark.live
def test_ms_features_raw_band(ms):
    fe = ms.query_features(LSST_QSO, survey="lsst", format="pandas")
    assert {"name", "value", "band", "version"} <= set(fe.columns) and "band_name" not in fe


@pytest.mark.live
def test_stamp_return_types_differ(ms, legacy, lsst_sn_bundle):
    mid = next(d["measurement_id"] for d in lsst_sn_bundle["detections"] if d.get("has_stamp"))
    st = ms.get_stamps(LSST_SN, measurement_id=mid, survey="lsst")
    assert set(st) == {"cutoutScience", "cutoutTemplate", "cutoutDifference"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hd = legacy.get_stamps(ZTF_SN, candid=3431211435315015003, survey="ztf")
    assert len(hd) == 3 and hd[0].data.shape == (63, 63)


@pytest.mark.live
def test_lsst_avro_not_served(ms, lsst_sn_bundle):
    mid = lsst_sn_bundle["detections"][0]["measurement_id"]
    b = ms.get_avro(LSST_SN, candid=mid, survey="lsst")
    assert isinstance(b, (bytes, bytearray)) and b"isn't available" in b


@pytest.mark.live
def test_missing_object_raises_not_found(ms):
    with pytest.raises(aex.ObjectNotFoundError):
        ms.query_object(1, survey="lsst")


@pytest.mark.live
def test_catshtm_redshift(ms):
    z = ms.catshtm_redshift(149.92867, 0.418448, 10)
    assert z is None or 0 < z < 1
