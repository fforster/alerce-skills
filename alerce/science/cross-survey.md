# One source in two surveys: ZTF ↔ LSST (tutorial 02)

There is **no cross-survey association in the database**. The same star is one object in ZTF and another (or several) in LSST. Link them by position.

## Find counterparts
```python
obj = am.get_object("ZTF26aaonmha", "ztf")
am.find_counterparts(obj["meanra"], obj["meandec"], radius_arcsec=2)   # REST conesearch, both surveys
am.tap_cone(ra, dec, 2.0)                                               # same via ADQL (sid optional)
```
- REST `lightcurve_api/conesearch/objects_by_coordinates` takes **radius in degrees** and returns `objectId` + `survey_id`.
- `object_api/list_objects` takes `ra, dec, radius` in **arcsec**, but only for one survey per call.
- Typical radii: 1–2″ for point sources. The explorer overlays the other survey's object within 3″ and skips matches with no detections or forced photometry.
- For samples of any size, upload the positions: `am.upload_crossmatch(ztf.meanra, ztf.meandec, 2.0, sid=1)` returns every LSST object within 2″ of each ZTF object (500 positions ≈ 3 s). Filter `sid` afterwards, not in the SQL.
- Expect multiple LSST diaObjects per source, and multiple ZTF objects in field overlaps.

## Combine light curves
- `am.api_lightcurve` (REST) and `am.get_lightcurve` (TAP) return the same columns for both surveys (`diff_flux`, `sci_flux` in nJy; `diff_mag`, `sci_mag`; `kind` = det/forced). `pd.concat` them, then call `am.plot_lightcurve(lc, flux="diff"|"sci", mag=False)`. In the plots, circles are ZTF, squares LSST, filled symbols detections and open symbols forced photometry. Band colours are shared.
- Choose **difference flux** for transients and **science/total flux** for variables and AGN.
- Watch for a band-pass mismatch (ZTF g/r/i vs LSST g/r/i are similar, not identical) and different templates (difference-flux zero points differ between surveys).
- LSST MJD is TAI; ZTF MJD is UTC.

## Compare classifications
- ZTF: BHRF light-curve classes plus the stamp classifier. LSST: stamp classifiers only (no LC classifier yet).
- Disagreements are common and informative: check `lastmjd`, the data each model saw.

## Stamps side by side
```python
s_z = am.get_stamps("ZTF26aaonmha", 0, ztf_candid)                # 63×63 @ 1.012″, already sky-aligned
s_l = am.get_stamps(314003014107006318, 1, lsst_measurement_id)  # 0.2″ pixels, WCS-resampled North-up
fp = dict(corners=am.stamp_corners(314003014107006318, 1, lsst_measurement_id),
          center=am.stamp_center("ZTF26aaonmha", 0, ztf_candid), scale_arcsec=am.ZTF_PIXEL_ARCSEC, label="LSST")
am.plot_stamps(s_z, "ZTF", footprint=fp)
```
The LSST stamp footprint (~6–10″) is tiny compared with ZTF's ~64″.

## API or TAP?
| need | API | TAP |
|---|---|---|
| one object's light curve, probabilities, magstats | ✔ fastest | ✔ |
| stamps | ✔ only | ✘ |
| features | ✔ one object (`features_api`) | ✔ samples |
| samples, joins, crossmatch tables | ✘ (paged, slow) | ✔ |
