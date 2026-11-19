# Periodic variable stars (tutorial 05)

## Data
- Use **forced photometry plus detections, in total (science) magnitudes** (`sci_mag`). Alert-only light curves are biased toward bright phases.
  ```python
  lz = am.api_lightcurve("ZTF17aabhbva", "ztf")
  ll = am.api_lightcurve(313888627082919999, "lsst")
  lc = pd.concat([lz, ll])
  am.plot_folded(lc, period=0.48888)
  ```
- **Duplicates go both ways.** One star can be several ZTF objects (different fields or CCDs) and several LSST diaObjects (Rubin splits sources). Look at each separately, then merge or keep the one with the most `n_det`. The guiding RR Lyrae has two LSST diaObjects.

## ALeRCE periods (TAP `feature`)
- Feature names: `Multiband_period` (band 12 for ZTF, band 0 for LSST), `Period_band` per band, `PPE` (period-power excess), `Amplitude`, Fourier components, etc.
- ZTF gave 0.4889 d for the RR Lyrae and LSST `Multiband_period` gave 0.978 d, **twice the true period** (an alias). Always sanity-check automatic periods.
```python
am.get_features("ZTF17aabhbva", 0, ["Multiband_period", "PPE"])
```
Sample query (verbatim pattern):
```sql
SELECT o.oid, o.meanra, o.meandec, o.n_det, p.class_id, p.probability
FROM alerce_tap.object AS o
JOIN alerce_tap.probability AS p ON p.oid = o.oid AND p.sid = o.sid
WHERE o.sid = 0 AND o.n_det >= 30
  AND p.classifier_id = {cid} AND p.ranking = 1 AND p.class_id IN ({class_ids})
  AND 1 = CONTAINS(POINT('ICRS', o.meanra, o.meandec), CIRCLE('ICRS', {RA0}, {DEC0}, {RADIUS}))
```
- `cid` is `lc_classifier_BHRF_forced_phot`, with classes RRLab, RRLc, CEP, DSCT, EA, EB/EW, LPV…
- For LSST, there is no LC classifier: take `object WHERE sid = 1 AND n_det >= 20 AND CONTAINS(...)` and match to ZTF locally with astropy.
- Then fetch features with one query: `feature WHERE sid = … AND feature_id = … AND oid IN (…)`.

## Measuring periods robustly
1. **Window function**: ground-based sampling clumps at the same time of night, giving 1-day aliases (`f ± 1 d⁻¹`) and harmonics (P/2, 2P). ZTF (Palomar) and LSST (Cerro Pachón) sample different UTC hours, so combining them helps.
2. Multi-band Lomb-Scargle on the combined light curve (`astropy.timeseries.LombScargleMultiband`), then **multi-harmonic Fourier fits** to break aliases. RR Lyrae are asymmetric, which the harmonics capture.
3. Refine and estimate precision: phase drift over the long ZTF + LSST baseline gives δP ~ P²·δφ/T. Bootstrap for errors.
4. **Sanity checks**: VSX (type and period), SIMBAD, Gaia DR3 variability flags. Use `am.vizier_query_region` / `am.simbad_query_region`, which have mirrors.
5. **Bailey diagram** (period vs amplitude) separates RRab from RRc.

Remember the time scales (LSST TAI vs ZTF UTC; 37 s is negligible for P ~ 0.5 d, but not for very short periods or high-precision O−C).

## Periodograms used by ALeRCE (official `ALeRCE_Other_Periodograms` notebook)
- **P4J** (`pip install P4J`) is the periodogram package from ALeRCE's pipeline. Its methods are `PDM1`, `LKSL`, `MHAOV` (multi-harmonic AoV; the pipeline's choice), `QMICS` and `QMIEU`.
- Pattern: `frequency_grid_evaluation(fmin=0, fmax=5, fresolution=1e-5)`, then `finetune_best_frequencies`.
- Multiband trick when you have no multiband method: z-normalise each band separately, merge them, and run a single-band periodogram.
- Example eclipsing binary: ZTF18abuamei, P = 0.26530758 d.
