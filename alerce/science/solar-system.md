# Solar-system objects (asteroids, comets)

Full ADQL for both surveys: `../tap/examples.md` (section "Solar system", from the Schema Explorer).

## LSST: its own survey id
- Rubin links moving-object detections into **solar-system objects**: `sid = 2` (tid 1). Their `oid` is Rubin's `ssObjectId`. They have stamp-classifier rows in TAP `probability` (known asteroids get P(asteroid) ≈ 1), but they are usually found by orbit or designation rather than by class.
- An alert that carries both a diaObject and an ssObject is stored as `sid = 1` (the diaObject); its `lsst_detection.ssobjectid` is then filled.
- Tables:

  | table | contents |
  |---|---|
  | `lsst_detection WHERE sid = 2` | fluxes in nJy |
  | `lsst_ss_detection` (key `ssobjectid, measurement_id`) | per-detection geometry: MPC designation, phase angle, elongation, ephemeris offsets, helio/topocentric vectors (ranges not filled yet) |
  | `lsst_mpc_orbits` (key `ssobjectid`) | Minor Planet Center orbit: `a, q, e, i, node, argperi, H, G`, uncertainties |
  | `lsst_ss_object` | published but **empty**; per-band H/G12 and MOID will live here |

- Typical search, near-Earth orbits. Add `q > 0`, because 0 means "not filled". Then fetch detections. For `sid = 2` the `oid` **is** the ssObjectId in every table:
  - time, band and position come from `detection`;
  - fluxes and `has_stamp` come from `lsst_detection`;
  - geometry and designation come from `lsst_ss_detection` (keyed by `ssobjectid`).
```python
# runnable
import alerce_ms as am
neo = am.tap_query("SELECT TOP 5 ssobjectid, designation, a, e, i, q, h FROM alerce_tap.lsst_mpc_orbits "
                   "WHERE q > 0 AND q < 1.3 ORDER BY h")
ss = int(neo.ssobjectid.iloc[0])
det = am.tap_query(f"""SELECT d.measurement_id, d.mjd, d.band, d.ra, d.dec, l.psfflux, l.psffluxerr, l.has_stamp,
                           g.designation, g.phaseangle
    FROM alerce_tap.detection AS d
    JOIN alerce_tap.lsst_detection AS l ON l.oid = d.oid AND l.sid = d.sid AND l.measurement_id = d.measurement_id
    LEFT JOIN alerce_tap.lsst_ss_detection AS g ON g.ssobjectid = d.oid AND g.measurement_id = d.measurement_id
    WHERE d.oid = {ss} AND d.sid = 2 ORDER BY d.mjd""")
mid = int(det[det.has_stamp].measurement_id.iloc[0])
stamps = am.get_stamps(ss, 2, mid)            # science / template / difference (usually 30x30)
print(neo.iloc[0].to_dict(), len(det), stamps["science"].shape)
```
- `lsst_mpc_orbits` holds the orbits of objects ALeRCE has received, with old-style designations included (e.g. `A918 AA`).
- **Features**: none for `sid = 2` (computed for DIA objects only).
- **Forced photometry**: none by design. It is measured at a fixed sky position.
- **Static-catalog crossmatch** does not apply; the counterpart is the MPC orbit.
- REST: `object_api`, `lightcurve_api` and `probability_api` return 404 for an ssObjectId; **`stamps_api` works** (`survey_id=lsst`, the ssObjectId as `oid`). Use TAP for everything else.
- Designations: `lsst_ss_detection.designation` is **packed** (`K10W64X`); `lsst_mpc_orbits.designation` is unpacked (`2010 WX64`), with the packed form in `packed_primary_provisional_designation`. `designation` is not indexed, so filter by `ssobjectid` when you can.
- Orbit columns use 0 for "not filled" (`earth_moid`, `a`, …) and 1970 timestamps for missing dates; `g` defaults to 0.15; `mpc_orb_jsonb` holds the covariance.

## ZTF: asteroids are ordinary objects
- ZTF has no separate solar-system id. Asteroid alerts are `sid = 0` objects, usually with **one detection**. The stamp classifiers label them `asteroid`.
- `ztf_ss` holds each alert's match to the nearest known solar-system object: `ssnamenr`, `ssdistnr` (arcsec; −999 = none), `ssmagnr`. A small `ssdistnr` (< 5″) means a known asteroid.
- Forced photometry at an asteroid's alert position measures empty sky after it moved on; ignore it.

## Rejecting asteroids from transient searches
- Use the hunter's ecliptic cut (`../hunter/candidate-search.md`). Its rescue rule (≥ 2 detections spanning ≥ 15 min) keeps only static sources, because an asteroid would have moved away from the position in that time.
- For ZTF, `ztf_ss.ssdistnr` between 0 and 5″ means a known asteroid.
- The stamp-classifier class `asteroid` is a strong hint, but it also hits some real SNe.

## Workflows from the official notebooks
- **Unknown-asteroid tracklets in LSST.** Among `sid = 1` diaObjects, select those detected on a single night (`lastmjd − firstmjd < 1`) whose top stamp class is `asteroid`. Look in small RA/Dec boxes for objects that line up night by night, then confirm with per-detection positions and stamps. Look up the classifier and class ids by name.
- **Satellite glints.** A train of single-detection objects that all share the same exposure (identical `mjd`) with streak-like stamps is a satellite or glint, not a set of transients.
- **ZTF tracklets.** Group single-detection ZTF objects by `ztf_ss.ssnamenr` (known object name) to rebuild an asteroid's track. Compare the predicted MPC magnitude `ssmagnr` with the measured `magap`.
- **Unknown moving objects in ZTF.** Check them with IMCCE SkyBoT (`astroquery.imcce.Skybot`) or the MPC checker.
- **Recent LSST ssObjects:** `SELECT … FROM alerce_tap.object WHERE sid = 2 AND lastmjd >= …`, then fetch `lsst_ss_detection` and `lsst_mpc_orbits` with `ssobjectid IN (…)` (or an upload join).
