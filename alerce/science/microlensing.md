# Microlensing (ZTF)

From the official `ALeRCE_Microlensing_Starter` notebook (github.com/alercebroker/usecases, `notebooks/ZTF/`). That notebook queries the legacy `ztf.*` schema; the `alerce_tap` versions are below.

## Select candidates and apply the cuts (end to end)
- Use the flat light-curve classifier `lc_classifier_BHRF_forced_phot`, class `Microlensing`, `ranking = 1`, with ids looked up by name (the stochastic branch numbers the class differently). ATAT `(beta)` also has the class in the legacy schema.
- An object needs **≥ 8 detections with rb ≥ 0.55** to be classified by the light-curve classifier, so short events are missed; `o.n_det >= 8` is a cheap pre-filter.
- The probability scan is the indexed path (`sid` + `ranking = 1` + `ORDER BY probability`, see `../tap/indexes-and-joins.md`). **Check for truncation:** if you get exactly `TOP` rows, raise `TOP` or add a probability floor. On 2026-11-19 the best microlensing probabilities were only ≈ 0.5 (the class is rare), so rank, don't threshold.
- **Cut rule:**
  - A band is **fitted** when all three of `ulens_u0`, `ulens_tE` and `ulens_chi` are present (missing features are not stored).
  - A fitted band **passes** if `u0 < 1`, `chi < 1` and `10 < tE < 300` d.
  - Keep an object if both bands pass, or if one band passes and the other has no fit.

```python
# runnable
import pandas as pd
import alerce_ms as am

clf = "lc_classifier_BHRF_forced_phot"
cid, mid = am.classifier_id(clf), am.class_id(clf, "Microlensing")
TOP = 2000
cand = am.tap_query(f"""
    SELECT TOP {TOP} p.oid, p.probability, o.n_det, o.firstmjd, o.lastmjd
    FROM alerce_tap.probability AS p
    JOIN alerce_tap.object AS o ON o.oid = p.oid AND o.sid = p.sid
    WHERE p.sid = 0 AND p.ranking = 1 AND p.classifier_id = {cid} AND p.class_id = {mid}
      AND o.n_det >= 8
    ORDER BY p.probability DESC""", maxrec=TOP)
if len(cand) == TOP:
    print(f"hit TOP {TOP}: raise TOP or add a probability floor (p.probability >= ...) to see the rest")

f = am.get_features_many(cand.oid, 0, ["ulens_u0", "ulens_tE", "ulens_chi"])  # columns ulens_u0_g, ulens_tE_r, ...


def band(b):
    """(fitted, passes) for one band: fitted = all three parameters present."""
    u0, tE, chi = (f.get(f"ulens_{p}_{b}") for p in ("u0", "tE", "chi"))
    if u0 is None:
        none = pd.Series(False, index=f.index)
        return none, none
    fitted = u0.notna() & tE.notna() & chi.notna()
    return fitted, fitted & (u0 < 1) & (chi < 1) & tE.between(10, 300)


fit_g, ok_g = band("g")
fit_r, ok_r = band("r")
keep = (ok_g & ok_r) | (ok_g & ~fit_r) | (ok_r & ~fit_g)  # both bands pass, or one passes and the other has no fit
good = cand.set_index("oid").join(f[keep], how="inner").sort_values("probability", ascending=False)
good["name"] = [am.oid_to_ztf_name(o) for o in good.index]
good["explorer"] = [am.explorer_url(n, "ztf") for n in good.name]
print(len(cand), "candidates,", len(good), "pass the cuts")
print(good[["name", "probability", "ulens_u0_g", "ulens_tE_g", "ulens_chi_g", "ulens_u0_r", "ulens_tE_r", "ulens_chi_r"]].head())
```
`get_features_many` fetches the features of the whole sample with one upload join (bands come out as `_g`, `_r`). This code runs in about 12 s.

## The Paczyński model features
Per band, the feature table has `ulens_u0`, `ulens_tE` [d], `ulens_fs`, `ulens_t0`, `ulens_mag0`, `ulens_chi`. In `alerce_tap`, `ulens_t0` is relative to `ulens_mjd_ref`. The model is (Khakpash+2021):
```python
u = np.sqrt(u0**2 + ((t - t0) / tE)**2)
A = (u**2 + 2) / (u * np.sqrt(u**2 + 4))
mag = -2.5 * np.log10(fs * (A - 1) + 1) + mag0
```
The official notebook's quality cuts are `u0 < 1`, `ulens_chi < 1` and `10 < tE < 300` d, applied in both g and r (or in one band when the other is NaN). Then inspect the light curves: a symmetric, achromatic bump on a flat baseline is the signature.

## Plotting conventions used there
- Difference and total flux in µJy: `F = 10**(-0.4 * (m - 23.9))`. The skill's helpers use nJy: `31.4` instead of `23.9`.
- Upper limits at SNU = 5 (Masci+2023).
- Use forced photometry to see the full baseline before and after the event.
