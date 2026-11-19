#!/usr/bin/env python3
"""Live smoke test of the ALeRCE services used by the skill (needs network).

    python smoke_test.py            # all checks
    python smoke_test.py --quick    # skip stamps and the candidate search

Uses the IUCAA-tutorial objects in COSMOS: SN 2026gzf (ZTF26aaonmha / LSST 314003014107006318) and the
RR Lyrae ZTF17aabhbva.  Prints one PASS/FAIL line per check and exits non-zero on any failure.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alerce_ms as am  # noqa: E402

am.USE_CACHE = False
ZTF_SN, LSST_SN, ZTF_RRL = "ZTF26aaonmha", 314003014107006318, "ZTF17aabhbva"
results = []


def check(name):
    def deco(f):
        t0 = time.time()
        try:
            msg = f() or ""
            results.append(True)
            print(f"PASS {name:<40s} {time.time() - t0:5.1f}s {msg}", flush=True)
        except Exception as e:  # noqa: BLE001
            results.append(False)
            print(f"FAIL {name:<40s} {time.time() - t0:5.1f}s {type(e).__name__}: {e}", flush=True)
        return f
    return deco


@check("ZTF name <-> oid round trip")
def _():
    oid = am.ztf_name_to_oid(ZTF_SN)
    assert oid == 36029005852662990, oid
    assert am.oid_to_ztf_name(oid) == ZTF_SN


@check("REST object (ztf, lsst)")
def _():
    z, l = am.get_object(ZTF_SN, "ztf"), am.get_object(LSST_SN, "lsst")
    assert z["oid"] == ZTF_SN and int(l["oid"]) == LSST_SN
    return f"n_det ztf={z['n_det']} lsst={l['n_det']}"


@check("REST light curve (ztf)")
def _():
    lc = am.api_lightcurve(ZTF_SN, "ztf")
    assert len(lc) > 10 and set(lc.kind) == {"det", "forced"}
    return f"{len(lc)} rows, bands {sorted(lc.band_name.dropna().unique())}"


@check("REST light curve (lsst)")
def _():
    lc = am.api_lightcurve(LSST_SN, "lsst")
    assert len(lc) > 10 and lc.diff_flux.notna().all()
    return f"{len(lc)} rows, bands {sorted(lc.band_name.dropna().unique())}"


@check("REST probabilities (lsst)")
def _():
    p = am.api_probabilities(LSST_SN, "lsst")
    assert {"classifier_name", "class_name", "probability", "ranking"} <= set(p.columns)
    return f"{p.classifier_name.nunique()} classifiers"


@check("TAP lookup tables")
def _():
    luts = am.load_luts()
    assert am.classifier_id("lc_classifier_BHRF_forced_phot") > 0
    lsst_u = luts["band"].query("sid == 1 and band_name == 'u'").band.iloc[0]
    return f"{len(luts['classifier'])} classifiers, LSST u band = {lsst_u}"


@check("TAP light curve (ztf) vs REST")
def _():
    tap = am.get_lightcurve(ZTF_SN, 0)
    rest = am.api_lightcurve(ZTF_SN, "ztf")
    assert abs(len(tap) - len(rest)) <= 2, (len(tap), len(rest))
    return f"tap={len(tap)} rest={len(rest)}"


@check("REST cone: ZTF+LSST counterparts")
def _():
    obj = am.get_object(ZTF_SN, "ztf")
    df = am.find_counterparts(obj["meanra"], obj["meandec"], 2.0)
    assert {"ztf", "lsst"} <= set(df.survey), df
    return f"{len(df)} objects"


@check("TAP features + probabilities (ztf RRL)")
def _():
    f = am.get_features(ZTF_RRL, 0, names=["Multiband_period"])
    p = am.get_probabilities(ZTF_RRL, 0, "lc_classifier_BHRF_forced_phot")
    return f"period={f.feature_value.iloc[0]:.5f} d, top class={p.class_name.iloc[0]}"


@check("explorer links")
def _():
    u = am.explorer_urls(ZTF_SN, "ztf")
    assert u["experimental explorer"].endswith("?survey=ztf&oid=ZTF26aaonmha")
    assert u["ALeRCE explorer"] == "https://lsst.alerce.online/object/ZTF26aaonmha?survey=ztf"


if "--quick" not in sys.argv:
    @check("stamps (ztf, lsst)")
    def _():
        raw_z = am.api_lightcurve_raw(ZTF_SN, "ztf")
        raw_l = am.api_lightcurve_raw(LSST_SN, "lsst")
        mid_z = next(d["measurement_id"] for d in raw_z["detections"] if d.get("has_stamp"))
        mid_l = next(d["measurement_id"] for d in raw_l["detections"] if d.get("has_stamp"))
        sz = am.get_stamps(ZTF_SN, 0, mid_z)
        sl = am.get_stamps(LSST_SN, 1, mid_l)
        return f"ztf {sz['science'].shape}, lsst {sl['science'].shape}"

    @check("hunter candidate search (lsst, TOP 5)")
    def _():
        df = am.hunter_candidates("lsst", top=5, max_days_since_first=30, max_days_since_last=10)
        return f"{len(df)} candidates" + (f", best p={df.probability.iloc[0]:.2f}" if len(df) else "")

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
