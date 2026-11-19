# Stamps (image cutouts)

Each detection with `has_stamp = true` has three cutouts: **science**, **template** (reference) and **difference**. Address them by `(oid, measurement_id)`. Take the `measurement_id` from a detection row (`lightcurve_api/lightcurve` or TAP `detection`).

| | LSST | ZTF |
|---|---|---|
| URL | `https://api-lsst.alerce.online/stamps_api/stamp?survey_id=lsst&oid={oid}&measurement_id={diaSourceId}&stamp_type={cutoutScience\|cutoutTemplate\|cutoutDifference}&file_format=fits&is_compressed=false` | `https://avro.alerce.online/get_stamp?oid={ZTF name}&candid={candid}&type={science\|template\|difference}&format=fits` |
| format | FITS (`file_format=png` also exists); extensions with UNCERT and PSF | **gzip-compressed** FITS (magic bytes `1f 8b`), slightly non-standard header; `format=png` exists |
| size / scale | **usually 30×30**, sometimes larger (e.g. 51×51, 75×75), at **0.2″/pix** | 63×63 at **1.012″/pix**; smaller and off-centre near CCD edges |
| WCS | full WCS, **rotated** to the detector frame (no CTYPE in some files) | **no WCS**; already sky-aligned (RA and Dec decrease with pixel index) |
| retention (checked 2026-11-19) | ≥ 11 months: stamps from Dec 2025 still served | every detection with `has_stamp = true` is served, 2018 to now; `has_stamp = false` normally 404 |

## Orientation (North up, East left)
- **ZTF**: `np.flipud(img)` and display with `imshow(origin="lower")`.
- **LSST**: resample with the inverse CD matrix, as `alerce_ms.north_up(img, header)` does. The explorer instead rotates the canvas (`stamps.js`).
- Use `alerce_ms.get_stamps(oid, sid, measurement_id, north=True)` to get `{science, template, difference}` arrays.
- Display with `plot_stamps(...)`: zscale lower limit, 99.8 percentile upper limit, asinh stretch, compass.
- `stamp_center` / `stamp_corners` let you outline one survey's footprint on the other's stamp.

## Tips
- Always sniff for gzip before `fits.open`. Cache the files (`alerce_ms` caches FITS on disk).
- The `/stamps_api/avro` endpoint returns 400 for LSST. ZTF stamps can also be read out of the AVRO packet.
- The stamp classifiers (`../classifiers/index.md`) see only the **first** alert's triplet. If you doubt a classification, look at the stamps yourself.
- A dipole in the difference image (positive and negative lobes) usually means misalignment or a bogus detection. A point source in the difference image offset from the galaxy centre in the science image is the classic SN signature.
