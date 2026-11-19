# Explorers: deep links and JSON endpoints

Give a human a link whenever they should look at objects. Agents rarely need to scrape the page; the data behind it comes from the REST/TAP calls described elsewhere.

## Experimental explorer (ALeRCE Labs): `https://explorer-experiment.alerce.online`
This is a FastAPI + htmx rewrite showing **ZTF and LSST together**. Features:
- Light curve with flux/mag, difference/science, apparent/absolute (Planck18) and dereddened (SF11 E(B−V), Fitzpatrick99) views. It overlays forced photometry, the other survey's counterpart (3″), ZTF DR photometry, model fits (SPM, FLEET, TDE tail) and a GP fit.
- Stamps rotated North-up, Aladin sky view and a classifier radar.
- Periodogram and phase folding, airmass, and the ZTF AVRO packet viewer.
- catsHTM + CDS/NED crossmatch with host redshift, TNS info, a nearby-LSST "mover" check, and CSV export.

### URL grammar
| Goal | URL |
|---|---|
| one object | `/?survey=ztf&oid=ZTF26aaonmha` · `/?survey=lsst&oid=314003014107006318` |
| one object, preselect a detection's stamps | `…&identifier=<candid or measurement_id>` |
| a list (kept in the order given; ≤ 200 oids per link) | `/?survey=lsst&oid=313888627082919999,313893021775560722` |
| survey omitted | guessed from the id: `^ZTF\d{2}[a-z]+$` means ztf, all digits means lsst |
| old style | `/object/{oid}` redirects (302) to `/?survey=…&oid=…`, keeping the query |
| run a search | `/?survey=lsst&classifier=stamp_classifier_rubin_beta_20260421&class_name=SN&probability=0.5&n_det_min=2&firstmjd_min=61350&lastmjd_min=61360&page=1` |
| cone search | `/?survey=ztf&ra=149.9287&dec=0.4184&radius=30` (radius in arcsec) |

Accepted search parameters: `classifier, classifier_version, class_name, probability, n_det_min, n_det_max, firstmjd_min, firstmjd_max, lastmjd_min, lastmjd_max, ra, dec, radius, oids, page, identifier`. Dates are MJD floats.

### JSON endpoints (small server: call sparingly)
| endpoint | returns |
|---|---|
| `GET /api/health` | `{"status":"ok"}` |
| `GET /api/ztf_dr?ra=&dec=&radius=` | ZTF DR light curve in nJy (radius ≤ 60″) |
| `GET /api/lsst_neighbors?ra=&dec=&lastmjd=&exclude_oid=` | LSST detections near a position and time (movers, trails) |
| `GET /api/xmatch_overlay?oid=&survey_id=` | the explorer's catalog crossmatch (SIMBAD, NED, VizieR catalogs) for an object |
| `GET /api/stamp_center?survey=&oid=&candid=` | sky position of a stamp's centre |

Prefer computing the crossmatch yourself with `alerce_ms.catalog_xmatch(ra, dec)`. It uses the same catalogs, radii and cuts, queried directly, which keeps load off the explorer.

## Production explorers
| site | URL forms |
|---|---|
| Multisurvey explorer | `https://lsst.alerce.online/object/{oid}?survey=ztf\|lsst`; list: `https://lsst.alerce.online/?survey=lsst&oid=a,b,c` (add `&classifier=…&page=1` to show a classifier's column; ≤ 200 oids) |
| Legacy ZTF explorer | `https://alerce.online/object/ZTF26aaonmha`; list: `https://alerce.online/?oid=A&oid=B&selectedClassifier=stamp_classifier&ranking=1&count=false&page=1&perPage=20` |

## Helpers
```python
am.explorer_url("ZTF26aaonmha", "ztf")                  # experimental explorer
am.explorer_url(oid, "lsst", site="alerce")             # lsst.alerce.online
am.explorer_list_urls(list_of_oids, "lsst")             # both explorers, whole list
```
CLI: `python scripts/alerce_cli.py link ZTF26aaonmha ZTF20acyxpwi`.

When reporting objects to a user, give a markdown table with a link column. Pass ZTF ids as **names**, not integer oids.
