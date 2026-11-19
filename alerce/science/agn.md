# AGN and quasars (tutorial 04)

## Identify
- **Classifiers**: ZTF BHRF classes QSO, AGN, Blazar (stochastic branch). The Rubin stamp classifiers (beta) tend to call point-like quasars **VS**; from one stamp a variable quasar looks like a star.
- **In-DB crossmatch** (TAP `xmatch`, ~1″): AllWISE `W1−W2 > 0.8` (Vega) selects AGN. Gaia DR3 adds `in_qso_candidates`, `classprob_dsc_combmod_quasar`, and parallax/pm consistent with zero.
  ```python
  am.get_xmatch("ZTF20acyxpwi", 0)           # one object
  ```
  For a sample, use one upload join (any size; 1,000 objects ≈ 3 s). `xmatch.dist` is in arcsec.
```python
# runnable
import pandas as pd, alerce_ms as am
clf = "lc_classifier_BHRF_forced_phot"
top = am.tap_query(f"""SELECT TOP 1000 oid, probability FROM alerce_tap.probability
    WHERE sid = 0 AND ranking = 1 AND classifier_id = {am.classifier_id(clf)} AND class_id = {am.class_id(clf, "QSO")}
    ORDER BY probability DESC""", maxrec=1000)
w = am.tap_upload_query("""SELECT x.oid, x.dist, a.w1mpro - a.w2mpro AS w1_w2
    FROM alerce_tap.xmatch AS x
    JOIN alerce_tap.catalog_id_lut AS c ON c.catid = x.catid
    JOIN alerce_tap.allwise AS a ON a.oid_catalog = x.oid_catalog
    JOIN tap_upload.ids AS u ON x.oid = u.objectid
    WHERE x.sid = 0 AND c.catalog_name = 'AllWISE'""", {"ids": pd.DataFrame({"objectid": top.oid.astype("int64")})})
print(len(w), "with AllWISE;", (w.w1_w2 > 0.8).mean(), "have W1-W2 > 0.8")
```
  ⚠️ **Circularity:** the light-curve classifier uses WISE colours (`W1-W2`, `g-W2`, …) as features, so its top QSOs are WISE-red almost by construction. On 2026-11-19, 1000 of the top 1000 had W1−W2 > 0.8. Use WISE as independent confirmation only for objects selected some other way (e.g. by variability or the stamp classifier).
- **External** (per object, small samples only; for large samples stick to the in-DB tables above or a bulk CDS XMatch upload): Milliquas / Véron-Cetty / SDSS DR16Q within 3″ (`am.catalog_xmatch`), and catsHTM (`am.catshtm_crossmatch(ra, dec, 5)`; the REST crossmatch_api uses 20″).
  - ⚠️ catsHTM **XMM coordinates are in radians** although labelled degrees.
- **Redshift**: SDSS DR16Q, DESI, NED or SIMBAD give spectroscopic z (the guiding quasar has z ≈ 1.48).

## Light curves
- Use **total (science) brightness**, `sci_mag`/`sci_flux`. The AGN is the source itself, so the difference flux depends on the template epoch.
  - ZTF: `magpsf_corr` (when `corrected`).
  - LSST: `scienceFlux`.
- Combine ZTF (long baseline, plus ZTF DR via `api.alerce.online/ztf/dr/v1/light_curve/`) with LSST (deeper, ugrizy).
- Rest-frame time: `Δt_rest = Δt_obs / (1+z)`. The rest-frame SED comes from catalog photometry (catsHTM/WISE/2MASS/GALEX) plus the redshift.

## Variability features (TAP `feature`)
- Damped random walk: `GP_DRW_sigma` (a **variance**, µJy² for ZTF) and `GP_DRW_tau` (days; values pile up at the fit bounds e^±6 d, meaning unconstrained).
- Also `ExcessVar`, `Amplitude`, `SF_ML_amplitude`, `SF_ML_gamma`, and `Pvar`/`ExcessVar` per band.
- Lesson: amplitudes agree between surveys while timescales do not, not even between ZTF g and r. Features come from whatever light curve existed, so a short baseline cannot constrain τ.
- To study timescales, compute a **structure function** from the combined ZTF + LSST rest-frame light curve.
```python
am.get_features(oid, sid, ["GP_DRW_sigma", "GP_DRW_tau", "ExcessVar"], wide=True)
```
Feature ids differ per survey; the helper looks them up.

## Samples (tutorial 04 §5–6)
- Select ZTF AGN/QSO with BHRF (`list_objects … n_det=[50, 100000]`, or TAP).
- Select LSST AGN via the stamp classifier (beta; noisy).
- Pair the two surveys within 1.5″ locally.
- Pull WISE/Gaia/redshifts with one TAP query, then plot the WISE colour–colour diagram and luminosities.
- Read ZTF oids as `Int64`, not float: they exceed 2^53.

## Notes from the official AGN notebooks
- **Corrected vs difference photometry.**
  - Use corrected (total) magnitudes for AGN light curves. The difference flux can change sign; Mrk 817 is the official example.
  - `g_r_mean_corr` (corrected colour) separates host-dominated AGN (redder) from QSOs; difference-image colours do not.
- **Useful features by class:** PS1 colours and `sgscore1` (from `ztf_ps1`), `MHPS_*` (Mexican-hat power spectrum) and `GP_DRW_*`.
- **Blazars:** overlay the ZTF Data Release light curve (`api.alerce.online/ztf/dr/v1/light_curve/`) on the alert light curve for a years-long baseline.
