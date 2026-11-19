"""Shared fixtures for the claim tests of the `alerce` skill.

Layers (pytest markers):
  offline   no network: ids, units, doc structure, helper names.
  live      ALeRCE services (REST, TAP, stamps, explorer, hunter).
  external  non-ALeRCE services the skill relies on (CDS, NED, dust proxy). Outages here are common.
  drift     snapshot comparisons against tests/baselines/*.json (see snapshot.py).

Run:
  pytest                                # everything
  pytest -m offline                     # no network
  pytest -m "live and not drift"        # claims only
  pytest -m drift                       # what changed since the baselines?
  pytest -m drift --update-baselines    # accept the current state as the new baseline
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "alerce")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import alerce_ms as am  # noqa: E402

am.USE_CACHE = False  # we want the live state, not yesterday's cache

# Guiding objects of the IUCAA tutorial (COSMOS) used throughout the skill.
ZTF_SN = "ZTF26aaonmha"                 # SN 2026gzf (Ic-BL)
ZTF_SN_OID = 36029005852662990
LSST_SN = 314003014107006318
ZTF_QSO = "ZTF20acyxpwi"
LSST_QSO = 313985345706262538
ZTF_RRL = "ZTF17aabhbva"
LSST_RRL = (313888627082919999, 313893021775560722)
API = am.API_URL
TAP_SYNC = am.TAP_URL + "/sync"


def pytest_addoption(parser):
    parser.addoption("--update-baselines", action="store_true",
                     help="write the current live state to tests/baselines instead of comparing")


def pytest_configure(config):
    for m, h in [("offline", "no network"), ("live", "needs ALeRCE services"),
                 ("external", "needs non-ALeRCE services (CDS, NED, ...)"),
                 ("drift", "compares the live state with stored baselines"),
                 ("examples", "runs all 69 workflow queries of tap/examples.md (opt-in: -m examples)")]:
        config.addinivalue_line("markers", f"{m}: {h}")


def pytest_collection_modifyitems(items):
    """Tests without a network marker are offline."""
    for item in items:
        if not any(item.get_closest_marker(m) for m in ("live", "external", "drift", "offline")):
            item.add_marker(pytest.mark.offline)


def skill_text(rel: str) -> str:
    with open(os.path.join(SKILL, rel)) as f:
        return f.read()


# ---- session-scoped live data: fetched once per run to keep the load on ALeRCE small ----
@pytest.fixture(scope="session")
def luts():
    return am.load_luts()


@pytest.fixture(scope="session")
def ztf_sn_bundle():
    return am.api_lightcurve_raw(ZTF_SN, "ztf")


@pytest.fixture(scope="session")
def lsst_sn_bundle():
    return am.api_lightcurve_raw(LSST_SN, "lsst")


@pytest.fixture(scope="session")
def ztf_sn_object():
    return am.get_object(ZTF_SN, "ztf")


@pytest.fixture(scope="session")
def tap_tables_live():
    return am.tap_query("SELECT table_name FROM TAP_SCHEMA.tables WHERE schema_name = 'alerce_tap'")


@pytest.fixture(scope="session")
def tap_columns_live():
    return am.tap_query("SELECT table_name, column_name, datatype, unit FROM TAP_SCHEMA.columns "
                        "WHERE table_name LIKE 'alerce_tap.%'", maxrec=100000)


@pytest.fixture
def update_baselines(request):
    return request.config.getoption("--update-baselines")
