# Hunter internals: candidate search, enrichment and fast object views

Source: the experimental hunter's search, enrichment and object-view logic (Nov 2026).

## Architecture that works
| step | service | why |
|---|---|---|
| search (rank candidates) | **TAP**, one query | exact filters, ecliptic cut applied before `TOP N` |
| enrichment (discovery/last mag, bands, negative-flux rejection) | **TAP**, one batched query per ≤100–1000 oids | avoids N round trips |
| open one candidate (object, probabilities, light curve, stamps) | **REST** first, TAP fallback on any error | REST ~1 s vs TAP ~4 s per query; a cold candidate went from 5–13 s to 0.8–2 s (≈5× faster) |
| prefetch neighbours | REST, **one at a time**, only after the visible object loaded; stop when the user moves on | bursts competed with the visible object and triggered IP blocks |

Fast object view, details:
- Start the single light-curve call (`lightcurve_api/lightcurve` returns det + nondet + forced) **before** the object record, and share it between the light curve and the stamp picker.
- Coalesce identical in-flight requests and cache for ~120 s; do not cache failures.
- The ZTF REST object record lacks `n_forced`; take it from the light-curve bundle.
- Legacy ZTF names the detection count `ndet` (map it to `n_det`).
- Classifier versions differ between TAP (`2.0.2`) and REST (`202`). Match exactly, then by digits.

## Search ADQL (verbatim structure)
```sql
SELECT TOP {limit} o.oid, o.meanra, o.meandec, o.firstmjd, o.lastmjd, o.n_det, o.n_forced,
       p.probability, t.class_name, c.classifier_name, c.classifier_version
FROM alerce_tap.object o
JOIN alerce_tap.probability p ON o.oid = p.oid AND o.sid = p.sid
JOIN alerce_tap.classifier c ON p.classifier_id = c.classifier_id
JOIN alerce_tap.taxonomy t ON p.class_id = t.class_id AND p.classifier_id = t.classifier_id
WHERE o.sid = {sid} AND p.ranking = 1
  AND o.n_det >= {n_det_min}
  AND o.firstmjd >= {now - 7} AND o.lastmjd >= {now - 1}
  [AND p.probability >= {pmin}]
  AND c.classifier_name = '{classifier}' [AND c.classifier_version = '{dotted}']
  AND t.class_name = 'SN'
  AND {ecliptic_keep_clause}
  [AND 1 = CONTAINS(POINT('ICRS', o.meanra, o.meandec), CIRCLE('ICRS', {ra}, {dec}, {r_deg}))]
ORDER BY p.probability DESC
```
`now` (MJD, UTC) = `unix_seconds/86400 + 40587`. Remember that LSST `firstmjd`/`lastmjd` are TAI; 37 s doesn't matter here.

### Ecliptic keep-clause (asteroid rejection inside the WHERE, before TOP)
```sql
(o.meanra IS NULL OR o.meandec IS NULL
 OR ABS(ASIN(SIN(RADIANS(o.meandec))*COS(RADIANS(23.4393))
           - COS(RADIANS(o.meandec))*SIN(RADIANS(23.4393))*SIN(RADIANS(o.meanra)))) > RADIANS(10)
 OR (o.n_det >= 2 AND (o.lastmjd - o.firstmjd) >= 0.010416666666666666))
```
It keeps objects more than 10° from the ecliptic, or with ≥2 detections spanning ≥15 min. Asteroids move away within minutes, so detections that far apart are only associated into one object if the source is static; the rescued objects are not asteroid leakage. Applying it after the fetch made the survivors depend on `TOP N`: 111 survivors at N=500 vs 165 at N=5000 for the same objects.

## Enrichment (one query for the result set)
```sql
-- ZTF
SELECT d.oid, d.mjd, d.band, zd.magpsf, zd.isdiffpos
FROM alerce_tap.detection d
JOIN alerce_tap.ztf_detection zd ON d.oid = zd.oid AND d.measurement_id = zd.measurement_id
WHERE d.sid = 0 AND d.oid IN ({oids}) ORDER BY d.oid, d.mjd
-- LSST
SELECT d.oid, d.mjd, d.band, ld.psfflux
FROM alerce_tap.detection d
JOIN alerce_tap.lsst_detection ld ON d.oid = ld.oid AND d.measurement_id = ld.measurement_id
WHERE d.sid = 1 AND d.oid IN ({oids}) ORDER BY d.oid, d.mjd
```
Then, per object:
- discovery mag = earliest detection;
- last mag = latest detection with positive flux;
- bands = set of detected bands;
- **reject** if any alert detection is negative (ZTF `isdiffpos` < 0, LSST `psfflux` < 0). Forced photometry is ignored for this.

## Model pre-labels (off-nuclear SN picks)
```sql
SELECT p.oid, p.probability, p.lastmjd, c.classifier_name, c.classifier_version
FROM alerce_tap.probability p
JOIN alerce_tap.classifier c ON c.classifier_id = p.classifier_id
JOIN alerce_tap.taxonomy t ON t.class_id = p.class_id AND t.classifier_id = p.classifier_id
WHERE p.sid = 1 AND c.classifier_name = 'stamp_sn_offnuclear_rubin_beta' AND t.class_name = 'SNoffnuclear'
  AND p.ranking = 1 AND p.lastmjd >= {now - 3}
ORDER BY p.probability DESC
```
The hunter itself filters on `classifier_id = 10, class_id = 0`. Joining by name, as above, survives renumbering. In Python, `am.classifier_id(name)` and `am.class_id(classifier, cls)` resolve the ids.

## Python
```python
import alerce_ms as am
c = am.hunter_candidates("lsst", class_name="SN", max_days_since_first=7, max_days_since_last=1, top=100)
for name in c.name[:5]:                                   # open each with REST, serially
    lc = am.api_lightcurve(name, "lsst"); pr = am.api_probabilities(name, "lsst")
print(am.explorer_list_urls(list(c.name), "lsst")["experimental explorer"])
```
If a short window returns 0 rows, the stream may be quiet or stalled (weather, season, downtime). Check the freshness first:
```sql
SELECT TOP 1 lastmjd FROM alerce_tap.object WHERE sid = 1 ORDER BY lastmjd DESC   -- ~2 s
```
Compare it with `now`, then anchor both windows at that epoch (`am.hunter_candidates(..., reference_mjd=am.latest_mjd("lsst"))`). Widening only the first-detection window does not help while the last-detection window excludes everything. Also guard against empty oid lists before building `IN (…)`: `IN ()` is an ADQL syntax error. `am.candidate_enrichment` handles that.
