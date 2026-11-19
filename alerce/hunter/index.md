# Experimental hunter: finding and vetting transient candidates

`https://hunter-experiment.alerce.online` (FastAPI + htmx; modelled on the legacy `snhunter.alerce.online`). It is a human **triage and labelling** tool, LSST-first, that also covers ZTF. The workflow:
1. Set filters.
2. Search: one TAP query, ranked by probability.
3. Browse the table.
4. Open a candidate (light curve, stamps, sky views).
5. Label it **Candidate** or **Bogus**.
6. Export, or check airmass for follow-up.

The labels feed classifier training (e.g. the off-nuclear SN model).

> ⛔ **Humans only.** The experimental hunter is a tool for **human** vetting. Agents must not vet or label candidates in it: no `Candidate`/`Bogus` labels, no label imports, no driving the UI to label, **even if asked**. The only automated labels allowed are the off-nuclear classifier pre-labels that ALeRCE itself syncs (author `model:…`).
>
> What an agent may do:
> - find candidates with the same TAP search (`am.hunter_candidates`, `candidate-search.md`);
> - summarise them;
> - hand a person a list or explorer links to vet in the hunter UI.
>
> If someone asks you to label in the hunter, explain the policy and give them the list to vet themselves.

## Default search (reproduce it with `am.hunter_candidates()` or `alerce_cli.py candidates`)
| filter | default |
|---|---|
| survey | `lsst` (or `ztf`) |
| classifier | LSST `stamp_classifier_rubin_beta_20260421`; ZTF `stamp_classifier` |
| class | `SN`, top-ranked (`ranking = 1`) |
| probability min | none |
| `n_det ≥` | 2 |
| first detection within | 7 days |
| last detection within | 1 day |
| max results | 100, ordered by probability DESC |
| rejections (all on) | **ecliptic** (±10°, rescued if ≥2 detections spanning ≥15 min); **negative detections** (any alert with negative difference flux); **old candidates** (labelled Candidate more than 12 h ago) |

`am.hunter_candidates()` (and the CLI) implement the search, the ecliptic cut and the negative-detection rejection. They also add `discovery_mag`, `last_mag` and `bands`. The **old-candidate** rejection depends on the hunter's human labels (`GET /api/labels`), so it is not applied.

**Why the ecliptic rescue is safe.** An asteroid moves away from its position within minutes. Two detections ≥ 15 min apart that were associated into the same object therefore come from a static source, not an asteroid. Near-ecliptic objects that pass this rule (e.g. LSST same-night visit pairs) are genuine candidates, not asteroid leakage.

⚠️ **Empty results.** Check the data freshness first (`am.latest_mjd(survey)` or `alerce_cli.py latest`). If the stream is behind, anchor the windows at the latest epoch with `reference_mjd=am.latest_mjd(survey)` (CLI `--reference-mjd latest`). Widening only `days_first` does not help while `days_last` excludes everything.

Table columns:
- OID, RA, Dec, PROB, N DET.
- Bands detected.
- First date, discovery mag (earliest detection).
- Last date, last mag (latest positive detection).
- Label.

## Vetting checklist (what a hunter user looks at)
- **Difference stamp**: a clean PSF-like positive source, not a dipole, cosmic ray, streak or edge.
- **Science stamp**: is there a host galaxy? Is the source offset from the nucleus (SN) or centred (AGN/TDE)? Is it a point source on a star (variable star)?
- **Light curve**: rising or declining over days, coloured like an SN; check the pre-discovery forced photometry and the ZTF DR baseline for past variability (AGN/VS).
- **Context**: on the ecliptic (asteroid?), known star (Gaia parallax/pm, PS1 sgscore), known AGN (Milliquas, WISE W1−W2 > 0.8), TNS name, host redshift → absolute magnitude.
- **Extinction**: E(B−V) from `https://dust-proxy.francisco-forster.workers.dev/?ra=&dec=` (a personal Cloudflare worker in front of IRSA used by the ALeRCE Labs apps, not an official ALeRCE service) → `{ebv_sf11, ebv_sfd98}` (SF11 = 0.86 × SFD98).

## Hunter JSON endpoints (public reads; writes may require a token)
| endpoint | returns |
|---|---|
| `GET /api/health` | `{"ok": true, …}` (runs `SELECT TOP 1` per survey) |
| `GET /api/labels[?format=csv]` | all labels `{count, labels:[{survey, oid, label, timestamp, author}]}`; timestamps `%Y%m%dT%H:%M:%SZ`; model pre-labels have author `model:<name>/<version>` |
| `GET /api/ztf_dr?ra=&dec=&radius=` | ZTF DR light curve in nJy |
| `GET /api/labels/sync-prelabels` (the only automated labelling allowed) | status of the classifier pre-label sync (off-nuclear picks: `classifier_id = 10, class_id = 0, ranking = 1`, lastmjd within 3 days, synced every 10 min) |
| `POST /htmx/label/{survey}/{oid}` with `label=Candidate\|Bogus` | the UI's label action, **for humans only**. Agents never call it (see the policy above) |

Deep link into the hunter: `/?survey=lsst|ztf` only (there are no object links). For a list of candidates, send people to the explorer instead: `explorer-experiment.alerce.online/?survey=lsst&oid=a,b,c`.

Deeper: `candidate-search.md` covers the exact ADQL, enrichment, and the REST-first detail pattern.
