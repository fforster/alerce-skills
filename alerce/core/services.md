# ALeRCE services, sites and the bundled helpers (verified 2026-11-18)

**Data access needs no authentication.** All data is public. Login (users.alerce.online, Google OAuth / JWT) is needed only for watchlists, reports and feedback.

## Data services
| Service | URL | Use |
|---|---|---|
| **Multisurvey REST API** (FastAPI) | `https://api-lsst.alerce.online/<name>_api/<endpoint>` | ZTF **and** LSST, one object at a time. Services: `object`, `lightcurve`, `probability`, `features`, `magstat`, `crossmatch`, `stamps`, `classifier`, `aladin`. Self-docs at `.../<name>_api/docs`. → `api/multisurvey.md` |
| **TAP** (GAVO DaCHS) | `https://tap.alerce.online/tap` (sync `/tap/sync`, async `/tap/async`) | ADQL over schema `alerce_tap` (31 tables, ZTF + LSST). Legacy schema `ztf` is ZTF only and keyed by name. Replaced direct SQL access (retired 2026). → `tap/index.md` |
| Legacy ZTF API (Flask) | `https://api.alerce.online/ztf/v1/...`, `/v2/...` | ZTF only. Still widely used; no retirement date. → `api/legacy-ztf.md` |
| ZTF Data Release light curves | `https://api.alerce.online/ztf/dr/v1/light_curve/?ra=&dec=&radius=` | Public ZTF DR photometry (radius in arcsec) |
| ZTF stamps & alert packets | `https://avro.alerce.online/get_stamp`, `/get_avro_info` | ZTF cutouts (gzip FITS, no WCS); AVRO packet JSON. About 8 req/s, 429 under load |
| catsHTM | `https://catshtm.alerce.online/crossmatch_all?ra=&dec=&radius=` | Nearest source in ~15 catalogs (2MASS, WISE, GALEX, XMM, SDSS, NED-z, Gaia, DECaLS…). → `crossmatch/index.md` |
| Python client | `pip install alerce` (v2.4.0, 2026-11-05) | `Alerce(ztf_backend="legacy"|"multisurvey")`, always with `survey=`. Wraps the REST APIs, stamps and catsHTM; no TAP, timeouts or retries. → `../client/index.md` |
| Kafka stream | per-classifier topics | On request only (not self-service) |
| Status page | https://status.alerce.online/ | Is a service down? Check here first when calls fail or hang |
| TAP Schema Explorer | https://claude.ai/artifact/JEpEyijsTpD1y83ut7Zia7#object (anchor = table name) | Interactive guide to every `alerce_tap` table, column, index and relation, with 8 science workflows; rebuilt daily (the skill's `tap/indexes-and-joins.md`, `tap/columns.md` and `tap/examples.md` are generated from it) |
| Multisurvey API Explorer | https://claude.ai/artifact/Bj9Jox1G6dBcsNAsBhtis8 | Every multisurvey REST endpoint with parameters and live examples |

## Web sites
| Site | URL |
|---|---|
| Experimental explorer (ALeRCE Labs): ZTF + LSST together, crossmatch, ZTF DR overlay | `https://explorer-experiment.alerce.online/?survey=ztf&oid=ZTF26aaonmha` → `explorer/index.md` |
| Multisurvey explorer (production) | `https://lsst.alerce.online/object/<oid>?survey=ztf\|lsst` |
| Legacy ZTF explorer | `https://alerce.online/object/<ZTF name>` |
| Experimental hunter (candidate triage + labelling) | `https://hunter-experiment.alerce.online` → `hunter/index.md` |
| Legacy SN Hunter, Watchlist, Reporter (ZTF only) | `snhunter.`, `watchlist.`, `reporter.alerce.online` |
| TOM (follow-up) | `tom.alerce.online` |

## Rate limits and etiquette
- All services are **rate-limited per IP** (HTTP 429). A classroom behind one NAT shares one quota, and bursts of requests can get an IP blocked.
- The APIs handle few concurrent requests well, so keep concurrency low. A REST call that runs longer than about 55 s is cut off (HTTP 504 "Query timed out").
- Recommended practice:
  - Cache everything.
  - Retry 429/502/503/504 with exponential backoff (5, 10, 20… s).
  - Batch (TAP `IN (...)` lists; REST `lightcurve_api` accepts up to ~200 repeated `oid`).
  - Run REST requests serially or with low concurrency; don't overlap TAP queries.
  - For prefetching, warm one object at a time.
- Measured latencies (Nov 2026): REST ~1 s per call; TAP ~4 s per query, growing when queries overlap.

## Bundled helper `scripts/alerce_ms.py` (import as `am`)
| Area | Functions |
|---|---|
| plumbing | `get_json(url, params)` (cache + retries), `api_get(service, endpoint, **params)`, `tap_query(adql, maxrec)`, `tap_tables()`, `tap_columns(table)`, `now_mjd()` |
| ids | `ztf_name_to_oid`, `oid_to_ztf_name`, `as_oid`, `display_name(oid, sid)` |
| lookups | `load_luts()`, `decode(df)` (adds survey/band/classifier/class/feature/catalog names), `classifier_id(name)`, `class_id(classifier, cls)`, `feature_ids(sid, names)`, `band_label(sid, band)` |
| one object (REST, fast) | `get_object(oid, survey)`, `api_lightcurve(oid, survey)`, `api_lightcurve_raw`, `api_non_detections`, `api_probabilities(oid, survey, classifier=None)`, `api_features(oid, survey, names=None)` |
| search | `list_objects(survey, **params)` (REST, paged, dedup), `hunter_candidates(...)` (TAP + batched enrichment, negative-flux rejection, `reference_mjd`), `candidate_enrichment(oids, survey)`, `ecliptic_keep_clause()`, `latest_mjd(survey)` (data freshness) |
| TAP per object | `get_lightcurve(oid, sid)`, `get_ztf_non_detections`, `get_features(oid, sid, names, wide)`, `get_probabilities(oid, sid, classifier)`, `get_magstats`, `get_xmatch(oid, sid)` |
| positions | `find_counterparts(ra, dec, radius_arcsec)` (REST, both surveys), `tap_cone(ra, dec, radius_arcsec, sid)`, `angular_sep_arcsec` |
| crossmatch | `catshtm_crossmatch(ra, dec, r)`, `catalog_xmatch(ra, dec)` (explorer recipe: SIMBAD, NED, VizieR), `object_xmatch(oid, survey)`, `simbad_query_region`, `simbad_tap`, `vizier_query_region` (mirrors) |
| stamps | `get_stamps(oid, sid, measurement_id, north=True)`, `plot_stamps`, `north_up`, `stamp_center`, `stamp_corners` |
| links | `explorer_url(oid, survey, site)`, `explorer_urls`, `explorer_list_urls(oids, survey)`, `show_link`, `show_table` (notebook) |
| plots | `plot_lightcurve(lc, flux='diff'\|'sci', mag=False)`, `plot_folded(lc, period)`, `sky_axes`/`sky_xy`, `BAND_COLORS` (Okabe-Ito: u #56B4E9, g #009E73, r #D55E00, i #E69F00, z #CC79A7, y #0072B2), ZTF = circles, LSST = squares, filled = detections, open = forced |

The cache lives in `~/.cache/alerce_skill`; override it with `ALERCE_CACHE`, or set `am.USE_CACHE = False`.
