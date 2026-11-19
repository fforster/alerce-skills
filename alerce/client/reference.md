# `alerce` 2.4.0: full reference

Source read in full and every public method exercised live on 2026-11-19 (Python 3.13, pandas 3.1, astropy 8.0). Requires Python ≥ 3.10 and pandas, astropy, requests, ipython, matplotlib.

## Architecture
- `Alerce(ztf_backend="legacy"|"multisurvey")` combines search (`AlerceCommonSearch`), catsHTM (`AlerceXmatch`) and stamps (`AlerceCommonStamps`). Any other backend raises `ValueError("ztf_backend must be one of ('legacy', 'multisurvey')")`.
- **Dispatch** happens per call:
  - `survey=None` → `"ztf"`, with a DeprecationWarning that is invisible by default (`stacklevel=1`).
  - `"ztf"` + legacy → `ZTFSearch`/`AlerceStamps`.
  - `"ztf"` + multisurvey, or `"lsst"` → `AlerceSearchMultiSurvey`/`AlerceStampsMultisurvey`.
  - Anything else raises `ValueError("survey must be one of ['ztf', 'lsst']")`.
- The `FutureWarning` about the default backend fires once per process.
- **HTTP**: one `requests.Session` per sub-client, **no timeout, no retries** (`Retry(total=0)`).
- **Errors** (`alerce.exceptions`):
  - 400 → `ParseError`, 404 → `ObjectNotFoundError`, other ≥ 400 → `APIError`; all subclass `APIError`.
  - Message = response `detail`; `.data` = the errors.
  - `FormatValidationError` is raised for formats outside `pandas, votable, json, csv`.
  - `CandidError` ("Object has no stamps.") is a plain `Exception`.
- **Config**:
  - `$ALERCE_CONFIG_PATH` replaces the packaged `default_config.json` **whole**; partial files are not merged.
  - Sections: `multisurvey`, `ztf`, `stamps`, `stamps_ztf`.
  - `Alerce.load_config_from_object(dict)` only changes catsHTM. To retarget others: `c.legacy_ztf_client.load_config_from_object(...)`, `c.multisurvey_client…`.
  - There is no `load_config_from_file`.
- `compat.py` (`to_legacy`, `decode_ztf_oid`) is shipped but unused.

## Methods
Legacy ZTF base `https://api.alerce.online`; multisurvey (MS) base `https://api-lsst.alerce.online/`.

| method | legacy ZTF endpoint | MS endpoint (LSST, or ZTF with `ztf_backend="multisurvey"`) | returns / notes |
|---|---|---|---|
| `query_objects(format="pandas", index=None, sort=None, survey=None, **kw)` | `/ztf/v1/objects`; `class_name`→`class`; kwargs unvalidated | `object_api/list_objects`; whitelist `oid, survey, classifier, class_name, ranking, n_det, probability, firstmjd, lastmjd, ra, dec, radius, page, page_size, count, order_by, order_mode`; `ndet`→`n_det`, `order_by` `ndet`/`deltajd` → `n_det`/`deltamjd` (DeprecationWarning) | MS returns items only (`total`, `has_next` dropped); legacy json returns the page dict |
| `query_object(oid, format="json", survey=None, return_survey_extra=True)` | `/ztf/v1/objects/{oid}` | `object_api/object` | dict; `votable` fails (`TypeError`) |
| `query_lightcurve(oid, format="json", survey=None)` | `/ztf/v1/objects/{oid}/lightcurve` | `lightcurve_api/lightcurve` | dict; use json only (pandas → 1 row of lists; votable → `ValueError: Inconsistent data column lengths`) |
| `query_detections(oid, format, survey, index, sort)` | `/ztf/v1/objects/{oid}/detections` | `lightcurve_api/detections` | list/DataFrame; MS adds `band_name`, drops `band_map`; legacy `candid` is a str |
| `query_non_detections(...)` | `…/non_detections` | `lightcurve_api/non_detections` | LSST: empty |
| `query_forced_photometry(...)` | `/v2/lightcurve/forced-photometry/{oid}` (flattens `extra_fields`) | `lightcurve_api/forced-photometry` | |
| `query_magstats(...)` | `…/magstats` (per `fid`) | `magstat_api/magstats` (ZTF per band; LSST one row of flux statistics) | MS new in 2.4.0 |
| `query_probabilities(...)` | `…/probabilities` (all versions) | `probability_api/probability` (`classifier_version` int, 202) | |
| `query_features(...)` / `query_feature(oid, name, …)` | `…/features[/{name}]` (all versions, `fid`) | `features_api/features[?name=]` (`band` raw int) | MS new in 2.4.0 |
| `query_classifiers(format, survey)` | `/ztf/v1/classifiers` (15) | `classifier_api/classifiers` (LSST 3, ZTF-MS 7) | |
| `query_classes(classifier_name, classifier_version, …)` | `/ztf/v1/classifiers/{name}/{version}/classes` (version like `hierarchical_random_forest_1.0.0`) | `classifier_api/classes` | wrong version → `ObjectNotFoundError` |
| `get_stamps(oid, candid=None, measurement_id=None, include_variance_and_psf=False, format="HDUList", survey=None)` | `avro.alerce.online/get_stamp?…&format=fits` ×3, gunzipped → `HDUList` | `stamps_api/stamp?…&file_format=fits` ×3 → dict `{cutoutScience, cutoutTemplate, cutoutDifference}` of `PrimaryHDU` | `format="numpy"` gives a list of 3 arrays; `candid=None` uses the first detection with a stamp; MS `include_variance_and_psf=True` gives HDULists (`PRIMARY`, `UNCERT`, `PSFIMAGE`) but crashes with numpy |
| `get_avro(oid, candid=None, survey=None)` | `avro.alerce.online/get_avro` → Avro bytes | `stamps_api/avro` → LSST error JSON; ZTF-MS JSON | **no status check**: error bodies come back as bytes |
| `plot_stamps(oid, candid=None, measurement_id=None, survey=None)` | IPython `<img>` (PNG) | matplotlib, 3 PNGs | notebooks only; otherwise `None` + RuntimeWarning |
| `catshtm_conesearch(ra, dec, radius_arcsec, catalog_name="all", format="pandas")` | `catshtm.alerce.online/conesearch[_all]` | – | single-row results collapse to a pandas `Series`; `all` → dict |
| `catshtm_crossmatch(ra, dec, radius_arcsec, catalog_name="all", format="pandas")` | `…/crossmatch[_all]` | – | dict catalog → Series (adds `distance`) |
| `catshtm_redshift(ra, dec, radius, format=…, verbose=False)` | `…/crossmatch_all` | – | first `z`, then `zphot`/`z_phot`, else None; `format` ignored |
| `catshtm_catalog_translator(name)` | – | – | `2MASS`→`TMASS`, `GAIA/DR2`→`GAIADR2`, … |

## Precision and types
- LSST ids stay exact (int / int64) in json, pandas and votable. ZTF-MS `measurement_id` is int64.
- Legacy ZTF `candid` is a **string**.
- LSST `band` ints map `1 g, 2 r, 3 i, 4 z, 5 y, 6 u`. `band_name` is added for detections, forced photometry and non-detections, not for features or magstats.
- Under pandas 3, `index=`/`sort=` emit a `Pandas4Warning` (`inplace=True`).

## Bugs and quirks (2.4.0)
- MS `query_objects` gives one row per classifier (2 LSST objects → 4 rows; 1 ZTF object → 7 rows).
- MS `count=True` total is discarded.
- No timeout: the unfiltered legacy search took 42 s; LSST `firstmjd=[a, b]` returned `APIError {'Error code': 504, 'Message': 'Query timed out'}` after 55 s.
- Legacy stamp `except urllib.error.HTTPError` blocks are dead code; bad ids give `gzip.BadGzipFile`.
- The README quickstart uses `class_name="SN"` with `lc_classifier`. That classifier's classes are `SNIa`/`SNIbc`/`SNII`/`SLSN`; `SN` belongs to the stamp classifiers.
- catsHTM: a `format="json"` request silently returns an astropy Table; an unknown catalog → `APIError 500 'Unknown API error.'`; a tiny radius → `None`.
- Legacy `plot_stamps` uses IPython's `display` without importing it.

## Adding a timeout and retries yourself
```python
import functools, requests
from requests.adapters import HTTPAdapter, Retry
c = Alerce(ztf_backend="multisurvey")
for sub in (c.multisurvey_client, c.legacy_ztf_client,                 # search
            c.multisurvey_stamps_client, c.legacy_stamps_client, c):   # stamps; c itself = catsHTM
    s = sub.session
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=4, backoff_factor=2, status_forcelist=[429, 502, 503, 504])))
    s.request = functools.partial(s.request, timeout=60)
```

## Changes from 2.3.1 (diff of the two sdists; no changelog shipped)
- New `ztf_backend=` with its FutureWarning. ZTF through the multisurvey API used to raise `NotImplementedError`.
- MS `query_magstats`, `query_features`, `query_feature`, `query_classifiers` and `query_classes` are implemented.
- `ndet`→`n_det` and `order_by` aliases; `query_object(return_survey_extra=True)`.
- **Breaking**: `get_avro(use_multisurvey_api=…)` was removed (dispatch is by survey); the MS Avro route moved to `/avro`.
- ZTF double-gzip stamp fix; `get_stamps` forwards `format` on MS.
