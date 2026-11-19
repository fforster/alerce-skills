# Crossmatch: what is this object next to?

## ⚠️ Choose by sample size first
Crossmatches come in two kinds that scale very differently:
- **Stored in the ALeRCE database.** Precomputed counterparts, queried in bulk through TAP. Use these for any sample size.
- **External services queried per object.** Each object costs one or more HTTP calls to someone else's server. Use these only for small samples.

| sample size | use | cost (measured 2026-11-19) |
|---|---|---|
| **any size: your own catalog → ALeRCE objects** | **spatial TAP upload**: `am.upload_crossmatch(ra, dec, radius_arcsec, sid=…)` (chunks of 2,000 positions, `tap_upload` join on `alerce_tap.object`) | **500 positions in ~3 s**. Don't add `WHERE o.sid` to the SQL (minutes); filter afterwards. Returns one row per (position, object) pair, with `src` = the 0-based row of your input; positions with no object are absent |
| **any size: hundreds to millions** | **In-DB tables via TAP only**: `xmatch` + `allwise` + `gaiadr3_source` (~1″ matches), and for ZTF `ztf_ps1`, `ztf_gaia`, `ztf_ss`. One query per chunk of ≤1000–5000 oids (`oid IN (…)`), never one per object | `xmatch` for **500 objects in one query: 4.4 s**. `ztf_ps1` for the same 500: 18 s and 43,581 rows (one row per alert), so keep one row per object (e.g. the first detection) |
| **small: up to a few hundred** | catsHTM (`am.catshtm_crossmatch`) or REST `crossmatch_api` (same catsHTM, 20″), serially, cached | **~1 s per object**: 100 objects ≈ 2 min, 1,000 ≈ 15–20 min (the upper limit of reasonable) |
| **very small: one to a few tens** | the explorer recipe `am.catalog_xmatch` / `am.object_xmatch` (SIMBAD + NED + ~20 VizieR catalogs: host redshifts, AGN and star catalogs), the TNS bridge, the dust proxy | **10–30 s per object**, and it depends on CDS being up: 30 objects ≈ 10 min; 1,000 objects ≈ 4–9 h plus rate limits. **Don't** |
| large sample that really needs an external catalog (e.g. spec-z for 10,000 hosts) | **one bulk job on the catalog's side**, not N cone searches: CDS XMatch (`astroquery.xmatch.XMatch.query` with an uploaded table of positions), or the catalog's own TAP service with a table upload (SIMBAD TAP accepts `TAP_UPLOAD`), or download the catalog region | one request per sample; check the service's upload limits. CDS XMatch has no mirror, so plan for outages |

Rules:
0. **What you send is seen.** Uploads and per-object queries send your positions or ids to the service (ALeRCE, CDS, NED, the dust proxy), which may log them. Ask the user before sending a confidential target list.
1. **Start with the in-DB tables.** They answer "is it a star / an AGN / near a Gaia source" for any sample size.
2. **Get the positions with one TAP query** (or upload your own list: `am.upload_crossmatch`) (`object.meanra, meandec … WHERE oid IN (…)`) before any external crossmatch.
3. **Never loop an external per-object service over a large sample.** It takes hours, overloads shared services (ALeRCE's are rate-limited per IP; CDS and NED are too) and fails partway through. Narrow the sample first (classifier, recency, in-DB cuts), or use a bulk upload.
4. **Cache external results** (`alerce_ms` caches to disk) and run them **serially or with ≤ 8 parallel requests**, like the explorer.

## Sources by need

| Need | Source | How |
|---|---|---|
| WISE colours, Gaia parallax/pm/variability for ALeRCE objects (**any sample size**) | **in-DB `xmatch`** (AllWISE and Gaia DR3; get `catid` from `catalog_id_lut`, currently 0 and 1; radius ~1″). `am.get_xmatch` returns one row per matched catalog; columns of the other catalog are NaN | TAP: `../tap/recipes.md#stored-crossmatch-allwise-gaia-dr3` · `am.get_xmatch(oid, sid)` |
| Nearest source in ~15 catalogs, one call (**per object, small samples**) | **catsHTM** `https://catshtm.alerce.online/crossmatch_all?ra=&dec=&radius=` (arcsec) | `am.catshtm_crossmatch(ra, dec, 5)`; REST twin `crossmatch_api/crossmatch?oid&survey_id` uses a fixed 20″ |
| Stars, AGN and host-galaxy redshifts (the **explorer's** recipe; **per object, very small samples**) | SIMBAD TAP + NED TAP + VizieR | `am.catalog_xmatch(ra, dec)` or `am.object_xmatch(oid, survey)` |
| Is it a known transient? (**per object**) | TNS | ALeRCE bridge `api.alerce.online/v2/object_details/htmx/tns/?ra=&dec=` (HTML; see `../api/legacy-ztf.md`) |
| ZTF-only quick hints (**any sample size**, in-DB) | `ztf_ps1` (sgscore, distpsnr), `ztf_gaia`, `ztf_ss` (known asteroid), `distnr` | TAP |

## The explorer's catalog recipe (reproduced in `alerce_ms.catalog_xmatch`)
| category | catalogs (VizieR id) | radius | cut |
|---|---|---|---|
| stellar | Gaia DR3 `I/355/gaiadr3`, VSX `B/vsx/vsx` | 3″ | the transient *is* the star |
| agn | Milliquas `VII/294/catalog`, Véron-Cetty `VII/258/vv10`, SDSS DR16Q `VII/289/dr16q` | 3″ (DR16Q 36″) | |
| host | SDSS DR16 `V/154/sdss16` (galaxies, zsp), DESI DR1 `V/161/zcatdr1` (ZWARN = 0, no stars) | 30″ | needs a redshift |
| host z-catalogs | 6dFGS, GAMA DR4, 2MRS, WiggleZ, zCOSMOS, VIPERS, OzDES, 2dFGRS, GLADE v2, HECATE | 36″ | quality flags (q_z ≥ 3, etc.) |
| host | HyperLEDA `VII/237/pgc` | 60″ | |
| any | SIMBAD (otype → stellar/agn/host), NED (`NEDTAP.objdir`) | 36″ | catalogued SNe are dropped as "hosts" |

Endpoints:
- SIMBAD TAP: `https://simbad.cds.unistra.fr/simbad/sim-tap/sync`, mirrors `simbad.idia.ac.za`, `simbad.cfa.harvard.edu`.
- NED TAP: `https://ned.ipac.caltech.edu/tap/sync`. It drops connections; retry.
- VizieR: `vizier.cds.unistra.fr`, mirrors `vizier.idia.ac.za`, `vizier.cfa.harvard.edu`.

## Robustness (CDS outages are real: Nov 2026)
- CDS services (SIMBAD, VizieR, XMatch, Sesame, Aladin/alasky, hips2fits) failed at the TCP level, so calls **hang** rather than error. Use short timeouts (10–30 s) and fall through to the mirrors. `am.simbad_tap` and `am.vizier_query_region` remember dead servers.
- No mirror exists for CDS XMatch, VizieR TAP, hips2fits or Sesame. Degrade gracefully and report which services did not answer. `catalog_xmatch` prints "Not answered (try again later): …" and does not cache partial answers.
- The explorer limits itself to 8 parallel CDS/NED requests with a 30 s deadline per catalog. Do the same.

## Interpretation tips
- **AGN**: Milliquas/Véron match, or WISE `W1−W2 > 0.8` (Vega). Gaia `in_qso_candidates`, or a high `classprob_dsc_combmod_quasar`.
- **Star**: significant Gaia parallax or proper motion; PS1 `sgscore1 > 0.5` within 1″; VSX type gives the variable class.
- **Host redshift**: prefer spectroscopic z from DESI/SDSS/NED. Then `M = m − 5 log10(d_L/10 pc) − A_λ`, with E(B−V) from the dust proxy (`https://dust-proxy.francisco-forster.workers.dev/?ra=&dec=` → `ebv_sf11`).
- **catsHTM caveats**: XMM coordinates come back in **radians** although labelled degrees. Units for every column are in the response (`{"unit","value"}`).
