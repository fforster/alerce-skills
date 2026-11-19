# ALeRCE Python client (`pip install alerce`), v2.4.0 (2026-11-05)

The official client wraps the REST APIs, ZTF/LSST stamps and catsHTM. Use it when the user wants or already uses `alerce.core.Alerce`, for quick per-object retrieval, stamps as FITS, or catsHTM. For TAP, features over samples, deduplicated searches, paging totals, timeouts or retries, use the bundled `alerce_ms.py` or direct REST/TAP. Full inventory: `reference.md`.

## Pick the backend explicitly
```python
from alerce.core import Alerce
c = Alerce(ztf_backend="multisurvey")   # recommended: ZTF and LSST via api-lsst.alerce.online, one schema
z = Alerce()                            # default "legacy": ZTF via api.alerce.online/ztf/v1 (FutureWarning: default will change)
```

| | `ztf_backend="legacy"` (default) | `ztf_backend="multisurvey"` |
|---|---|---|
| ZTF endpoints | `api.alerce.online/ztf/v1`, `avro.alerce.online` | `api-lsst.alerce.online/<name>_api` (same as LSST) |
| ZTF classifiers | legacy catalogue: `lc_classifier` (15 classes), `stamp_classifier`, ATAT/BHRF `(beta)` | `lc_classifier_BHRF_forced_phot*` 2.2.0, `stamp_classifier` 1.0.4, `stamp_classifier_2025_beta` 2.1.1 |
| field names | `ndet`, `deltajd`, `fid`, `candid` (**string**) | `n_det`, `deltamjd`, `band` + `band_name`, `measurement_id` (int64) |
| extras | `count=True` totals (json only), real Avro bytes, all feature versions | unified light curve with forced photometry |

LSST always uses the multisurvey API, whatever the backend. **Always pass `survey="ztf"|"lsst"`.** Omitting it defaults to ZTF, and the DeprecationWarning is hidden by Python's default filters.

## Everyday calls (verified live, 2026-11-19)
```python
c.query_object(314003014107006318, survey="lsst")                      # dict (~100 keys with survey extras)
det = c.query_detections(314003014107006318, survey="lsst", format="pandas")   # psfFlux, scienceFlux, band_name, ...
fp  = c.query_forced_photometry(314003014107006318, survey="lsst", format="pandas")
lc  = c.query_lightcurve("ZTF26aaonmha", survey="ztf")                   # dict: detections, non_detections[, forced_photometry]
pr  = c.query_probabilities("ZTF20acyxpwi", survey="ztf", format="pandas")
fe  = c.query_features(313985345706262538, survey="lsst", format="pandas")      # band is a raw int (no band_name)
df  = c.query_objects(survey="lsst", classifier="stamp_classifier_rubin_beta_20260421", class_name="SN",
                      probability=0.5, ranking=1, n_det=[5, 1000], order_by="lastmjd", order_mode="DESC",
                      page=1, page_size=50).drop_duplicates("oid")
st  = c.get_stamps(314003014107006318, measurement_id=170032901818679622, survey="lsst")  # dict of PrimaryHDU
c.catshtm_crossmatch(149.92867, 0.418448, 10)   # dict catalog -> pandas Series (radius in arcsec)
c.catshtm_redshift(149.92867, 0.418448, 10)     # first z / zphot found, e.g. 0.0345 (NEDz)
```

## The gotchas that bite first
1. **`query_objects` returns one row per (object × classifier)** on the multisurvey API. Pass `classifier=` + `ranking=1`, or `drop_duplicates("oid")`.
2. **No timeout and no retries.** A broad LSST `firstmjd` search hit the server's 55 s limit (`APIError 504 'Query timed out'`). Keep searches narrow, or use TAP (`../hunter/candidate-search.md`).
3. **Totals are lost on multisurvey.** `count=True` works only on legacy ZTF with `format="json"`.
4. **Return types differ by backend**:
   - `get_stamps` gives an `HDUList` on legacy and a dict `{cutoutScience, cutoutTemplate, cutoutDifference}` on multisurvey.
   - `query_objects` defaults to pandas; every other method defaults to json.
   - On dict responses `format="votable"` fails. `format="pandas"` gives one row: fine for `query_object`, a row of lists for `query_lightcurve` (use json there).
5. **Classifier names differ by backend.** `lc_classifier` exists only on legacy; on multisurvey it fails with `ParseError … not found`. Probability versions are ints there (2.0.2 → 202).
6. **Legacy ZTF accepts any kwarg silently** (`n_det` is ignored; it wants `ndet`). Multisurvey validates and raises `ValueError("Invalid parameter: …")`.
7. **Bad stamp/Avro ids surface oddly**: stamps raise `gzip.BadGzipFile`; `get_avro` returns the error body as bytes. LSST Avro is not served.
8. **Exceptions**: 400 `ParseError`, 404 `ObjectNotFoundError`, other ≥400 `APIError` (all `alerce.exceptions`). The message comes from the API's `detail`.

More from ALeRCE's official notebooks:
- Ranges can be open: `n_det=[30, None]`, `firstmjd=[61000, None]`.
- `get_stamps(..., survey="lsst", include_variance_and_psf=True)` adds variance and PSF planes. Headers carry `BUNIT = 'nJy'`, `ROTPA` and a full WCS; flux planes are usually 30×30 px, sometimes larger.
- `plot_stamps` and `get_stamps` also work for LSST solar-system objects (pass the ssObjectId as `oid`).
- Porting old notebooks (`lc_classifier`, `first_mjd`, `multisurvey_get_stamps`): see `../science/index.md`.

## Client vs the skill's own tools
| need | use |
|---|---|
| one object, quick, user already in the client | client (multisurvey backend) |
| light curve as nJy + mag for both surveys in one frame | `am.api_lightcurve` (normalised) |
| candidate search, samples, features of many objects, joins | TAP (`am.hunter_candidates`, `../tap/`) |
| paging totals, retries, timeouts, caching | direct REST via `am.get_json` / `am.list_objects` |
| stamps North-up with WCS handling | `am.get_stamps(..., north=True)` |
