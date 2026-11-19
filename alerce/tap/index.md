# TAP / ADQL access (`https://tap.alerce.online/tap`)

Use TAP for **many objects**: sample selection, joins, features, batched light curves, statistics. It is a GAVO DaCHS service over the multisurvey DB, with schema **`alerce_tap`** (31 tables, ZTF + LSST, integer oids). The legacy schema `ztf` (ZTF only, oid = name) is still served; avoid it except for `ztf.magstat` lookups by name.

## Clients
```python
import pyvo
tap = pyvo.dal.TAPService("https://tap.alerce.online/tap")
df = tap.search("SELECT TOP 10 * FROM alerce_tap.object WHERE sid = 1", maxrec=100000).to_table().to_pandas()
# or the cached + retrying wrapper:
import alerce_ms as am; df = am.tap_query(adql, maxrec=1_000_000)
```
Without pyvo, use plain HTTP:
`GET https://tap.alerce.online/tap/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv|json&MAXREC=N&QUERY=<urlencoded>`.
- JSON comes back as `{"columns":[{"name":…}],"data":[[…]]}`.
- **Errors come back as VOTable XML even when you asked for JSON or CSV.** Check the response before parsing.
- Long queries go to `/tap/async` (pyvo `tap.run_async`). Async jobs can be lost if the service restarts, so keep their results promptly.

CLI: `python scripts/alerce_cli.py adql "SELECT …" --maxrec 100000`.

## Discover the schema at runtime
```sql
SELECT table_name, description FROM TAP_SCHEMA.tables WHERE schema_name = 'alerce_tap'
SELECT column_name, datatype, unit, description FROM TAP_SCHEMA.columns WHERE table_name = 'alerce_tap.object'
```

## Rules of thumb
1. **Join on `(oid, sid)`.** Survey extension tables (`ztf_*`) have no `sid`; join them on `(oid, measurement_id)`. `lsst_*` tables do have `sid`.
2. **Filter by `sid`** in every per-object query (0 = ZTF, 1 = LSST).
3. **ZTF oids are integers here.** Convert names with `ztf_name_to_oid`. LSST oids are diaObjectIds.
4. **Decode with lookup tables**, not constants: `classifier`, `taxonomy`, `band`, `feature_name_lut`, `feature_version_lut`, `catalog_id_lut`, `sid_lut`. `alerce_ms.decode(df)` adds all the names.
5. **Always `TOP N` and/or `maxrec`.** The default MAXREC truncates without an error; pyvo merely warns `DALOverflowWarning` (20k or 200k have been observed; the hard limit is 20M).
6. **Batch.** Use one query with `oid IN (…)` (hundreds to a few thousand ids) instead of a loop. For larger id lists, or any list of positions, **upload a table** (TAP_UPLOAD; `am.tap_upload_query`, `am.upload_crossmatch`): 500 ids join in ~1 s and 500 positions crossmatch in ~3 s. Two traps: an uploaded column named `oid` fails (call it `objectid`), and a `WHERE o.sid = …` filter in a spatial upload join makes it take minutes (filter sid afterwards). (Before 2026-11-19 this skill wrongly said uploads were disabled.) Uploads are read-only queries over HTTPS, but the uploaded list is sent to ALeRCE's public service: ask before uploading a confidential catalog. Without an upload, a spatial join of many positions written as one big query times out.
7. **Select the small set first, then join.** For example, filter `probability` by classifier_id/class_id/ranking and `object` by time or cone, then join the detections.
8. **Avoid `COUNT(*)` and unfiltered scans** on `detection` (~660M rows), `forced_photometry` (~1.5G rows) and `feature`. Filter on indexed columns first: `oid` everywhere; on `object` also `(sid, firstmjd|lastmjd|n_det)` and cones; on `probability` use `sid + ranking = 1 + ORDER BY probability`. See `indexes-and-joins.md`.
9. **Don't overlap queries.** Each takes ~4 s and they slow each other down. For a single object, use REST (`../api/index.md`).
10. **Cone search** uses `1 = CONTAINS(POINT('ICRS', meanra, meandec), CIRCLE('ICRS', ra, dec, r_deg))`. Separation: `3600*DISTANCE(POINT('ICRS',meanra,meandec), POINT('ICRS',ra,dec))`.

Deeper:
- `schema.md`: tables and key columns, feature families.
- `indexes-and-joins.md`: **which filters are fast**, join rules, relations.
- `columns.md`: all 725 columns with units and descriptions; grep it.
- `recipes.md`: copy-paste ADQL.
- `examples.md`: 8 end-to-end workflows, re-run daily by the Schema Explorer.
- `gotchas.md`: slow, empty, truncated or wrong results.

The last three generated files come from the **alerce_tap Schema Explorer**, an interactive page with every table, column, index and relation, refreshed daily: https://claude.ai/artifact/JEpEyijsTpD1y83ut7Zia7#object (change the anchor to jump to a table) (regenerated with `tools/build_schema_refs.py`). A companion **Multisurvey API Explorer** documents the REST endpoints with live examples: https://claude.ai/artifact/Bj9Jox1G6dBcsNAsBhtis8.
