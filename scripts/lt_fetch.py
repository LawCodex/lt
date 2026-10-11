#!/usr/bin/env python3
"""Fetch the current official consolidated text (aktuali suvestinė redakcija) from
e-seimas.lrs.lt for the Constitution, the codes and a few other acts whose e-seimas document id
is known (see KNOWN below, plus the acts linked from the public "Naujausi įsigalioję įstatymai"
pre-filled search page).  e-seimas uses its own document ids (TAIS.<n> or 32-hex), which differ
from the e-tar ids of the open-data index and cannot be looked up without the (JavaScript-only)
search form, so this cannot be done for every act.

Only plain GET requests on public URLs are used:
  /portal/legalActEditions/lt/TAD/<id>     list of consolidated editions of an act
  /rs/actualedition/<id>/<editionId>/      HTML of one consolidated edition
Each text is matched to the index through the e-tar id linked from its own header
("... paskelbtas: Žin. ..., Nr. <a href=e-tar ...documentId=...>").

Usage: lt_fetch.py RAW_DIR
"""
import concurrent.futures as cf
import datetime
import html
import json
import os
import re
import sys
import threading
import time

import requests

BASE = "https://e-seimas.lrs.lt"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
WORKERS = 2
DELAY = 0.4
TODAY = datetime.date.today().isoformat()

_local = threading.local()


def session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = UA
        _local.s = s
    return s


def get(url, binary=False):
    for attempt in range(6):
        try:
            time.sleep(DELAY)
            r = session().get(BASE + url, timeout=300)
            if r.status_code == 404:
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.RequestException("HTTP %s" % r.status_code)
            r.raise_for_status()
            r.encoding = "utf-8"
            t = r.text
            if "Unauthorized Request Blocked" in t[:2000]:
                raise RuntimeError("blocked by WAF: " + url)
            return t
        except requests.RequestException as e:
            wait = 15 * (attempt + 1)
            print("  retry", url, e, "in", wait, file=sys.stderr, flush=True)
            time.sleep(wait)
    raise RuntimeError("failed: " + url)


class Store:
    def __init__(self, raw):
        self.raw = raw
        self.cache = os.path.join(raw, "cache")
        for sub in ("ed", "txt"):
            os.makedirs(os.path.join(self.cache, sub), exist_ok=True)
        self.state_path = os.path.join(raw, "fetched.json")
        self.state = json.load(open(self.state_path)) if os.path.exists(self.state_path) else {}
        self.lock = threading.Lock()

    def save(self):
        with self.lock:
            tmp = self.state_path + ".tmp"
            json.dump(self.state, open(tmp, "w"), ensure_ascii=False, indent=0)
            os.replace(tmp, self.state_path)

    def cached(self, kind, key, url):
        p = os.path.join(self.cache, kind, key.replace("/", "_") + ".html")
        if os.path.exists(p):
            return open(p, encoding="utf-8").read()
        t = get(url)
        if t is None:
            t = ""
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            f.write(t)
        os.replace(p + ".tmp", p)
        return t


ROW_RE = re.compile(
    r'<tr data-ri="\d+"[^>]*>\s*<td role="gridcell"><a href="/portal/legalAct/lt/TAD/([^/"]+)/([A-Za-z]+)"[^>]*>'
    r'Suvestinė nuo (\d{4}-\d{2}-\d{2})</a></td><td role="gridcell">(\d{4}-\d{2}-\d{2})?</td>', re.S)


def editions(page):
    rows = [(ed, fr, to) for (_id, ed, fr, to) in ROW_RE.findall(page)]
    return rows


def pick_edition(rows):
    cur = [r for r in rows if r[1] <= TODAY and (not r[2] or r[2] >= TODAY)]
    if cur:
        return max(cur, key=lambda r: r[1])
    past = [r for r in rows if r[1] <= TODAY]
    if past:
        return max(past, key=lambda r: r[1])
    return None


def page_title(page):
    m = re.search(r"<title>(.*?)</title>", page, re.S)
    return html.unescape(m.group(1)).strip() if m else None


def fetch_doc(store, eid, consolidated=True):
    """Return dict with text html path info for e-seimas document id `eid`."""
    info = {"eseimas_id": eid}
    if consolidated:
        page = store.cached("ed", eid, "/portal/legalActEditions/lt/TAD/%s" % eid)
        if "teisėkūros objektas nerastas" in page:
            return None
        info["page_title"] = page_title(page)
        rows = editions(page)
        ed = pick_edition(rows)
        if ed:
            info.update(edition_id=ed[0], edition_from=ed[1], edition_to=ed[2] or None,
                        url="/rs/actualedition/%s/%s/" % (eid, ed[0]),
                        portal="%s/portal/legalAct/lt/TAD/%s/asr" % (BASE, eid))
            txt = store.cached("txt", eid, info["url"])
            info["has_text"] = bool(txt.strip())
            return info
    info.update(url="/rs/legalact/TAD/%s/" % eid, portal="%s/portal/legalAct/lt/TAD/%s" % (BASE, eid))
    txt = store.cached("txt", eid, info["url"])
    if not txt.strip():
        return None
    info["has_text"] = True
    return info


def text_of(store, eid):
    p = os.path.join(store.cache, "txt", eid + ".html")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


LINK_RE = re.compile(
    r'<a href="(?:https?://www3?\.lrs\.lt/cgi-bin/preps2\?a=(\d+)[^"]*|'
    r'https?://www3?\.lrs\.lt/pls/inter3?/dokpaieska\.showdoc_l\?p_id=(\d+)[^"]*|'
    r'(?:https?://e-seimas\.lrs\.lt)?/portal/legalAct/lt/TAD/TAIS\.(\d+)[^"]*)"[^>]*>(.*?)</a>', re.S)


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def harvest(txt):
    """Yield (tais_id, link_text, year) for every TAIS link; year = last 'YYYY, Nr.' before it."""
    b = txt.find("<body")
    txt = txt[b:] if b >= 0 else txt
    marks = []

    def repl(m):
        marks.append(("TAIS." + (m.group(1) or m.group(2) or m.group(3)), strip(m.group(4))))
        return " \x00%d\x00 " % (len(marks) - 1)
    t = LINK_RE.sub(repl, txt)
    t = strip(t)
    for m in re.finditer(r"\x00(\d+)\x00", t):
        tid, text = marks[int(m.group(1))]
        before = re.sub(r"\x00\d+\x00", "", t[max(0, m.start() - 300):m.start()])
        ys = re.findall(r"(\d{4})\s*,?\s*Nr\.", before)
        yield tid, text, (ys[-1] if ys else None)


def own_tar_ids(txt):
    """TAR ids linked from the 'paskelbtas:' header of a consolidated text."""
    b = txt.find("<body")
    head = txt[b:b + 30000]
    i = head.find("paskelbtas")
    if i < 0:
        return set()
    seg = head[i:i + 3000]
    return re.findall(r"documentId=(TAR\.[0-9A-F]{12}|[0-9a-f]{32})", seg)


KNOWN = [
    "TAIS.1890",        # Konstitucija
    "TAIS.107687",      # Civilinis kodeksas
    "TAIS.111555",      # Baudžiamasis kodeksas
    "TAIS.162435",      # Civilinio proceso kodeksas
    "TAIS.163482",      # Baudžiamojo proceso kodeksas
    "TAIS.171368",      # Bausmių vykdymo kodeksas
    "b8d908c0215b11e58a4198cd62929b7a",  # Administracinių nusižengimų kodeksas
    "10c6bfd07bd511e6a0f68fd135e6f40c",  # Darbo kodeksas
    "44e06821075711edbfe9c72e552dd5bd",  # Rinkimų kodeksas
    "TAIS.232217",      # Geležinkelių transporto kodeksas
    "TAIS.283041",      # Valstybės politikų elgesio kodeksas
    "TAIS.33417",       # Kelių transporto kodeksas
    "TAIS.32085",       # Vidaus vandenų transporto kodeksas
    "TAIS.5705",        # Patentų įstatymas
]
PREFILLED = "/portal/prefilledSearch/lt/2e08f55f-1579-4b44-852f-ece2aa6ccacf"


def short_key(doc_id):
    return doc_id if doc_id.startswith("TAR.") else "TAR." + doc_id[:12].upper()


def main(raw):
    store = Store(raw)
    keys, by_no = {}, {}
    for l in open(os.path.join(raw, "index.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        keys[short_key(r["id"])] = r["id"]
        if r["number"] and not r["amending"]:
            by_no.setdefault(r["number"].replace(" ", ""), []).append(r["id"])
    st = store.state
    cands = list(KNOWN)
    try:
        page = get(PREFILLED) or ""
        for eid in re.findall(r'href="/portal/legalAct/lt/TAD/([^/"?]+)/asr', page):
            if eid not in cands:
                cands.append(eid)
    except Exception as e:  # noqa
        print("prefilled search failed:", e, flush=True)
    print(len(cands), "candidate e-seimas documents", flush=True)

    def one(eid):
        try:
            info = fetch_doc(store, eid, consolidated=True)
        except Exception as e:  # noqa
            return eid, None, str(e)
        if not info or not info.get("edition_id"):
            return eid, None, "no consolidated edition"
        own = own_tar_ids(text_of(store, eid))
        if own:
            # the first link of the header is the act's own publication reference
            if short_key(own[0]) not in keys:
                return eid, None, "header id %s not in index" % own[0]
            info["etar_id"] = keys[short_key(own[0])]
        else:
            # TAR-era header has no link: match on the document number of the page title
            no = (info.get("page_title") or "").split(" ")[0]
            hits = by_no.get(no, [])
            if len(hits) > 1:
                return eid, None, "number %r matches %d index entries" % (no, len(hits))
            # acts missing from the (older) open-data mirror are kept under their e-seimas id
            info["etar_id"] = hits[0] if hits else None
        return eid, info, None

    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for eid, info, err in ex.map(one, cands):
            if info:
                st[info["etar_id"] or "eseimas:" + eid] = info
                print("  ok", eid, "->", info["etar_id"] or "(not in index)", info.get("edition_from"), flush=True)
            else:
                print("  skip", eid, err, flush=True)
    store.save()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Users/magicaltux/projects/lawcodex/_raw/lt")
