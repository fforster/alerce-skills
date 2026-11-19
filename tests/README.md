# Claim tests for the `alerce` skill

These tests check that what the skill tells an agent is still true. They also flag the day ALeRCE changes.

```bash
pip install -r requirements-test.txt
pytest                                   # everything (~2 min, ~200 tests, a few hundred light requests)
pytest -m offline                        # no network: ids, units, doc structure, helper/CLI names
pytest -m "live and not drift"           # factual claims against the live services
pytest -m external                       # CDS / NED / dust proxy (outages here are common, not our bug)
pytest -m drift                          # what changed since tests/baselines/*.json?
pytest -m examples                       # run all 69 workflow queries of tap/examples.md (~1 min, opt-in)
python tools/build_schema_refs.py        # regenerate tap/{indexes-and-joins,columns,examples}.md from the book
python tools/build_diagram.py            # regenerate the README skill map (also done by the pre-commit hook and CI)
```

## Layout
| file | checks |
|---|---|
| `test_offline.py` | name↔oid encoding, AB zero point, NaN mag for negative flux, band sets, ecliptic clause vs astropy, `check_skill.py`, every `am.<fn>` and `alerce_cli.py <cmd>` named in the docs exists |
| `test_api.py` | multisurvey REST claims (shapes, 404/422, `survey_id` default, radius units, per-classifier duplicates, version spellings, LSST non-detections, magstats), stamps (gzip, size, WCS, scale), legacy ZTF API quirks, ZTF DR, TNS bridge, AVRO |
| `test_tap.py` | 31 tables, LUTs, `feature_value`, `sid` columns, int2 versions, magstat ZTF-only, empty `lsst_ss_object`, XML errors, `IN ()`, maxrec behaviour, recipes (cone, light curves REST = TAP, xmatch LEFT join), feature ids per survey |
| `test_classifiers_sites_science.py` | documented classifiers exist, no LSST LC classifier, per-classifier class ids, BHRF hierarchy, explorer and hunter endpoints and deep links, hunter search, crossmatch, and the tutorial's science facts (SN counterpart, QSO W1−W2 and class, RR Lyrae period, LSST alias and split) |
| `test_client.py` | the official `alerce` client: backend/survey dispatch, exceptions, sub-client sessions, one row per classifier, dropped totals, id precision, version spellings, stamp return types, LSST Avro, catsHTM; drift on its public API and on PyPI releases |
| `test_schema_explorer.py` | the book's Schema Explorer content: generated files in sync with `alerce-book/explorer`, every live column in `columns.md`, indexed filters are fast, TAP index-flag snapshot, solar-system claims; `-m examples` runs the 69 workflow queries |
| `test_usecases_claims.py` | claims added or corrected after reviewing ALeRCE's official use-case notebooks: TAP_UPLOAD (id and spatial joins, the `oid` column trap), `_`-suffixed duplicate columns, quoted oid literals, stamp retention (LSST months, ZTF all epochs), solar-system objects over REST, the live legacy `ztf.*` schema, the retired forecast API |
| `test_doc_snippets.py` | runs every ```python block marked `# runnable` in the skill (microlensing, solar system, AGN samples), checks `get_features_many` against `get_features`, the LSST stamp-size wording and catalog lookup by name |
| `test_security.py` | cache files are only unpickled when private to the user, string values can't change ADQL, the router tells agents to treat service data as data, no secrets in the skill, the hunter is human-only (no labelling helpers) |
| `test_drift.py` | snapshots of classifiers, taxonomy, LUTs, TAP columns, feature names, REST endpoints/parameters/versions, legacy classifiers and light-curve fields; plus **docs vs live**: every live classifier and table is documented, documented versions, columns, endpoints and feature names exist |

Each test's docstring quotes the claim it checks and the skill file it comes from.

## When something fails
1. **A claim test fails**: the service changed or the skill is wrong. Fix the skill file named in the docstring, or the helper in `alerce/scripts/alerce_ms.py`, then fix the test's expectation.
2. **A drift test fails**: the message lists what was added, removed or changed. Update the affected skill files (e.g. a new classifier goes into `classifiers/index.md` and maybe `SKILL.md`), then accept the new state:
   ```bash
   pytest -m drift --update-baselines
   git diff tests/baselines              # review, then commit together with the doc changes
   ```
3. **An `external` test fails**: usually a CDS/NED outage. Re-run later before changing anything.

Some tests are designed to fail when a known gap closes, so the docs get updated:
- `test_no_lsst_light_curve_classifier`
- `test_lsst_ss_object_empty`
- `test_magstat_has_no_lsst_rows`
- `test_list_objects_radius_is_arcsec_and_rows_per_classifier`

A `.github/workflows/claim-tests.yml` workflow runs the suite weekly and on demand.
