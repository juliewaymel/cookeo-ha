#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moissonneur de recettes officielles Cookeo (API SEB) -> catalogue local FR.

Pas de liste publique : on échantillonne l'espace d'ids fonctionnels et on garde
les recettes FR (market GS_FR), dédupliquées par groupingId. Header `apikey`
(domaine PRO_COO). Images servies par le CDN public /statics (pas de cache).

Usage : python3 harvest.py [start] [stop] [step] [target]
Catalogue écrit dans /opt/cookeo-catalog/catalog.json (fusion incrémentale).
"""
import json, os, sys, time, urllib.request

API = "https://sebplatform.api.groupe-seb.com"
KEY = "GtPU4am4rpf83Zptq4xahtJsEytbrvKP"
OUT_DIR = os.environ.get("COOKEO_CATALOG_DIR", "/opt/cookeo-catalog")
OUT = os.path.join(OUT_DIR, "catalog.json")

START = int(sys.argv[1]) if len(sys.argv) > 1 else 500000
STOP = int(sys.argv[2]) if len(sys.argv) > 2 else 1150000
STEP = int(sys.argv[3]) if len(sys.argv) > 3 else 37      # échantillonnage
TARGET = int(sys.argv[4]) if len(sys.argv) > 4 else 600   # nb recettes visé


def fetch(fid):
    req = urllib.request.Request(
        "%s/common-api/recipes/PRO/%d/" % (API, fid),
        headers={"apikey": KEY, "Accept": "application/json",
                 "User-Agent": "catalog-harvester"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            if r.status != 200:
                return None
            return json.load(r)
    except Exception:
        return None


def step_info(st):
    """Étape de cuisson : description + programme Cookeo + durée(s) + température."""
    info = {"desc": st.get("applicationDescription")}
    prog = None
    fp = st.get("firstProgram")
    if isinstance(fp, dict):
        prog = fp.get("key")
    if not prog:
        for p in st.get("programs") or []:
            if isinstance(p, dict) and p.get("key"):
                prog = p["key"]
                break
    if prog:
        info["program"] = prog
    for seq in st.get("sequences") or []:
        for op in seq.get("operations") or []:
            if isinstance(op, dict) and op.get("firstProgram") and not info.get("program"):
                fp2 = op.get("firstProgram")
                if isinstance(fp2, dict) and fp2.get("key"):
                    info["program"] = fp2["key"]
            for par in op.get("parameters") or []:
                ck = par.get("commonKey")
                if ck == "DURATION" and "duration_s" not in info:
                    info["duration_s"] = par.get("value")
                elif ck == "TEMPERATURE" and "temp" not in info:
                    info["temp"] = par.get("value")
    return info


def card(d):
    if (d.get("market") or "") != "GS_FR" or (d.get("lang") or "") != "fr":
        return None
    cover = (d.get("cover") or {}).get("media") or {}
    ings = []
    for ing in d.get("ingredients") or []:
        if isinstance(ing, dict):
            n = ing.get("applicationDescription")
            if not n:
                food = ing.get("food")
                if isinstance(food, dict):
                    for nm in food.get("name") or []:
                        if isinstance(nm, dict) and nm.get("lang") == "fr":
                            n = nm.get("value")
                            break
            if n:
                ings.append(n)
    steps = [step_info(s) for s in d.get("steps") or [] if isinstance(s, dict)]
    steps = [s for s in steps if s.get("desc")]
    dur = d.get("durations") or {}
    y = d.get("yield") or {}
    return {
        "fid": (d.get("identifier") or {}).get("functionalId"),
        "grouping": d.get("groupingId"),
        "title": d.get("title"),
        "image": cover.get("original") or cover.get("medium") or cover.get("thumbnail"),
        "ingredients": ings,
        "steps": steps,
        "total_min": dur.get("totalTime"),
        "yield": y.get("quantityDisplay"),
        "categories": d.get("categories") or [],
    }


def save(catalog):
    tmp = OUT + ".tmp"
    data = {"updated_ts": int(time.time()), "count": len(catalog),
            "recipes": sorted(catalog.values(), key=lambda x: (x.get("title") or "").lower())}
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)  # écriture atomique


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    catalog = {}
    if os.path.exists(OUT):
        try:
            for c in json.load(open(OUT, encoding="utf-8")).get("recipes", []):
                catalog[str(c.get("grouping") or c.get("fid"))] = c
        except Exception:
            pass
    start_n = len(catalog)
    scanned = 0
    last_save = 0
    for fid in range(START, STOP, STEP):
        if len(catalog) - start_n >= TARGET:
            break
        scanned += 1
        d = fetch(fid)
        if not d:
            continue
        c = card(d)
        if not c:
            continue
        key = str(c.get("grouping") or c["fid"])
        if key not in catalog:
            catalog[key] = c
            if len(catalog) - last_save >= 20:   # sauvegarde incrémentale
                save(catalog)
                last_save = len(catalog)
        if scanned % 50 == 0:
            time.sleep(0.3)  # politesse
    save(catalog)
    print("catalogue: %d recettes (%d nouvelles), %d ids scannés -> %s"
          % (len(catalog), len(catalog) - start_n, scanned, OUT))


if __name__ == "__main__":
    main()
