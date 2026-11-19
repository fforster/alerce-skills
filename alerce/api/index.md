# REST APIs: which endpoint answers which question

Default to the **multisurvey API** `https://api-lsst.alerce.online/<name>_api/<endpoint>`. It serves both ZTF (by name) and LSST (by diaObjectId), returns JSON and needs no auth. A call takes ~1 s, which makes it the fast path for **one object**. For many objects use TAP (`../tap/index.md`).

| Question | Call (all GET; `survey_id=ztf\|lsst` always) | Notes |
|---|---|---|
| Basic record (position, first/last MJD, n_det, n_forced, n_non_det) | `object_api/object?oid=&survey_id=` | 404 `{"detail":"Object … not found"}` if missing |
| Full light curve | `lightcurve_api/lightcurve?oid=&survey_id=` | `{detections, non_detections, forced_photometry}` in one call; repeat `oid` (≤~200) for several |
| Class probabilities | `probability_api/probability?oid=&survey_id=[&classifier=]` | bare list; `classifier_version` is an int (2.0.2 → 202) |
| Classifiers and classes | `classifier_api/classifiers[?survey_id=]` | `[{classifier_name, classifier_version, classes[], classifier_id, survey_id}]` |
| Search / filter objects | `object_api/list_objects?survey_id=&…` | paged; **radius in arcsec**; one row per (object, classifier); see `multisurvey.md` |
| Objects near a position, both surveys | `lightcurve_api/conesearch/objects_by_coordinates?ra=&dec=&radius=&neighbors=` | **radius in degrees**; returns `[{objectId, survey_id, ra, dec}]` |
| Light-curve features (periods, SPM, DRW, colours, …) | `features_api/features?oid=&survey_id=[&name=][&band=][&version=]` | `[{name, value, band, version}]`; different features can come from different extractor versions |
| Per-band magnitude statistics | `magstat_api/magstats?oid=&survey_id=` | ZTF: one row per band (mags); LSST: one row of diaObject flux summaries (nJy) |
| Live catsHTM crossmatch | `crossmatch_api/crossmatch?oid=&survey_id=` | 20″ cone; `[{catalog:{col:{unit,value}}}]` |
| Image cutouts | `stamps_api/stamp?...` (LSST) / `avro.alerce.online/get_stamp` (ZTF) | see `stamps.md` |
| ZTF public Data Release light curve | `https://api.alerce.online/ztf/dr/v1/light_curve/?ra=&dec=&radius=` | radius in arcsec; see `legacy-ztf.md` |
| TNS name/type/redshift at a position | `https://api.alerce.online/v2/object_details/htmx/tns/?ra=&dec=` | returns HTML; see `legacy-ztf.md` |
| ZTF alert packet (all candidate fields, prv_candidates) | `https://avro.alerce.online/get_avro_info?oid=&candid=` | ZTF only |

## Minimal Python
```python
import requests
API = "https://api-lsst.alerce.online"
lc = requests.get(f"{API}/lightcurve_api/lightcurve",
                  params={"oid": "ZTF26aaonmha", "survey_id": "ztf"}, timeout=60).json()
# or, normalised to nJy + AB mag for both surveys, cached, with retries:
import alerce_ms as am; df = am.api_lightcurve("ZTF26aaonmha", "ztf")
```

## Rules
- Always send `survey_id`. The old `survey=` parameter is deprecated; when both are given, `survey_id` wins.
- ZTF ids go in as names (`ZTF26aaonmha`), not the integer TAP oid. LSST ids go in as integers; read responses with int64-safe parsing.
- Bands come as ints. Map them with the row's `band_map` (`{"6":"u","1":"g",…}`).
- Use timeouts of 30–60 s and retry 429/5xx with backoff. Run calls serially. If you prefetch neighbours, do it one at a time.
- If a REST call fails, the same data is in TAP (`../tap/recipes.md`). The hunter falls back to TAP on any REST error.
- Legacy `api.alerce.online/ztf/v1` has different parameter names (`class`, `ndet`) and quirks. Read `legacy-ztf.md` before using it.

Deeper: `multisurvey.md` (all parameters and shapes) · `legacy-ztf.md` · `stamps.md`
