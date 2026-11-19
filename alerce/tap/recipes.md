# ADQL recipes (all tested patterns from the tutorial, explorer and hunter)

`{oid}` is the integer oid: ZTF via `ztf_name_to_oid`, LSST = diaObjectId. Look up `{cid}`/`{class_id}` from `classifier`/`taxonomy` by name.

## Lookups
```sql
SELECT classifier_id, classifier_name, classifier_version, tid FROM alerce_tap.classifier
SELECT c.classifier_name, t.class_id, t.class_name FROM alerce_tap.taxonomy t
  JOIN alerce_tap.classifier c ON c.classifier_id = t.classifier_id ORDER BY c.classifier_id, t.taxonomy_order
SELECT sid, band, band_name, band_order FROM alerce_tap.band
SELECT sid, feature_id, feature_name FROM alerce_tap.feature_name_lut WHERE sid = 0
```

## Cone search (both surveys)
```sql
SELECT oid, sid, meanra, meandec, firstmjd, lastmjd, n_det, n_forced,
       3600 * DISTANCE(POINT('ICRS', meanra, meandec), POINT('ICRS', {ra}, {dec})) AS sep_arcsec
FROM alerce_tap.object
WHERE 1 = CONTAINS(POINT('ICRS', meanra, meandec), CIRCLE('ICRS', {ra}, {dec}, {radius_arcsec}/3600.))
ORDER BY sep_arcsec
```

## Uploading your own table (TAP_UPLOAD): ids or positions, any size
Upload ids (name the column anything but `oid`):
```python
ids = pd.DataFrame({"objectid": oids.astype("int64")})
df = am.tap_upload_query(
    "SELECT p.oid, p.class_id, p.probability FROM alerce_tap.probability AS p "
    "JOIN tap_upload.ids AS u ON p.oid = u.objectid WHERE p.sid = 1 AND p.ranking = 1", {"ids": ids})
```
Upload positions (crossmatch an external catalog against ALeRCE objects; 500 positions ≈ 3 s):
```sql
SELECT c.src, o.oid, o.sid, 3600 * DISTANCE(POINT('ICRS', o.meanra, o.meandec), POINT('ICRS', c.ra, c.dec)) AS sep
FROM tap_upload.cat AS c
JOIN alerce_tap.object AS o
  ON 1 = CONTAINS(POINT('ICRS', o.meanra, o.meandec), CIRCLE('ICRS', c.ra, c.dec, 0.000555556))
```
Don't add `WHERE o.sid = …` here (seconds become minutes); filter in pandas. `am.upload_crossmatch(ra, dec, radius_arcsec, sid=…)` wraps this, in chunks of 2,000.

## Light curves
ZTF detections, magnitudes:
```sql
SELECT d.measurement_id, d.mjd, d.band, x.magpsf, x.sigmapsf, x.isdiffpos,
       x.magpsf_corr, x.sigmapsf_corr_ext, x.rb, x.drb, x.has_stamp
FROM alerce_tap.detection AS d
JOIN alerce_tap.ztf_detection AS x ON x.oid = d.oid AND x.measurement_id = d.measurement_id
WHERE d.oid = {oid} AND d.sid = 0 ORDER BY d.mjd
```
ZTF forced photometry:
```sql
SELECT f.mjd, f.band, f.measurement_id, x.mag, x.e_mag, x.isdiffpos, x.mag_corr, x.e_mag_corr_ext
FROM alerce_tap.forced_photometry AS f
JOIN alerce_tap.ztf_forced_photometry AS x ON x.oid = f.oid AND x.measurement_id = f.measurement_id
WHERE f.oid = {oid} AND f.sid = 0
```
ZTF upper limits (no sid column):
```sql
SELECT mjd, band, diffmaglim FROM alerce_tap.ztf_non_detection WHERE oid = {oid} ORDER BY mjd
```
LSST detections (nJy). For forced photometry, swap in `forced_photometry` + `lsst_forced_photometry`:
```sql
SELECT d.measurement_id, d.mjd, d.band, x.psfflux, x.psffluxerr, x.scienceflux, x.sciencefluxerr,
       x.snr, x.reliability, x.has_stamp
FROM alerce_tap.detection AS d
JOIN alerce_tap.lsst_detection AS x
  ON x.oid = d.oid AND x.measurement_id = d.measurement_id AND x.sid = d.sid
WHERE d.oid = {oid} AND d.sid = 1 ORDER BY d.mjd
```
**Batched**: replace `d.oid = {oid}` with `d.oid IN ({oid1}, {oid2}, …)` and add `d.oid` to the SELECT. Use one query for the whole sample. `alerce_ms.get_lightcurve(oid, sid)` returns all of this as nJy + AB mag.

## Probabilities
All classifiers for one object, decoded:
```sql
SELECT c.classifier_name, c.classifier_version, t.class_name, p.probability, p.ranking, p.lastmjd
FROM alerce_tap.probability p
JOIN alerce_tap.classifier c ON p.classifier_id = c.classifier_id
JOIN alerce_tap.taxonomy t ON p.class_id = t.class_id AND p.classifier_id = t.classifier_id
WHERE p.oid = {oid} AND p.sid = {sid} ORDER BY c.classifier_name, p.ranking
```
Sample selection (top class = X with p > 0.8), joined to object properties:
```sql
SELECT TOP 1000 p.oid, p.probability, o.meanra, o.meandec, o.n_det, o.firstmjd, o.lastmjd
FROM alerce_tap.probability AS p
JOIN alerce_tap.object AS o ON o.oid = p.oid AND o.sid = p.sid
WHERE p.sid = 0 AND p.classifier_id = {cid} AND p.class_id = {class_id}
  AND p.ranking = 1 AND p.probability > 0.8
ORDER BY p.probability DESC
```
Hierarchical BHRF, ZTF: `P(SNIa) = P_top(Transient) × P_transient(SNIa)`, or read the flat `lc_classifier_BHRF_forced_phot` directly (see `../classifiers/index.md`).

## Features (TAP for samples; one object: REST `features_api/features`)
```sql
SELECT f.oid, n.feature_name, f.band, f.feature_value
FROM alerce_tap.feature AS f
JOIN alerce_tap.feature_name_lut AS n ON n.sid = f.sid AND n.feature_id = f.feature_id
WHERE f.sid = {sid} AND f.oid IN ({oids}) AND n.feature_name IN ('Multiband_period', 'Amplitude')
```
- For speed, resolve the feature ids first (`alerce_ms.feature_ids(sid, names)`) and filter `f.feature_id IN (…)`.
- `band = 12` means g+r combined; `band = 0` means band-independent. The ZTF `Multiband_period` is band 12, the LSST one band 0.
- Pivot wide in pandas: `alerce_ms.get_features(oid, sid, names, wide=True)` for one object; `alerce_ms.get_features_many(oids, sid, names)` for a sample (one upload join per 5,000 objects; columns `<name>_<band>`).

## Stored crossmatch (AllWISE, Gaia DR3)
```sql
SELECT c.catalog_name, x.oid_catalog, x.dist,
       a.w1mpro, a.w2mpro, a.w1mpro - a.w2mpro AS w1_w2,
       g.phot_g_mean_mag, g.bp_rp, g.parallax, g.parallax_error, g.pm, g.ruwe, g.in_qso_candidates
FROM alerce_tap.xmatch AS x
JOIN alerce_tap.catalog_id_lut AS c ON c.catid = x.catid
LEFT JOIN alerce_tap.allwise AS a ON c.catalog_name = 'AllWISE' AND a.oid_catalog = x.oid_catalog
LEFT JOIN alerce_tap.gaiadr3_source AS g ON c.catalog_name = 'GaiaDR3_source' AND g.oid_catalog = x.oid_catalog
WHERE x.oid = {oid} AND x.sid = {sid}
```
Use **LEFT** joins. Each xmatch row matches only one of the two catalogs, so inner joins return 0 rows. Catalogs are picked by name through `catalog_id_lut` (`AllWISE`, `GaiaDR3_source`), not by `catid`. `x.dist` is in arcsec. For a sample, join `tap_upload` ids instead of `x.oid = …` (see `../science/agn.md`).

## ZTF host and star hints
```sql
SELECT TOP 1 sgscore1, distpsnr1, srmag1 FROM alerce_tap.ztf_ps1 WHERE oid = {oid}
SELECT TOP 1 ssdistnr, ssnamenr FROM alerce_tap.ztf_ss WHERE oid = {oid}
```
- `sgscore1` > 0.5 with `distpsnr1` < 1″ suggests a star.
- `ssdistnr` ≥ 0 and small means a known asteroid.

## Recent-object searches, ecliptic cut, now-MJD
See `../hunter/candidate-search.md` for the full hunter search (classifier + class + recency + n_det + ecliptic rejection, ordered by probability).

## Magnitude statistics
- ZTF, integer oids: `SELECT * FROM alerce_tap.magstat WHERE oid = {oid} AND sid = 0`.
- ZTF by name (legacy): `SELECT oid, fid, magmin, magmean_corr FROM ztf.magstat WHERE oid IN ('ZTF..', …)`.
- LSST has no magstat. Per-band mean fluxes are in `lsst_dia_object`, e.g. `SELECT oid, g_psffluxmean, r_psffluxmean, g_sciencefluxmean FROM alerce_tap.lsst_dia_object WHERE oid IN (…)`.
