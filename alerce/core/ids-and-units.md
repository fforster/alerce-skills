# Identifiers, bands, units and time

## Survey keys
| key | values | where |
|---|---|---|
| `sid` (survey id) | 0 = ZTF, 1 = LSST DIA object, 2 = LSST solar-system object | every per-object TAP table; **join on `(oid, sid)`** |
| `tid` (telescope id) | 0 = ZTF, 1 = Rubin | `object.tid`, `classifier.tid` |
| `survey_id` (REST) | `"ztf"` or `"lsst"` | every multisurvey REST call (anything else → HTTP 422) |

The idmapper prefix inside oids (ZTF = 1, ATLAS = 2, LSST = 3, LS4 = 4) is a different numbering. Do not confuse it with `sid`.

## Object ids
- **ZTF name**: `ZTF` + 2-digit year + 7 lowercase letters, e.g. `ZTF26aaonmha`. REST APIs, explorers and the hunter UI take names.
- **ZTF integer oid**, used in TAP `alerce_tap.*`: `(1 << 55) + yy*26**7 + base26(letters)`. Example: `ZTF26aaonmha ↔ 36029005852662990`.
  ```python
  def ztf_name_to_oid(name):
      year, letters = int(name[3:5]), name[5:12]
      seq = sum((ord(c) - ord("a")) * 26 ** (6 - i) for i, c in enumerate(letters))
      return (1 << 55) + year * 26 ** 7 + seq
  # inverse: alerce_ms.oid_to_ztf_name(oid)
  ```
  The legacy TAP schema `ztf.*` and the legacy API `api.alerce.online/ztf/v1` use the **name** as `oid`.
- **LSST oid** = Rubin `diaObjectId` (or `ssObjectId` for sid 2), an 18-digit integer such as `314003014107006318`. It is larger than 2^53:
  - pandas: read it as `Int64`/`int64`, never float.
  - JS: treat it as a string.
  - JSON parsers that turn numbers into doubles silently corrupt it. The explorer wraps 16+ digit numbers as strings before parsing.
- **Per-measurement id `measurement_id`**:
  - ZTF detection: `candid` (also > 2^53; keep it as a string in JS). This is the key for stamps.
  - ZTF forced photometry: `pid`, unique only within an object.
  - LSST: `diaSourceId`.

  Detection and forced-photometry tables join to their survey extension on `(oid, measurement_id)`; LSST joins also include `sid`.
- **Survey guess from an id** (explorer rule): `^ZTF\d{2}[a-z]+$` → ztf; all digits → lsst.

- An LSST alert that carries both a diaObject and an ssObject is stored under the diaObject (`sid = 1`); `lsst_detection.ssobjectid` is then filled.
- pandas tip: `read_csv(..., dtype_backend="pyarrow")` or `Int64` dtypes keep 64-bit ids exact.

## Bands
Read the band mapping from the data rather than hard-coding it. REST rows carry `band_map`; in TAP use the `alerce_tap.band` LUT.

| sid | band int → name | `band_order` (wavelength) |
|---|---|---|
| 0 ZTF | 1 g, 2 r, 3 i | g, r, i |
| 1, 2 LSST | **6 u**, 1 g, 2 r, 3 i, 4 z, 5 y | u, g, r, i, z, y |

- In the `feature` table, `band` can be a **band set**: `12` = g+r, `0` = band-independent (e.g. `W1-W2`). Decode digit by digit (`alerce_ms.band_label`).
- Legacy ZTF APIs call the band `fid` (1 = g, 2 = r, 3 = i), and use 12 for multiband features.

## Photometry and units
| quantity | ZTF | LSST |
|---|---|---|
| difference-image (alert) measurement | `magpsf ± sigmapsf` (AB mag), sign in `isdiffpos` (1/−1; legacy 't'/'f') | `psfFlux ± psfFluxErr` [nJy], signed |
| total ("science") brightness | `magpsf_corr ± sigmapsf_corr(_ext)`: reference flux added back, only when `corrected` is true | `scienceFlux ± scienceFluxErr` [nJy], direct image |
| forced photometry | `mag, e_mag, isdiffpos, mag_corr, e_mag_corr(_ext)` | `psfFlux`, `scienceFlux` (same names) |
| upper limits | `diffmaglim` (5σ), `ztf_non_detection` | **none** |

- AB ↔ nJy: `F = 10**(-0.4*(m - 31.4))`, `m = 31.4 - 2.5*log10(F)`, `σF = F * ln(10)/2.5 * σm`, `σm ≈ 1.0857 σF/|F|`.
- Signed ZTF difference flux: `F = isdiffpos * 10**(-0.4*(magpsf - 31.4))`.
- **Sentinels**:
  - ZTF errors of `100` mean "not available".
  - `mag == 100` in forced photometry means no measurement.
  - `sigmapsf_corr` is almost always 100 in legacy v1. Use `sigmapsf_corr_ext` / `e_mag_corr_ext` and reject errors ≥ 1.
- Negative difference flux is physical: a source fainter than in the template, or noise in forced photometry.
- `alerce_ms.get_lightcurve` (TAP) and `alerce_ms.api_lightcurve` (REST) return both surveys in one format:
  - `diff_flux`, `sci_flux` [nJy] plus `diff_mag`, `sci_mag`;
  - `kind` is `det` or `forced`. Non-detections come separately (`api_non_detections`, or the object's `n_non_det`).
- **A negative flux has a NaN magnitude**, while its `*_mag_err` is still finite. That is common for LSST detections (e.g. 35 of 108 for SN 2026gzf) and for forced photometry. Filter on flux or S/N, not on mag.
- **Peak** = the brightest positive-flux point. State which you use: detections only (the alert stream) or detections plus forced photometry. Per band, prefer S/N > 5.

## Time
- Use `mjd` everywhere. **LSST MJD is TAI, ZTF MJD is UTC**: subtract 37 s from LSST to get UTC.
- `now_mjd = unix_seconds/86400 + 40587`.
- `object.firstmjd/lastmjd` are the first and last detection. `probability.lastmjd` is the last data the classifier saw; for stamp classifiers that is the first alert.

## Positions
- `object.meanra/meandec` [deg, ICRS]; `sigmara/sigmadec` are in deg.
- ZTF stamps are 1.012″/pix, already North-up after flipping rows. LSST stamps are 0.2″/pix and carry a rotated WCS (see `api/stamps.md`).
