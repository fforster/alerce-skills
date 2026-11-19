# `alerce_tap` schema (live TAP_SCHEMA, 2026-11-18)

Row counts are approximate (Oct 2026). Units are in brackets. The column lists are complete except for the very wide tables.

## Core, both surveys (keyed by `oid, sid`)
| table | columns |
|---|---|
| `object` (~150M) | oid, tid, sid, meanra[deg], meandec[deg], sigmara[deg], sigmadec[deg], firstmjd, lastmjd, deltamjd, n_det, n_forced, n_non_det, created_date, updated_date |
| `detection` (~660M) | oid, sid, measurement_id, mjd, ra, dec, band, created_date |
| `forced_photometry` (~1.5G) | same shape as `detection` |
| `probability` | oid, sid, classifier_id, classifier_version (**int2**, lossy), class_id, probability, ranking, lastmjd. Latest values only |
| `feature` | oid, sid, feature_id, band (band set: 12 = gr, 0 = none), version, **feature_value** (not `value`), updated_date |
| `magstat` | **ZTF rows only**. oid, sid, band, stellar, corrected, ndubious, dmdt_first, dm_first, sigmadm_first, dt_first, magmean, magmedian, magmax, magmin, magsigma, maglast, magfirst, and `*_corr` versions, step_id_corr, n_det, firstmjd, lastmjd, saturation_rate |
| `xmatch` | oid, sid, catid (0 = AllWISE, 1 = Gaia DR3), dist[arcsec], oid_catalog. Pipeline radius ~1″ |

### Feature families (`feature_name_lut`: 127 ZTF and 146 LSST names; ids differ per survey)
| family | names |
|---|---|
| periodicity | `Multiband_period`, `Period_band`, `PPE`, `delta_period`, `Power_rate_*`, `Harmonics_mag_1..7`, `Harmonics_phase_2..7`, `Harmonics_chi/mse` |
| variability stats | `Amplitude`, `PercentAmplitude`, `Std`, `Mean`, `Meanvariance`, `MedianAbsDev`, `Skew`, `SmallKurtosis`, `Beyond1Std`, `StetsonK`, `Eta_e`, `Q31`, `Rcs`, `Con`, `Autocor_length`, `LinearTrend`, `MaxSlope`, `PairSlopeTrend`, `AndersonDarling`, `Gskew`, `Psi_CS`, `Psi_eta` |
| stochastic / AGN | `ExcessVar`, `Pvar`, `GP_DRW_sigma`, `GP_DRW_tau`, `SF_ML_amplitude`, `SF_ML_gamma`, `IAR_phi`, `MHPS_*` |
| transient models | `SPM_A, SPM_beta, SPM_t0, SPM_gamma, SPM_tau_rise, SPM_tau_fall, SPM_chi`, `fleet_a/w/m0/t0/chi`, `TDE_mag0/decay/decay_chi`, `ulens_t0/tE/u0/fs/mag0/chi` |
| forced-phot context | `dbrightness_first_det_band`, `dbrightness_forced_phot_band`, `max/median_brightness_before/after_band`, `last_brightness_before_band`, `n_forced_phot_band_before/after`, `positive_fraction` |
| colours | `g-r_max/mean(_corr)` (LSST also `u-g`, `r-i`, `i-z`, `z-y`), `<band>-W1..W4`, `W1-W2`, `W2-W3`, `W3-W4`; ZTF `ps_g-r`, `ps_r-i`, `ps_i-z` |
| context | `Coordinate_x/y/z`, ZTF: `sgscore1`, `distpsnr1`, `mean_distnr`, `sigma_distnr`, `mean_sharpnr`, `mean_chinr` |

## Lookup tables (small; load once)
| table | columns |
|---|---|
| `sid_lut` | sid, tid, survey_name (ZTF / LSST DIA Object / LSST SS Object) |
| `band` | sid, tid, band, band_name, band_order |
| `classifier` | classifier_id, classifier_name, classifier_version (**dotted text**), tid |
| `taxonomy` | class_id, class_name, taxonomy_order, classifier_id. Class ids are **per classifier** |
| `feature_name_lut` | feature_id, feature_name, sid, tid. Ids **differ per survey** |
| `feature_version_lut` | version_id, version_name (e.g. `27.5.7a31.dev1`), sid, tid |
| `catalog_id_lut` | catid, catalog_name |

## ZTF extension tables (no `sid`; join on `oid` [+ `measurement_id`])
| table | columns |
|---|---|
| `ztf_object` | oid, g_r_max, g_r_max_corr, g_r_mean, g_r_mean_corr, corrected, stellar, reference_change, diffpos, ndethist, ncovhist, mjdstarthist, mjdendhist |
| `ztf_detection` | oid, measurement_id (= candid), pid, diffmaglim, isdiffpos, nid, magpsf, sigmapsf, magap, sigmagap, distnr["], rb, rbversion, drb, drbversion, magapbig, sigmagapbig, rfid, magpsf_corr, sigmapsf_corr, sigmapsf_corr_ext, corrected, dubious, parent_candid, has_stamp |
| `ztf_forced_photometry` | oid, measurement_id (= pid), pid, mag, e_mag, mag_corr, e_mag_corr, e_mag_corr_ext, isdiffpos, corrected, dubious, parent_candid, field, rcid, rfid, sciinpseeing, scibckgnd, scisigpix, magzpsci(unc,rms), clrcoeff, clrcounc, exptime, adpctdif1/2, diffmaglim, programid, procstatus, distnr, ranr, decnr, magnr, sigmagnr, chinr, sharpnr |
| `ztf_non_detection` | oid, band, mjd, diffmaglim (5σ) |
| `ztf_ps1` | oid, measurement_id, objectidps1..3, sgmag/srmag/simag/szmag 1..3, **sgscore1..3** (star-galaxy, 1 = star), **distpsnr1..3**["], nmtchps |
| `ztf_gaia` | oid, measurement_id, neargaia["], neargaiabright, maggaia, maggaiabright |
| `ztf_ss` | oid, measurement_id, ssdistnr["] (−999 = none), ssmagnr, ssnamenr ('null' = none) |
| `ztf_reference` | oid, rfid, measurement_id, band, rcid, field, magnr, sigmagnr, chinr, sharpnr, ranr, decnr, mjdstartref, mjdendref, nframesref |
| `ztf_dataquality` | oid, measurement_id, xpos, ypos, fwhm, classtar, mindtoedge, seeratio, nneg, nbad, magzpsci, exptime, … |

## LSST extension tables (have `sid`; join on `oid, sid, measurement_id`)
| table | columns |
|---|---|
| `lsst_detection` (102 cols) | oid, sid, measurement_id (= diaSourceId), visit, detector, diaobjectid, ssobjectid, ra/dec errors, x, y, apflux(err), isnegative, snr, **psfflux, psffluxerr** [nJy, difference], **scienceflux, sciencefluxerr** [nJy, direct], psfchi2, trail*, dipole*, templateflux, extendedness, **reliability**, pixelflags_*, has_stamp, … |
| `lsst_forced_photometry` | oid, sid, measurement_id, visit, detector, psfflux, psffluxerr, scienceflux, sciencefluxerr, timeprocessedmjdtai, timewithdrawnmjdtai |
| `lsst_dia_object` (83 cols) | oid, validitystartmjdtai, ra, dec (+ errors), and per band u..y: `<b>_psffluxmean(err)`, `<b>_psffluxsigma`, `<b>_psffluxndata`, `<b>_fpfluxmean(err)`, `<b>_sciencefluxmean`, …, ndiasources |
| `lsst_ss_detection` | measurement_id, ssobjectid, designation, ecliptic/galactic coords, elongation, phaseangle, topo/helio ranges and vectors, ephemeris offsets. Helio/topo distances not filled yet |
| `lsst_ss_object` | (81 cols: H, G12 per band, MOID, Tisserand…) **currently empty** |
| `lsst_mpc_orbits` | ssobjectid, designation, a[AU], q, e, i, node, argperi, peri_time, mean_anomaly, period, uncertainties, … |

**There is no LSST non-detection table and no LSST magstat.**

## External catalogs (joined via `xmatch`)
- `allwise`: oid_catalog, ra, dec, w1mpro..w4mpro, w1sigmpro..w4sigmpro, j_m_2mass, h_m_2mass, k_m_2mass (+ sig).
- `gaiadr3_source` (52 cols): oid_catalog, ra, dec, parallax(_error), pm, pmra, pmdec, ruwe, phot_g/bp/rp_mean_mag, bp_rp, radial_velocity, phot_variable_flag, in_qso_candidates, in_galaxy_candidates, non_single_star, classprob_dsc_combmod_quasar/galaxy/star, …

## Legacy schema `ztf.*` (ZTF only, oid = ZTF name), live and updated daily
16 tables: `object, detection, forced_photometry, non_detection, magstat, probability, xmatch, allwise, gaia_ztf, ss_ztf, ps1_ztf, reference, dataquality, taxonomy, feature_version, feature`. ALeRCE's official ZTF use-case notebooks use this schema.

| legacy `ztf.*` | `alerce_tap` |
|---|---|
| `oid = 'ZTF26aaonmha'` (string) | integer oid (`ztf_name_to_oid`) + `sid = 0` |
| `ndet`, `deltajd`, `fid`, `candid` | `n_det`, `deltamjd`, `band`, `measurement_id` |
| `ps1_ztf`, `ss_ztf`, `gaia_ztf` | `ztf_ps1`, `ztf_ss`, `ztf_gaia` |
| `feature(oid, name, value, fid, version)`; quote `"value"`; NaNs and **all versions** kept | `feature(oid, sid, feature_id, band, version, feature_value)`, latest only, no NaNs |
| `probability(oid, classifier_name, classifier_version text, class_name, probability, ranking)` | ids + LUTs; `classifier_version` int2 |
| `taxonomy.classes` (array column: request CSV, pyvo's VOTable parser fails) | `taxonomy` one row per class |

`ztf.probability` keeps **several classifier generations side by side**. For ZTF26aaonmha on 2026-11-19 it held:
- `lc_classifier` (`lc_classifier_1.1.13`);
- `LC_classifier_ATAT_forced_phot(beta)` 1.0.0;
- `lc_classifier_BHRF_forced_phot` and its branches **2.1.0**, while `alerce_tap` serves 2.2.0;
- `stamp_classifier` (`stamp_classifier_1.0.4`);
- `stamp_classifier_2025_beta` (`2.1.1_beta`).

Filter on `classifier_version` (text) to pick one. Use `ztf.*` when porting an official notebook, or when you need ATAT or the legacy classifiers or feature versions. Otherwise prefer `alerce_tap`, which covers both surveys.
