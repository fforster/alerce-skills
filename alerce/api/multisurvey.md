# Multisurvey REST API reference (`https://api-lsst.alerce.online`), verified 2026-11-18

Each service has OpenAPI docs at `/<name>_api/docs`. Versions: object 0.2.24, lightcurve 0.2.27, stamps 0.2.25, the rest 0.2.20. `*` = required.

## object_api
### `GET /object_api/object` — `oid*`, `survey_id*`, `return_survey_extra=false`
```json
{"oid":"ZTF26aaonmha","tid":0,"sid":0,"meanra":149.9286,"meandec":0.4184,"sigmara":0.0029,"sigmadec":0.0029,
 "firstmjd":61121.316,"lastmjd":61185.211,"deltamjd":63.9,"n_det":39,"n_forced":36,"n_non_det":54, ...}
```
The LSST `oid` comes back as an integer. Probabilities are **not** in this record; use `probability_api`.

### `GET /object_api/list_objects`
Parameters: `survey_id` (**without it only ZTF is searched**), `classifier`, `class_name`, `ranking=1`, `probability=0` (minimum), `n_det` (repeat for `[min,max]`), `firstmjd` (repeat for `[min,max]`), `lastmjd` (repeat), `ra`, `dec`, `radius` (**arcsec**), `oid` (repeatable), `page=1`, `page_size=10`, `count=false`, `order_by=probability`, `order_mode=DESC`.

Response:
```json
{"total":null,"next":2,"has_next":true,"prev":null,"has_prev":false,"current_page":1,
 "items":[{"oid":170587116145737778,"sid":1,"meanra":...,"n_det":2,"class_name":"SN",
           "classifier_name":"stamp_classifier_rubin_beta_20260421","classifier_version":"2.0.2",
           "probability":0.995,"ranking":1}, ...]}
```

Gotchas:
- **One row per (object, classifier)** unless you pass `classifier`. Deduplicate by `oid`.
- Keep `count=false`. The total count is the expensive path.
- `has_next` can be unreliable. Treat a full page as "maybe more".
- `page_size` ≤ 100 is safe. Larger pages have returned 422 or timed out.
- For a cone search combined with a time window on dense fields, use `order_by=lastmjd&order_mode=DESC`. Ordering by probability scans everything, can time out, and has silently ignored `lastmjd`.
- Searching by an `oid` list: results come back ordered by probability and paginated, so walk the pages until every id appears. Don't add a classifier filter, or objects not yet classified are dropped.
- `list_objects` reports `classifier_version` as a dotted string; `probability_api` reports it as an int.
- Empty result: `{"items":[],"info_message":"Empty query",...}`.
- For complex or large selections TAP is faster and exact (`../hunter/candidate-search.md`).

## lightcurve_api (`survey_id*`, `oid*` repeatable up to ~200)
| endpoint | returns |
|---|---|
| `/lightcurve` | `{"detections":[…],"non_detections":[…],"forced_photometry":[…]}` |
| `/detections`, `/non_detections`, `/forced-photometry` (hyphen) | the single list |
| `/conesearch/objects_by_coordinates?ra&dec&radius&neighbors` | `[{"objectId":"314003014107006318","survey_id":"lsst","ra":…,"dec":…}, {"objectId":"ZTF26aaonmha","survey_id":"ztf",…}]`. **radius in degrees**; both surveys |
| `/conesearch/objects_by_oid?oid&survey_id&radius&neighbors` | neighbours of an object |
| `/conesearch/lightcurve_by_oid?oid&survey_id&radius&neighbors` | combined light curves of neighbours |

With one oid, a missing object answers 404. With several oids, missing ones are silently left out.

**LSST detection row** (selected fields of 120+):
- Ids and position: `band`, `band_map`, `mjd` (TAI), `ra`, `dec`, `oid`, `measurement_id` (= diaSourceId), `visit`, `detector`.
- Photometry: `psfFlux`, `psfFluxErr` (difference, nJy), `scienceFlux`, `scienceFluxErr` (direct image, nJy), `templateFlux`, `apFlux`, `snr`.
- Quality and shape: `reliability` (real/bogus), `extendedness`, `isDipole`, trail fields, `pixelFlags_*`, `isNegative`.
- `has_stamp`.

**LSST forced row**: `band`, `mjd`, `measurement_id`, `ra`, `dec`, `visit`, `detector`, `psfFlux(Err)`, `scienceFlux(Err)`.

**ZTF detection row**:
- `band`, `band_map`, `mjd` (UTC), `measurement_id` (= candid), `pid`, `isdiffpos`.
- Photometry: `magpsf`, `sigmapsf`, `magpsf_corr`, `sigmapsf_corr`, `sigmapsf_corr_ext`, `magap`, `diffmaglim`.
- Flags and quality: `corrected`, `dubious`, `rb`, `drb`, `distnr`, `rfid`, `parent_candid`, `has_stamp`.

**ZTF forced row**: `mag`, `e_mag`, `mag_corr`, `e_mag_corr`, `e_mag_corr_ext`, `isdiffpos`, `corrected`, `field`, `rcid`, `magzpsci`, `sciinpseeing`, `diffmaglim`, `distnr`, `magnr`, …

**ZTF non-detection row**: `band`, `mjd`, `diffmaglim`. LSST: always `[]`.

## probability_api
`GET /probability_api/probability?oid*&survey_id[&classifier]` returns
`[{"classifier_name":"stamp_classifier_rubin_beta_20260421","classifier_version":202,"class_name":"AGN","probability":0.457,"ranking":2}, …]`.
These are the latest values only. For a ZTF object the list can include several historical versions of a classifier. Keep the highest version, or match the TAP dotted version by its digits.

## classifier_api
- `GET /classifier_api/classifiers[?classifier_name][&survey_id]` → `[{"classifier_name","classifier_version":"2.0.2","classes":["SN","AGN","VS","asteroid","bogus"],"classifier_id":3,"survey_id":1}]`.
- `GET /classifier_api/classes?classifier_name*&classifier_version*[&survey_id]` → `[{"name":…}]` in taxonomy order.

## features_api
`GET /features_api/features?oid*&survey_id*[&name][&band][&version]` returns `[{"name":"Amplitude","value":0.0779,"band":1,"version":"27.8.0"}, …]`. Example sizes: 550 rows for an LSST quasar, 193 for a ZTF one.
- `band` is a raw int, or a band set (12 = g+r, 0 = none), with no `band_name`.
- **One object's features can come from different extractor versions** (e.g. LSST: some `27.5.7a31`, some `27.8.0`; one row per (name, band)). Pass `version=` if you need a consistent set.
- `name=` returns one feature, e.g. `Multiband_period`.
- Missing from an API snapshot of 2026-11-18; verified live 2026-11-19 (service version 0.2.20).

## magstat_api
`GET /magstat_api/magstats?oid*&survey_id*` returns per band: `{band, ndet, magmean, magmedian, magmax, magmin, magsigma, magfirst, maglast, firstmjd, lastmjd, corrected, stellar, ndubious}`. That is the ZTF shape. For LSST the same call returns **one** row of diaObject summaries in nJy (`u_psfFluxMean`, `g_psfFluxMax`, `r_psfFluxNdata`, `firstDiaSourceMjdTai`, …), like TAP `lsst_dia_object`. The TAP `magstat` table has no LSST rows.

## crossmatch_api
`GET /crossmatch_api/crossmatch?oid*&survey_id*` is a live catsHTM cone of 20″. It returns `[{"DECaLS":{"RA":{"unit":"deg","value":…},…}},{"GAIA/DR2":{…}},…]`, which is **not** the stored `xmatch` table in TAP.

## stamps_api
See `stamps.md`. `GET /stamps_api/stamp?oid*&measurement_id*&stamp_type*&file_format*&survey_id*&is_compressed=true`. `/stamps_api/avro` returns 400 for LSST.

## Errors
| HTTP | Meaning |
|---|---|
| 404 | `{"detail":"Object 1 not found on the database"}` |
| 422 | bad enum/type, e.g. `survey_id=atlas` → "Input should be 'ztf' or 'lsst'" |
| 429 | rate limited; back off |
| 5xx/timeout | retry with backoff, then fall back to TAP |
