# Classifiers and probabilities (live, verified 2026-11-18)

**Every model is still "beta". Never hard-code ids;** look them up by name in TAP `classifier`/`taxonomy` or REST `classifier_api/classifiers`. Classifier names have changed before (e.g. `stamp_classifier_ztf` → `stamp_classifier`), and class ids are per classifier.

| id | classifier_name | version | survey | classes (class_id) | input |
|---|---|---|---|---|---|
| 1 | `stamp_classifier_rubin_beta` | 2.0.1 | LSST | SN 0, AGN 1, VS 2, asteroid 3, bogus 4 | first-alert stamps + metadata |
| 3 | `stamp_classifier_rubin_beta_20260421` | 2.0.2 | LSST (**default**) | same 5 classes | first-alert stamps |
| 10 | `stamp_sn_offnuclear_rubin_beta` | 0.0.1 | LSST | SNoffnuclear 0, notSNoffnuclear 1 | stamps; flags SNe offset from host nucleus |
| 4 | `stamp_classifier` | 1.0.4 | ZTF (**default stamp**) | SN 0, AGN 1, VS 2, asteroid 3, bogus 4, satellite 5 | first-alert stamps |
| 2 | `stamp_classifier_2025_beta` | 2.1.1 | ZTF | same 6 classes | first-alert stamps |
| 5 | `lc_classifier_BHRF_forced_phot` | 2.2.0 | ZTF (**use for science**) | flat 21 classes: SNIa 18, SESN 14, SNII 16, SNIIn 17, SLSN 15, TDE 19, Microlensing 8, QSO 10, AGN 0, Blazar 1, YSO 20, CV/Nova 3, LPV 7, EA 5, EB/EW 6, Periodic-Other 9, RSCVn 13, CEP 2, RRLab 11, RRLc 12, DSCT 4 | light curve (incl. forced photometry) features |
| 6 | `lc_classifier_BHRF_forced_phot_top` | 2.2.0 | ZTF | Periodic 0, Stochastic 1, Transient 2 | |
| 7 | `lc_classifier_BHRF_forced_phot_transient` | 2.2.0 | ZTF | SESN 0, SLSN 1, SNII 2, SNIIn 3, SNIa 4, TDE 5 | |
| 8 | `lc_classifier_BHRF_forced_phot_stochastic` | 2.2.0 | ZTF | AGN 0, Blazar 1, CV/Nova 2, Microlensing 3, QSO 4, YSO 5 | |
| 9 | `lc_classifier_BHRF_forced_phot_periodic` | 2.2.0 | ZTF | CEP 0, DSCT 1, EA 2, EB/EW 3, LPV 4, Periodic-Other 5, RRLab 6, RRLc 7, RSCVn 8 | |

There is **no LSST light-curve classifier yet**. The legacy API also carries `lc_classifier` (15-class BHRF, Sánchez-Sáez+2021) and ATAT (`LC_classifier_ATAT_forced_phot(beta)`); see `../api/legacy-ztf.md`. Nicknames you may meet: BHRF forced-phot 2.2.0 is "Squidward" (in production since 19 Oct 2026); ATAT is "Mbappe".

## How to read the probabilities
- `ranking = 1` is the top class of that classifier. Probabilities are the **latest** prediction only; `probability.lastmjd` says which data the model saw.
- **Hierarchy**: branch classifiers (`_transient/_stochastic/_periodic`) run on every object and are **conditional** on the branch. `P(SNIa) = P_top(Transient) × P_transient(SNIa | Transient)`. **Never read a branch classifier's top class on its own.** Use the flat `lc_classifier_BHRF_forced_phot` or multiply.
- **Stamp classifiers** see only the first alert's image triplet. They are good for early triage (SN vs AGN vs VS vs asteroid vs bogus) and blind to the later light curve. Known failure modes:
  - The LSST stamp model tags quasars as VS.
  - It classified a pre-explosion host-nucleus detection as bogus/AGN.
  - Many LSST counterparts of real SNe get "asteroid".
- Thresholds are a trade-off. The hunter's default is "top class SN" with no probability cut, followed by human vetting. For science samples the tutorial used `p > 0.8`.

## Versions: REST vs TAP spelling
| source | `classifier_version` |
|---|---|
| TAP `classifier.classifier_version` | dotted text `2.0.2` |
| TAP `probability.classifier_version` | int2 `202` (lossy) |
| REST `list_objects` | `"2.0.2"` |
| REST `probability_api` | int `202`; ZTF may also list historical versions (e.g. BHRF 1.0.7 … 1.1.5) |
| legacy ZTF API | strings like `stamp_classifier_1.0.4` or `hierarchical_random_forest_1.0.0` |

To compare versions, match exactly first, then by digits only (what the hunter does). The legacy ZTF API matches only its own spelling (`classifier_version=stamp_classifier_1.0.4`); a dotted `1.0.4` silently returns 0 rows.

## Recipes
- REST: `GET https://api-lsst.alerce.online/probability_api/probability?oid=ZTF26aaonmha&survey_id=ztf[&classifier=lc_classifier_BHRF_forced_phot]`
- TAP: see `../tap/recipes.md#probabilities`.
- Python: `am.api_probabilities(oid, survey)` (REST) or `am.get_probabilities(oid, sid, classifier)` (TAP, decoded).
