# Legacy ZTF API and other api.alerce.online services

Base `https://api.alerce.online/ztf/v1/` (Flask, ZTF only, keyed by ZTF name). It is still heavily used and has no retirement date, but prefer the multisurvey API (`multisurvey.md`, `survey_id=ztf`). Use the legacy API when you need the **legacy classifiers** (`lc_classifier` 15-class BHRF, ATAT) or **all historical feature versions** (`/objects/{oid}/features`). The multisurvey API serves the current features at `features_api/features` (see `multisurvey.md`).

## Endpoints
| endpoint | notes |
|---|---|
| `objects/?classifier=&class=&ndet=&firstmjd=MIN&firstmjd=MAX&ranking=1&probability=&page=&page_size=&order_by=probability&order_mode=DESC&count=false` | search |
| `objects/{oid}` | record: `oid, ndet, ndethist` (string!), `ncovhist, firstmjd, lastmjd, deltajd, meanra, meandec, corrected, stellar, class, classifier, probability` |
| `objects/{oid}/lightcurve` | `{detections, non_detections}`; `sigmapsf_corr` is ~always 100 here |
| `objects/{oid}/probabilities` | many versions per classifier |
| `objects/{oid}/features` | flat `[{name, value, fid, version}]` over **all** extractor versions; take the highest strict `N.N.N` version |
| `objects/{oid}/magstats`, `classifiers` | classifiers come back duplicated; dedupe by name |
| `https://api.alerce.online/v2/lightcurve/lightcurve/{oid}?survey_id=ztf` | v2: detections + **forced photometry** with `mag, e_mag, mag_corr, e_mag_corr, e_mag_corr_ext` |

## Quirks (each has bitten real code)
- Parameter names differ from multisurvey: `class` (not `class_name`), `ndet` (not `n_det`). Add `ranking=1` to get the top class.
- `firstmjd` must be passed **twice** (min and max); a single value errors. The same applies to `ndet` ranges.
- Unknown parameters are silently dropped. A `classifier_version` filter must use the legacy spelling (`stamp_classifier_1.0.4`); a dotted version (`1.0.4`) **silently returns 0 rows**. When unsure, leave it out.
- Bare paths answer **308** to the trailing-slash form (`/objects` → `/objects/`). Follow redirects.
- `has_next` is unreliable without `count=true`; assume more pages while pages come back full.
- Corrected-magnitude errors: take `e_mag_corr_ext` from v2 (join by `candid`, compared as a string), not v1 `sigmapsf_corr`.
- Python client: `alerce.core.Alerce()` defaults to this legacy API (`survey="ztf"`, with a deprecation warning).

## Legacy-only classifiers
- `lc_classifier` (hierarchical BHRF, Sánchez-Sáez+2021), 15 classes: SNIa, SNIbc, SNII, SLSN, QSO, AGN, Blazar, CV/Nova, YSO, LPV, E, DSCT, RRL, CEP, Periodic-Other.
- `lc_classifier_top/_transient/_stochastic/_periodic`.
- `LC_classifier_ATAT_forced_phot(beta)` and `LC_classifier_BHRF_forced_phot(beta)`, 22 classes. Names carry a `(beta)` suffix; check the live `classifiers` list.

## ZTF public Data Release light curves
`GET https://api.alerce.online/ztf/dr/v1/light_curve/?ra=&dec=&radius=` (radius in **arcsec**, 1.5 is typical).
```json
[{"_id":417214200030577,"filterid":2,"fieldid":417,"rcid":53,"nepochs":261,"objra":149.92871,"objdec":0.41835,
  "hmjd":[58217.20, …],"mag":[…],"magerr":[…]}, …]
```
- There is one entry per (field, rcid, filter); merge entries per filter.
- `filterid` is 1/2/3 = g/r/i.
- `hmjd` is heliocentric MJD.
- `mag` is total (PSF-fit) magnitude on science images, not difference. This gives years of baseline before the alert stream.
- The explorer and hunter proxy it at `/api/ztf_dr?ra&dec&radius` (≤60″), returning nJy.

## TNS bridge
`GET https://api.alerce.online/v2/object_details/htmx/tns/?ra=&dec=` returns **HTML**.
- Parse the cells with `id="type"`, `id="name"`, `id="redshift"` and the link `id="tns-link"`.
- With no match it still answers 200, with `-` in the cells.
- For programmatic TNS access at scale, use the TNS API itself (needs a TNS bot key).

## ZTF alert packets and finding charts
- `GET https://avro.alerce.online/get_avro_info?oid=ZTF…&candid=…` returns `{candidate:{…all ZTF alert fields…}, objectId, prv_candidates, schemavsn, publisher}`. ZTF only; LSST ids give 404. Use `candidate.xpos/ypos` for the true pixel position in edge-clipped stamps.
- `findingchart.alerce.online`: ZTF finding chart PDF.

## Alert-packet fields worth knowing
`get_avro_info` returns the full ZTF `candidate` record. Useful fields:
- **`xpos`, `ypos`** (pixel position on the CCD): compare them across nearby candidates to catch a detector artefact (bad column, ghost) that shows up as several "transients" at the same pixels. This is the official `ALeRCE_API_check_pixels` notebook.
- **`objectidps1..3`, `sgscore1..3`, `distpsnr1..3`**: the three nearest Pan-STARRS sources with star–galaxy scores. These are also in TAP `ztf_ps1`.
- `rb`/`drb` (real–bogus), `fwhm`, `magzpsci`, plus the `prv_candidates` history.

## Retired or obsolete
- The forecast API `api.alerce.online/forecast/v1/parametric/sn` returns **404** (checked 2026-11-19).
- The 2019 POST API at `ztf.alerce.online` (`/query`, `/get_detections`, `/get_sql`, classes `classrf`/`classearly`), documented in the use-case repo's `api/*.md`, is gone.
- Direct PostgreSQL access (the `alercereaduser*.json` credentials in old notebooks) is retired; use TAP.
- **Silent parameter drop, real example:** several official notebooks pass `first_mjd=[min, None]`. The legacy API ignores unknown keys, so their date cut never applied. The correct key is `firstmjd`.
