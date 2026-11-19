# TAP gotchas and how to fix them

| Symptom | Cause | Fix |
|---|---|---|
| Result has exactly 20 000 / 200 000 rows | default MAXREC truncates without an error: DaCHS returns maxrec+1 rows as an overflow marker; pyvo only emits `DALOverflowWarning` | `TOP N` plus explicit `maxrec` (hard limit 20M); split by sky or time ranges |
| 0 rows for a ZTF object | used the name or float oid | `ztf_name_to_oid(name)` → int; never round-trip oids through float |
| 0 rows joining xmatch to allwise/gaia | inner joins; each row matches one catalog | `LEFT JOIN … ON x.catid = 0 AND …` |
| 0 rows filtering `probability.classifier_version = '2.1.0'` | `probability.classifier_version` is a lossy int2 (2.1.0 → 210; 1.10.0 and 11.0.0 collide) | filter by `classifier_id`; get versions from `classifier.classifier_version` (text) |
| Wrong class names | class ids are per classifier (QSO is 10 in classifier 5, 4 in classifier 8) | always join `taxonomy` on **both** `class_id` and `classifier_id` |
| Duplicate rows or cross-survey mixups | joined on `oid` only | join on `(oid, sid)`; `ztf_*` tables join on `(oid, measurement_id)` |
| `value` column error | reserved word | the column is `feature_value` |
| Feature ids "wrong" for LSST | ids differ per survey | `feature_name_lut WHERE sid = …` |
| No LSST magstat / upper limits in TAP | never produced | use `lsst_dia_object` means (or REST `magstat_api`, which serves them), or forced photometry |
| `TAP_UPLOAD query could not be run on the direct execution path, and the slow FDW upload-join is disabled` | the uploaded table has a column named `oid` (it collides with a system column, so the server falls back to a disabled slow path). Uploads themselves work | rename the column (`objectid`); `am.tap_upload_query` refuses `oid` with a clear message |
| Spatial upload crossmatch takes minutes instead of seconds | a `WHERE o.sid = …` filter in the join query makes the planner skip the sky index (100 positions: 282 s with it, ~2 s without) | drop the sid filter and filter in pandas (`am.upload_crossmatch(..., sid=1)` does) |
| Spatial join of many positions times out | positions written into one big query instead of uploaded, 150M-row `object` | upload them: `am.upload_crossmatch(ra, dec, radius_arcsec)` (500 positions ≈ 3 s) |
| Columns `oid_`, `sid_`, `measurement_id_`, `created_date_` appear | `SELECT a.*, b.*` returns duplicated names with a `_` suffix | select explicit columns, or drop the `_` duplicates |
| `psfflux` here, `psfFlux` there | TAP returns lower-case column names; REST and the client return camelCase | normalise (`df.columns.str.lower()`) before mixing sources |
| A feature is missing for an object | `alerce_tap.feature` does not store NaN features (legacy `ztf.feature` keeps NaNs and every version); LSST features need ≥ 2 detections | treat missing as NaN |
| `E13: Invalid arraysize` parsing a result | array columns (e.g. legacy `ztf.taxonomy.classes`) break pyvo's VOTable parser | request CSV: `tap.create_query(q, responseformat='csv')`, read with pandas |
| Query takes >30 s / times out | no index behind the filter, e.g. `magstat WHERE sid = 1` or `probability WHERE classifier_id = …` without `ranking = 1`; unselective scans of `detection`/`forced_photometry`/`feature` | filter on an indexed column first (`indexes-and-joins.md`): `oid IN (…)`; on `object`, `sid` + firstmjd/lastmjd/n_det or a cone; on `probability`, `sid` + `ranking = 1` ordered by probability. Avoid `COUNT(*)`; use async for long jobs |
| Everything slow when running many queries | queries overlap and share the service (~4 s each, growing) | serialise; batch; use REST for per-object views |
| JSON parse error on `/tap/sync` | errors are VOTable XML regardless of FORMAT | check the content type or a leading `<?xml` before parsing |
| LSST ids corrupted | parsed as float or JS number | int64 / `Int64` dtype, or strings |
| Times off by ~37 s between surveys | LSST is TAI, ZTF is UTC | subtract 37 s from LSST MJDs for UTC |
| ZTF errors of 100 | "not available" sentinel | set them to NaN (also `mag == 100` in forced photometry) |
| Features or probabilities look stale | latest-only, upserted per row; the history is not in TAP | check `probability.lastmjd`, `feature.updated_date` |
| Missing ZTF objects or detections | multisurvey ZTF backfill lacks ~0.3% of objects and ~1.4M detections; ZTF xmatch has gaps since ~Nov 2025 | cross-check with the legacy API or `ztf.*` |

Also note:
- Quoted oid literals work in `IN ('313…', '313…')`.
- `DISTANCE(ra, dec, meanra, meandec) < r_deg` is accepted as a cone shorthand (fast on `object`); `CONTAINS` stays the portable form.
- ADQL has no `LIMIT`; use `SELECT TOP N`.
- String literals take single quotes.
- Geometry functions use `'ICRS'`.
- `CONTAINS(...) = 1` must be written as a comparison.
