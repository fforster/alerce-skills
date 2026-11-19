#!/usr/bin/env python3
"""alerce_cli.py — command-line access to ALeRCE for agents (wraps alerce_ms.py).

Examples
  python alerce_cli.py oid ZTF26aaonmha                     # name <-> integer oid
  python alerce_cli.py object ZTF26aaonmha --survey ztf      # REST object record (JSON)
  python alerce_cli.py lc 314003014107006318 --survey lsst   # REST light curve (CSV, nJy + AB mag)
  python alerce_cli.py probs ZTF26aaonmha --survey ztf       # REST class probabilities (CSV)
  python alerce_cli.py cone 149.9287 0.4184 --radius 2       # ZTF + LSST objects within 2" (CSV)
  python alerce_cli.py adql "SELECT TOP 5 * FROM alerce_tap.classifier" --maxrec 1000
  python alerce_cli.py candidates --survey lsst --class SN --days-first 7 --days-last 1 --top 20
  python alerce_cli.py candidates --survey lsst --days-first 3 --reference-mjd latest   # stream stalled?
  python alerce_cli.py latest --survey lsst                  # newest data epoch vs now
  python alerce_cli.py link ZTF26aaonmha ZTF20acyxpwi --survey ztf
  python alerce_cli.py xmatch 149.9287 0.4184               # SIMBAD/NED/VizieR catalogs (explorer recipe)

Output: CSV for tables (``--json`` for JSON), JSON for records.  The survey is guessed from the id when
``--survey`` is omitted (ZTF names -> ztf, all digits -> lsst).  Global flags go BEFORE the subcommand.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alerce_ms as am  # noqa: E402


def guess_survey(oid: str, survey: str | None) -> str:
    if survey:
        return survey
    return "ztf" if str(oid).startswith("ZTF") else "lsst"


def emit(df, as_json: bool):
    if as_json:
        print(df.to_json(orient="records", double_precision=10))
    else:
        print(df.to_csv(index=False), end="")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="tables as JSON records instead of CSV")
    ap.add_argument("--no-cache", action="store_true", help="bypass the on-disk cache")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("oid", help="convert ZTF name <-> integer oid")
    p.add_argument("ids", nargs="+")

    for name in ("object", "lc", "probs"):
        p = sub.add_parser(name)
        p.add_argument("oid")
        p.add_argument("--survey", choices=["ztf", "lsst"])
        if name == "lc":
            p.add_argument("--no-forced", action="store_true")
            p.add_argument("--tap", action="store_true", help="use TAP instead of REST")
        if name == "probs":
            p.add_argument("--classifier")

    p = sub.add_parser("cone", help="ZTF+LSST objects near a position (REST conesearch)")
    p.add_argument("ra", type=float)
    p.add_argument("dec", type=float)
    p.add_argument("--radius", type=float, default=2.0, help="arcsec (default 2)")
    p.add_argument("--neighbors", type=int, default=10)

    p = sub.add_parser("adql", help="run an ADQL query on tap.alerce.online")
    p.add_argument("query")
    p.add_argument("--maxrec", type=int, default=100000)

    p = sub.add_parser("candidates", help="hunter-style candidate search (TAP)")
    p.add_argument("--survey", default="lsst", choices=["ztf", "lsst"])
    p.add_argument("--classifier")
    p.add_argument("--class", dest="class_name", default="SN")
    p.add_argument("--days-first", type=float, default=7)
    p.add_argument("--days-last", type=float, default=1)
    p.add_argument("--ndet-min", type=int, default=2)
    p.add_argument("--prob-min", type=float)
    p.add_argument("--no-ecliptic-cut", action="store_true")
    p.add_argument("--keep-negative", action="store_true", help="don't reject objects with negative alert flux")
    p.add_argument("--reference-mjd", help="anchor the time windows at this MJD, or 'latest' (newest data epoch)")
    p.add_argument("--top", type=int, default=100)

    p = sub.add_parser("latest", help="MJD of the newest data for a survey (is the stream current?)")
    p.add_argument("--survey", default="lsst", choices=["ztf", "lsst"])

    p = sub.add_parser("link", help="explorer links for one or many objects")
    p.add_argument("oids", nargs="+")
    p.add_argument("--survey", choices=["ztf", "lsst"])

    p = sub.add_parser("xmatch", help="catalog crossmatch at a position (SIMBAD, NED, VizieR)")
    p.add_argument("ra", type=float)
    p.add_argument("dec", type=float)

    a = ap.parse_args(argv)
    if a.no_cache:
        am.USE_CACHE = False

    if a.cmd == "oid":
        out = []
        for i in a.ids:
            if i.startswith("ZTF"):
                out.append({"name": i, "oid": am.ztf_name_to_oid(i)})
            else:
                out.append({"name": am.oid_to_ztf_name(int(i)), "oid": int(i)})
        print(json.dumps(out))
    elif a.cmd == "object":
        print(json.dumps(am.get_object(a.oid, guess_survey(a.oid, a.survey))))
    elif a.cmd == "lc":
        s = guess_survey(a.oid, a.survey)
        if a.tap:
            df = am.get_lightcurve(a.oid, am.SID[s], forced=not a.no_forced)
        else:
            df = am.api_lightcurve(a.oid, s, forced=not a.no_forced)
        emit(df, a.json)
    elif a.cmd == "probs":
        emit(am.api_probabilities(a.oid, guess_survey(a.oid, a.survey), a.classifier), a.json)
    elif a.cmd == "cone":
        emit(am.find_counterparts(a.ra, a.dec, a.radius, a.neighbors), a.json)
    elif a.cmd == "adql":
        emit(am.tap_query(a.query, maxrec=a.maxrec, cache=not a.no_cache), a.json)
    elif a.cmd == "candidates":
        ref = a.reference_mjd
        if ref == "latest":
            ref = am.latest_mjd(a.survey)
        df = am.hunter_candidates(a.survey, a.classifier, a.class_name, a.days_first, a.days_last,
                                  a.ndet_min, a.prob_min, not a.no_ecliptic_cut,
                                  reject_negative=not a.keep_negative,
                                  reference_mjd=float(ref) if ref is not None else None, top=a.top)
        emit(df, a.json)
    elif a.cmd == "latest":
        last = am.latest_mjd(a.survey)
        print(json.dumps({"survey": a.survey, "latest_mjd": last, "now_mjd": am.now_mjd(),
                          "days_behind": am.now_mjd() - last}))
    elif a.cmd == "link":
        s = guess_survey(a.oids[0], a.survey)
        if len(a.oids) == 1:
            print(json.dumps(am.explorer_urls(a.oids[0], s)))
        else:
            print(json.dumps(am.explorer_list_urls(a.oids, s)))
    elif a.cmd == "xmatch":
        emit(am.catalog_xmatch(a.ra, a.dec, cache=not a.no_cache), a.json)


if __name__ == "__main__":
    main()
