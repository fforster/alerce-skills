# Science workflows: routing

These playbooks are distilled from the IUCAA 2026 ALeRCE multisurvey tutorial ([github.com/fforster/alerce-iucaa-2026](https://github.com/fforster/alerce-iucaa-2026)) and the experimental hunter. The guiding objects are all in COSMOS:

| object | ZTF | LSST diaObjectId(s) |
|---|---|---|
| SN 2026gzf (SN Ic-BL) | `ZTF26aaonmha` | `314003014107006318` |
| quasar (z ≈ 1.48) | `ZTF20acyxpwi` | `313985345706262538` |
| RR Lyrae (P = 0.48888 d) | `ZTF17aabhbva` | `313888627082919999`, `313893021775560722` (split) |

| Task | Read |
|---|---|
| supernovae: find, vet, host, redshift, absolute magnitude, samples | `supernovae.md` |
| AGN / quasars: identification, WISE/Gaia, variability features, structure function | `agn.md` |
| periodic variables: periods, aliases, folding, Bailey diagram | `variable-stars.md` |
| the same source in ZTF and LSST: matching, combining light curves, comparing classifiers | `cross-survey.md` |
| asteroids and other moving objects: LSST sid 2, MPC orbits, ZTF known-asteroid matches | `solar-system.md` |
| microlensing events: selection, Paczyński features, quality cuts | `microlensing.md` |
| complete ADQL workflows for SN, AGN, variables, solar system (both surveys) | `../tap/examples.md` |

## General lessons
1. **A classification depends on the data the model saw.** Check `lastmjd`. Stamp classes are a fast first guess; light-curve classes (ZTF BHRF) are more reliable.
2. **Use forced photometry** for variables and for pre-discovery limits. Alert detections are biased toward bright epochs.
3. **Features are computed automatically from whatever light curve existed at that moment.** Check that the data can constrain them (baseline vs timescale, number of points, aliases).
4. **Combining surveys** gives more than either alone: ZTF has a long baseline (2018 onward plus DR), LSST is deeper with ugrizy.
5. **Always check your data**: units, sentinels (100), duplicate objects, TAI vs UTC, catalog unit bugs.
6. Samples: select with **one TAP query**, fetch everything else in **batched** TAP queries, and keep the results (cache, parquet). Precompute anything that needs hundreds of requests.

## Official ALeRCE use-case notebooks
github.com/alercebroker/usecases holds ALeRCE's own tutorials. Reviewed on 2026-11-19:
- **`notebooks/LSST/`** (Tables, TAP_Queries, Client_Queries, SSO, ZTF; updated Nov 2026) and its helper module `lib_multisurvey/alerce_multisurvey_tools.py` (stamp grids, single- and two-panel ZTF+LSST light curves, absolute magnitudes, folding). These are current; read in that order.
- **`notebooks/ZTF/`**: starters for SN, AGN, variable stars, asteroids and microlensing, plus fast SNe, periodograms, watchlists, the ML classifiers, stamp animation, AVRO pixel checks and external-catalog crossmatch. They were moved from direct SQL to TAP in June 2026 but still use the **legacy** `ztf.*` schema, the legacy client and the 2021 `lc_classifier`.
- **`notebooks/Meetings/`**: workshop copies (2020–2026). Many use the retired direct-SQL access with credentials files; don't reuse those parts.

### Porting a use-case notebook to the current services
| in the notebooks | today |
|---|---|
| `Alerce()` without `survey=` | `Alerce(ztf_backend="multisurvey")`, always `survey="ztf"` or `"lsst"` (`../client/index.md`) |
| `classifier="lc_classifier"`, `class_name="SNIa"` | `lc_classifier_BHRF_forced_phot` (multisurvey); classes in `../classifiers/index.md` |
| `first_mjd=[min, None]` | **silently ignored** by the legacy API: use `firstmjd` |
| `ztf.object`, `ztf.probability`, `ztf.feature`, `ps1_ztf`, `ss_ztf` (oid = name, `ndet`, `fid`, `"value"`) | `alerce_tap.object`… with `sid = 0`, integer oids, `n_det`, `band`, `feature_value`, `ztf_ps1`, `ztf_ss` (`../tap/schema.md`) |
| `tap.search(q)` / `maxrec=10_000_000` without `TOP` | `TOP N` + explicit `maxrec` |
| psycopg2 + `alercereaduser*.json` credentials | retired: use TAP |
| one TAP cone per watchlist row | one upload crossmatch: `am.upload_crossmatch` |
| `api.alerce.online/forecast/v1/parametric/sn` | gone (404). Evaluate the SPM model locally (`supernovae.md`) |

## Feature-similarity search
The IAU GA 2024 notebook (`notebooks/Meetings/IAU_GA_2024/`) finds look-alike objects with a nearest-neighbour index on the light-curve features:
1. Get the features: the Zenodo release of all ZTF features to 2024-05-03 (doi:10.5281/zenodo.11123894), or TAP for a current sample.
2. Scale them with `QuantileTransformer`.
3. Index them with `faiss.IndexFlatL2` (`pip install faiss-cpu`) and query k = 200 neighbours of an example object.
4. Open the neighbours as an explorer list link.

The ZTF training set of Sánchez-Sáez+2021 is at doi:10.5281/zenodo.4279623.
