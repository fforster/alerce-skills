"""Offline claims: identifiers, units, helper names, doc structure. No network."""
import math
import os
import re
import subprocess
import sys

import numpy as np
import pytest

from conftest import SKILL, ZTF_SN, ZTF_SN_OID, am, skill_text


# ---- core/ids-and-units.md ----
def test_ztf_name_to_oid_example():
    """Claim (core/ids-and-units.md): ZTF26aaonmha <-> 36029005852662990."""
    assert am.ztf_name_to_oid(ZTF_SN) == ZTF_SN_OID
    assert am.oid_to_ztf_name(ZTF_SN_OID) == ZTF_SN


@pytest.mark.parametrize("name", ["ZTF17aabhbva", "ZTF20acyxpwi", "ZTF18aaaaaaa", "ZTF25zzzzzzz", "ZTF19abcdefg"])
def test_ztf_oid_roundtrip_and_prefix(name):
    """Claim: oid = (1 << 55) + yy*26**7 + base26(letters); the inverse recovers the name."""
    oid = am.ztf_name_to_oid(name)
    assert oid >> 55 == 1
    assert am.oid_to_ztf_name(oid) == name


def test_ztf_oids_exceed_float_precision():
    """Claim: ZTF integer oids (and LSST ids) exceed 2**53, so floats corrupt them."""
    assert ZTF_SN_OID > 2 ** 53
    assert int(float(ZTF_SN_OID)) != ZTF_SN_OID


def test_ab_zero_point_njy():
    """Claim: m = 31.4 - 2.5 log10(F/nJy); 1 nJy <-> 31.4 mag; 3631 Jy <-> 0 mag."""
    assert am.AB_ZP_NJY == 31.4
    assert am.mag_to_flux(31.4) == pytest.approx(1.0)
    assert am.flux_to_mag(3631e9) == pytest.approx(0.0, abs=1e-3)


def test_negative_flux_gives_nan_mag():
    """Claim (core/ids-and-units.md): a negative flux has a NaN magnitude."""
    assert np.isnan(am.flux_to_mag(-100.0))


def test_band_label_decodes_band_sets(monkeypatch):
    """Claim: feature band 12 = g+r, 0 = band-independent."""
    import pandas as pd
    lut = pd.DataFrame(dict(sid=[0, 0, 0], band=[1, 2, 3], band_name=["g", "r", "i"], band_order=[0, 1, 2]))
    monkeypatch.setattr(am, "load_luts", lambda: {"band": lut})
    assert am.band_label(0, 12) == "gr"
    assert am.band_label(0, 0) == ""
    assert am.band_label(0, 2) == "r"


def test_survey_guess_rule():
    """Claim (explorer/index.md): ^ZTF\\d{2}[a-z]+$ -> ztf, all digits -> lsst."""
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    import alerce_cli
    assert alerce_cli.guess_survey("ZTF26aaonmha", None) == "ztf"
    assert alerce_cli.guess_survey("314003014107006318", None) == "lsst"


# ---- hunter/candidate-search.md ----
def test_ecliptic_clause_constants():
    """Claim: ecliptic cut = |beta| > 10 deg with obliquity 23.4393, rescue = n_det >= 2 spanning >= 15 min."""
    c = am.ecliptic_keep_clause()
    assert "23.4393" in c and "RADIANS(10" in c and "o.n_det >= 2" in c
    assert re.search(r">= 0\.0104166", c)  # 15 min in days


def _ecliptic_lat(ra, dec, eps=23.4393):
    r, d, e = map(math.radians, (ra, dec, eps))
    return math.degrees(math.asin(math.sin(d) * math.cos(e) - math.cos(d) * math.sin(e) * math.sin(r)))


def test_ecliptic_formula_matches_astropy():
    """The clause's sin(beta) formula agrees with astropy's ecliptic latitude to < 0.01 deg."""
    from astropy.coordinates import SkyCoord, GeocentricTrueEcliptic
    import astropy.units as u
    for ra, dec in [(0, 0), (90, 23.44), (180, -10), (270, 60), (149.93, 0.42)]:
        b = SkyCoord(ra * u.deg, dec * u.deg).transform_to(GeocentricTrueEcliptic(equinox="J2000")).lat.deg
        assert _ecliptic_lat(ra, dec) == pytest.approx(b, abs=0.01)


def test_now_mjd_is_utc():
    """Claim: now_mjd = unix/86400 + 40587."""
    from astropy.time import Time
    assert am.now_mjd() == pytest.approx(Time.now().mjd, abs=1e-4)


# ---- structure: SKILL.md router and references ----
def test_check_skill_passes():
    """Every referenced file exists and is reachable; SKILL.md <= 150 lines; valid frontmatter."""
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "check_skill.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def _all_docs():
    for d, _, fs in os.walk(SKILL):
        for f in fs:
            if f.endswith(".md"):
                yield os.path.relpath(os.path.join(d, f), SKILL)


def test_every_am_function_mentioned_in_docs_exists():
    """Every `am.<name>(` / `alerce_ms.<name>` mentioned anywhere in the skill is a real attribute."""
    missing = set()
    for rel in _all_docs():
        for name in re.findall(r"\b(?:am|alerce_ms)\.([A-Za-z_][A-Za-z0-9_]*)", skill_text(rel)):
            if name != "py" and not hasattr(am, name):  # `alerce_ms.py` is the file name
                missing.add(f"{rel}: {name}")
    assert not missing, sorted(missing)


def test_function_index_lists_real_functions():
    """The module docstring's function index (referenced from SKILL.md) names only real functions."""
    block = am.__doc__.split("Function index", 1)[1].split("Requirements", 1)[0]
    names = re.findall(r"\b([a-z_][a-z0-9_]+)\b", "\n".join(l[11:] for l in block.splitlines()[2:]))
    assert names and not [n for n in names if not hasattr(am, n)]


def test_cli_subcommands_in_docs_exist():
    """Every `alerce_cli.py <cmd>` mentioned in the docs is a CLI subcommand."""
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "alerce_cli.py"), "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    help_text = r.stdout
    cmds = set()
    for rel in list(_all_docs()):
        cmds |= set(re.findall(r"alerce_cli\.py (?:--\S+ )*([a-z]+)", skill_text(rel)))
    cmds -= {"help"}
    assert cmds
    for c in cmds:
        assert re.search(rf"\b{c}\b", help_text), f"CLI has no subcommand {c!r}"


def test_readme_skill_map_is_current():
    """The Mermaid skill map in README.md matches the alerce/ tree (regenerate: python tools/build_diagram.py)."""
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(SKILL), "tools", "build_diagram.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_skill_md_points_to_status_page_and_schema_explorer():
    text = skill_text("SKILL.md")
    assert "https://status.alerce.online/" in text
    assert "https://claude.ai/artifact/JEpEyijsTpD1y83ut7Zia7#object" in text


def test_skill_md_routes_to_every_area():
    text = skill_text("SKILL.md")
    for area in ["api/", "tap/", "classifiers/", "explorer/", "hunter/", "crossmatch/", "science/", "core/"]:
        assert area in text
