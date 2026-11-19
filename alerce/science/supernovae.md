# Supernovae

## Find young candidates (real-time)
Use the hunter recipe (`../hunter/candidate-search.md`):
```bash
python scripts/alerce_cli.py candidates --survey lsst --class SN --days-first 7 --days-last 1 --top 50
python scripts/alerce_cli.py candidates --survey ztf  --class SN --days-first 5 --days-last 2
```
Then reject:
- objects near the ecliptic with a single detection (asteroids);
- objects with any negative alert flux;
- objects coincident with stars (Gaia parallax/pm, PS1 `sgscore1 > 0.5` within 1″) or known AGN (Milliquas, W1−W2 > 0.8);
- dipoles and edge artefacts (look at the stamps).

## Classified SN samples (archival)
ZTF, light-curve classifier (BHRF forced-phot). The REST version pages with `has_next`:
```python
am.list_objects("ztf", classifier="lc_classifier_BHRF_forced_phot", class_name="SNIa",
                probability=0.5, firstmjd=[61040, 61405], max_pages=20)
```
In TAP the same selection is one query on `probability` (classifier_id/class_id from the LUTs, `ranking = 1`, `probability > p`) joined to `object` (`../tap/recipes.md`). Transient sub-classes: SNIa, SESN (Ib/c), SNII, SNIIn, SLSN, TDE.

## One supernova end to end (tutorial 03, Part A)
1. **Light curves in both surveys**: `am.api_lightcurve(name, "ztf")` + `am.api_lightcurve(lsst_id, "lsst")`. Overplot `diff_flux` with `am.plot_lightcurve(pd.concat([...]))`.
2. **Classifiers**: BHRF said SNIbc/SESN correctly, while the stamp classifiers said bogus/AGN. LSST's first alert was a noisy host-nucleus detection about 60 d *before* explosion, so the stamp classifier never saw the SN.
3. **Host hint**: ZTF alerts carry the nearest PS1 sources (`ztf_ps1.distpsnr1`, `sgscore1`), and `distnr` gives the distance to the nearest reference-image source.
4. **Host position**: DELIGHT (CNN on PS1 images) predicts the host-centre offset.
5. **Host redshift** (one object or a few tens; 10–30 s each, see `../crossmatch/index.md`): run `am.catalog_xmatch(ra, dec)` or `am.object_xmatch(name, "ztf")` and keep `category == "host"` rows with z. DESI DR1, SDSS, NED and GAMA… are within 30–60″. Drop catalogued SNe; their z is the event's own. Prefer spectroscopic z.
6. **Absolute magnitude**:
   ```python
   from astropy.cosmology import Planck18
   mu = Planck18.distmod(z).value
   good = lc[lc.diff_flux / lc.diff_flux_err > 5]
   M = good.diff_mag - mu - A_band
   ```
   - Take E(B−V) from the dust proxy (SF11).
   - Apply a K-correction when z is not small.
   - Use **difference** flux for the SN, not science flux (that includes the host).

## Sample-level lessons (tutorial 03, Part B)
- Build the sample in ZTF with BHRF (p > threshold, 2026 discoveries). Find LSST counterparts by position (≤2″) with one upload crossmatch (`am.upload_crossmatch(..., sid=1)`).
- Fetch light curves for the whole sample in **one** TAP query per survey (`WHERE c.oid IN (...)`).
- Results:
  - LSST detects SNe earlier and deeper.
  - Peak magnitudes against host z give a Hubble diagram.
  - The classifiers often disagree between surveys: 9 of 24 LSST counterparts were stamp-classified "asteroid".
- The sample needs about 600 requests. Cache it, or precompute it (the tutorial ships precomputed tables).
- Crossmatches for samples: in-DB `xmatch`/`ztf_ps1` in one batched TAP query work at any size. Per-object host-redshift searches (`catalog_xmatch`) are fine for the tutorial's 24 SNe but not for thousands; use a bulk upload (CDS XMatch) instead (`../crossmatch/index.md`).

## Pitfalls
- ZTF `magpsf_corr` (total magnitude) exists only when `corrected` is true. For SNe on galaxies use the difference photometry.
- LSST `scienceFlux` includes the host, so subtract the pre-explosion baseline from forced photometry if you need the total SN flux.
- A single detection plus a near-ecliptic position is usually an asteroid. Check `ztf_ss.ssdistnr` for ZTF.
- TNS may already have a name and spectroscopic type: query it through the ALeRCE bridge (`../api/legacy-ztf.md`).

## Fast risers (official `ALeRCE_SN_Fast` notebook)
- Rise rate from the first detection against each earlier non-detection: `dmdt = (magpsf_first − diffmaglim_prev) / dt`. A conservative version uses `(magpsf + sigmapsf − diffmaglim) / dt`.
- Keep `dmdt < −0.5 mag/day` with `dt > 0.5 d`, then apply context cuts:
  - off the ecliptic: `n_det > 1` or ecliptic |β| > 20°;
  - off the Galactic plane: |b| > 20°;
  - low extinction: A_g < 1, from E(B−V) via the dust proxy.
- ZTF only, because LSST has no non-detections. For LSST, use the forced-photometry flux before the first detection.
- Batch the non-detections with one query (`ztf_non_detection WHERE oid IN (…)` or an upload join). `magstat.dmdt_first` holds a precomputed version.

## SPM (supernova parametric model) features
The `SPM_*` features fit a Villar-like model per band:
- `SPM_A` (amplitude);
- `SPM_t0`, relative to `SPM_mjd_ref` in `alerce_tap`;
- `SPM_gamma` (plateau length);
- `SPM_beta` (plateau slope);
- `SPM_tau_rise`, `SPM_tau_fall`;
- `SPM_chi`.

Compare `SPM_tau_rise`/`tau_fall` to tell fast transients from slow ones. The old forecast service that evaluated the model is gone (404), so evaluate it locally if you need a prediction.

## Host-galaxy tools used in the official notebooks
- **DELIGHT** (`pip install astro-delight`) predicts the host position from Pan-STARRS images.
- **NED cone search** gives host redshifts; for many objects use the crossmatch rules in `../crossmatch/index.md`.
- **SFD extinction** comes from IrsaDust or the dust proxy.
- **ipyaladin** gives an interactive sky view with catalog overlays.
