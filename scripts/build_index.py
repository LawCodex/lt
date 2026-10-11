#!/usr/bin/env python3
"""Build the list of Lithuanian laws in force (RAW/index.jsonl) and locate their texts.

Why mirrors: the official open-data export of the Register of Legal Acts (data.gov.lt dataset
2613 "Teisės aktų registras", Spinta API get.data.gov.lt/datasets/gov/lrsk/teises_aktai/...)
answers "Web Page Blocked" (FortiWeb WAF) to our network, www.e-tar.lt is behind a Cloudflare
JavaScript challenge, and the e-seimas.lrs.lt search forms are blocked for non-JavaScript
clients (F5 bot defence).  None of these were circumvented.  The list of acts and the plain
text of each act's consolidated version are therefore taken from two public git mirrors of
that same official data.gov.lt dataset:

  * https://github.com/Yiin/lt-teises-aktai  (primary: plain text kept in source order)
  * https://github.com/legalize-dev/legalize-lt  (used only for acts missing from the first)

Usage: build_index.py RAW_DIR
"""
import datetime
import json
import os
import re
import subprocess
import sys

import yaml

MIRRORS = {
    "yiin": "https://github.com/Yiin/lt-teises-aktai.git",
    "legalize-lt": "https://github.com/legalize-dev/legalize-lt.git",
}
TODAY = datetime.date.today().isoformat()
AMEND_RE = re.compile(
    r"(pakeitimo|papildymo|pripažinimo netekusi|pripažinimo netekusiais|pakeitimų|"
    r"galiojimo sustabdymo|įsigaliojimo atidėjimo|dalinio pakeitimo)", re.I)
RANK_TYPE = {"konstitucija": "constitution", "konstitucinis_istatymas": "constitutional_law",
             "istatymas": "act", "kodeksas": "code"}


def clone(raw, name):
    d = os.path.join(raw, name)
    if not os.path.isdir(d):
        subprocess.check_call(["git", "clone", "-q", "--depth", "1", MIRRORS[name], d])
    else:
        subprocess.call(["git", "-C", d, "pull", "-q", "--depth", "1"])
    return d, subprocess.check_output(["git", "-C", d, "log", "-1", "--format=%H %cI"]).decode().strip()


def split_fm(path):
    t = open(path, encoding="utf-8").read()
    if not t.startswith("---"):
        return None, t
    parts = t.split("\n---", 1)
    try:
        fm = yaml.safe_load(parts[0][3:])
    except yaml.YAMLError:
        return None, t
    body = parts[1][1:] if len(parts) > 1 else ""
    return fm, body


def consolidated_from(body):
    m = re.search(r"Suvestinė redakcija nuo (\d{4}-\d{2}-\d{2})", body[:4000])
    return m.group(1) if m else None


def short_key(doc_id):
    return doc_id if doc_id.startswith("TAR.") else "TAR." + doc_id[:12].upper()


def s(v):
    return None if v in (None, "") else str(v)


def main(raw):
    ydir, yrev = clone(raw, "yiin")
    ldir, lrev = clone(raw, "legalize-lt")
    out = {}
    # 1. Yiin mirror
    for sub in ("konstitucija", "konstituciniai-istatymai", "kodeksai", "istatymai"):
        for f in sorted(os.listdir(os.path.join(ydir, sub))):
            if not f.endswith(".md"):
                continue
            p = os.path.join(ydir, sub, f)
            fm, body = split_fm(p)
            if not fm:
                continue
            rank = fm.get("rusis")
            st = fm.get("statusas")
            org = fm.get("leidziantis_organas") or ""
            if rank not in RANK_TYPE:
                continue
            if rank == "kodeksas" and "Seimas" not in org:
                continue  # codes of ethics etc. adopted by associations / ministries
            eff = s(fm.get("isigaliojimo_data"))
            if st == "galioja" or (st == "dar_neisigaliojo" and eff and eff <= TODAY):
                pass
            else:
                continue
            url = fm.get("etar_url") or ""
            doc_id = url.rstrip("/").rsplit("/", 1)[-1] if url else fm["tar_id"]
            title = fm.get("pavadinimas") or ""
            out[short_key(doc_id)] = {
                "id": doc_id, "title": title, "rank": rank, "number": s(fm.get("dok_nr")),
                "issuer": org or None, "date": s(fm.get("priemimo_data")),
                "in_force_from": eff, "published": s(fm.get("paskelbimo_data")),
                "mirror_status": st, "consolidated_from": consolidated_from(body),
                "text": os.path.relpath(p, raw), "mirror": "yiin",
                "amending": bool(AMEND_RE.search(title)) and rank not in ("konstitucija", "kodeksas"),
            }
    # 2. legalize-lt: acts in force missing from the Yiin mirror
    d = os.path.join(ldir, "lt")
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        fm, body = split_fm(p)
        if not fm or fm.get("status") != "in_force":
            continue
        rank = fm.get("rank")
        if rank not in RANK_TYPE:
            continue
        doc_id = fm["identifier"]
        k = short_key(doc_id)
        if k in out:
            continue
        title = fm.get("title") or ""
        out[k] = {
            "id": doc_id, "title": title, "rank": rank, "number": s(fm.get("document_number")),
            "issuer": fm.get("department"), "date": s(fm.get("publication_date")),
            "in_force_from": None, "published": s(fm.get("published_in_tar")),
            "mirror_status": fm.get("status"), "consolidated_from": consolidated_from(body),
            "tar_code": fm.get("tar_code"),
            "text": os.path.relpath(p, raw), "mirror": "legalize-lt",
            "amending": bool(AMEND_RE.search(title)) and rank != "konstitucija",
        }
    rows = sorted(out.values(), key=lambda r: (r["date"] or "", r["id"]))
    with open(os.path.join(raw, "index.jsonl"), "w", encoding="utf-8") as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump({"yiin": yrev, "legalize-lt": lrev, "built": TODAY},
              open(os.path.join(raw, "index.meta.json"), "w"), indent=1)
    from collections import Counter
    print(len(rows), "acts;", Counter((r["mirror"], r["rank"], r["amending"]) for r in rows))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Users/magicaltux/projects/lawcodex/_raw/lt")
