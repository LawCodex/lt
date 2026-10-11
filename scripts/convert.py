#!/usr/bin/env python3
"""Convert the collected Lithuanian legislation to Markdown.

Inputs (all under RAW_DIR, produced by build_index.py and lt_fetch.py):
  index.jsonl            list of acts in force + path of their plain text in the mirrors
  fetched.json           acts for which the official e-seimas HTML consolidated text was fetched
  cache/txt/<id>.html    e-seimas HTML texts

Usage: convert.py RAW_DIR OUT_REPO_DIR
"""
import datetime
import html as htmlmod
import json
import os
import re
import sys
import unicodedata

import yaml
from lxml import html as lhtml

TODAY = datetime.date.today().isoformat()
ESEIMAS = "https://e-seimas.lrs.lt"

CODES = {
    "TAR.8A39C83848CB": "civilinis-kodeksas",
    "TAR.2B866DFF7D43": "baudziamasis-kodeksas",
    "TAR.2E7C18F61454": "civilinio-proceso-kodeksas",
    "TAR.EC588C321777": "baudziamojo-proceso-kodeksas",
    "TAR.A0A0CCC6B997": "bausmiu-vykdymo-kodeksas",
    "4ebe66c0262311e5bf92d6af3f6a2e8b": "administraciniu-nusizengimu-kodeksas",
    "f6d686707e7011e6b969d7ae07280e89": "darbo-kodeksas",
    "418f26f0082b11edb4cae1b158f98ea5": "rinkimu-kodeksas",
    "TAR.6EA8AC8A483B": "gelezinkeliu-transporto-kodeksas",
    "TAR.955166852BD7": "valstybes-politiku-elgesio-kodeksas",
    "TAR.65AD818F5F9C": "keliu-transporto-kodeksas",
    "TAR.DEBA0718FB0F": "vidaus-vandenu-transporto-kodeksas",
}
CONSTITUTION = "TAR.47BB952431DA"

ORD = (r"(?:[IVXLC]+|PIRM|ANTR|TREČI|KETVIRT|PENKT|ŠEŠT|SEPTINT|AŠTUNT|DEVINT|DEŠIMT|"
       r"VIENUOLIKT|DVYLIKT|TRYLIKT|KETURIOLIKT|PENKIOLIKT|ŠEŠIOLIKT|SEPTYNIOLIKT|AŠTUONIOLIKT|"
       r"DEVYNIOLIKT|DVIDEŠIMT|TRISDEŠIMT|KETURIASDEŠIMT|PENKIASDEŠIMT|BENDR|SPECIALI|BAIGIAM|"
       r"ĮŽANGIN)[A-ZĄČĘĖĮŠŲŪŽ\-]*(?:\s+(?:PIRM|ANTR|TREČI|KETVIRT|PENKT|ŠEŠT|SEPTINT|AŠTUNT|"
       r"DEVINT)[A-ZĄČĘĖĮŠŲŪŽ]*)?")
UNITS = ["KNYGA", "DALIS", "SKYRIUS", "SKIRSNIS", "POSKIRSNIS"]
STRUCT_RE = re.compile(r"^(%s)(?:[\-–]\d+)?\s+(KNYGA|DALIS|SKYRIUS|SKIRSNIS|POSKIRSNIS)\.?$" % ORD, re.I)
ART_RE = re.compile(r"^(\d+(?:[.\-]\s?\d+)*(?:<sup>[^<]*</sup>)?)\s*(?:<sup>[^<]*</sup>)?\s+straipsnis(?:\.|\s|$)\s*(.*)$")
TRANS = str.maketrans("ąčęėįšųūžĄČĘĖĮŠŲŪŽ", "aceeisuuzACEEISUUZ")


def slugify(s, maxlen=90):
    s = s.translate(TRANS)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s


def yaml_str(v):
    return json.dumps(v, ensure_ascii=False)


def md_escape(line):
    if re.match(r"^\s*(#|>|[-+*]\s|=+\s*$|-{3,}\s*$|\|)", line):
        return "\\" + line.lstrip()
    return line


# --------------------------------------------------------------------------- blocks
# A document is converted to a list of blocks: ("p", text, attrs) or ("table", markdown)
# then headings are detected on the "p" blocks.

def inline(el):
    """Text of an element with <sup>/<sub> kept as HTML, whitespace normalised.
    CSS text-transform:uppercase (used for headings in the Word HTML) is applied."""
    parts = []

    def up(e, upper):
        st = (e.get("style") or "").replace(" ", "").lower()
        if "text-transform:uppercase" in st:
            return True
        if "text-transform:none" in st:
            return False
        return upper

    def T(x, upper):
        return x.upper() if upper else x

    def walk(e, upper):
        tag = e.tag if isinstance(e.tag, str) else ""
        upper = up(e, upper) if tag else upper
        if tag in ("sup", "sub"):
            t = re.sub(r"\s+", " ", e.text_content()).strip()
            if t:
                parts.append("<%s>%s</%s>" % (tag, T(t, upper), tag))
            return
        if tag == "br":
            parts.append("\n")
            return
        if tag in ("script", "style", "img") or not tag:
            return
        if e.text:
            parts.append(T(e.text, upper))
        for c in e:
            walk(c, upper)
            if c.tail:
                parts.append(T(c.tail, upper))

    walk(el, False)
    s = "".join(parts).replace("\xa0", " ")
    s = "\n".join(re.sub(r"[ \t\r\f\v]+", " ", x).strip() for x in s.split("\n"))
    return s.strip()


def is_bold(p):
    txt = re.sub(r"\s+", "", p.text_content())
    if not txt:
        return False
    b = "".join(re.sub(r"\s+", "", x.text_content()) for x in p.iter("b", "strong"))
    return len(b) >= 0.6 * len(txt)


def is_italic(p):
    txt = re.sub(r"\s+", "", p.text_content())
    if not txt:
        return False
    b = "".join(re.sub(r"\s+", "", x.text_content()) for x in p.iter("i", "em"))
    return len(b) >= 0.9 * len(txt)


def is_center(p):
    st = (p.get("style") or "") + " " + (p.get("align") or "")
    return "center" in st


def cell_text(td):
    lines = []
    for p in td.iter("p"):
        t = inline(p)
        if t:
            lines.append(t)
    if not lines:
        t = inline(td)
        if t:
            lines.append(t)
    return "<br>".join(x.replace("\n", "<br>") for x in lines)


def table_md(tb):
    rows = []
    complex_ = False
    for tr in tb.iter("tr"):
        cells = []
        for td in tr:
            if not isinstance(td.tag, str) or td.tag not in ("td", "th"):
                continue
            if td.get("colspan", "1") != "1" or td.get("rowspan", "1") != "1":
                complex_ = True
            if td.find(".//table") is not None:
                complex_ = True
            cells.append((td, cell_text(td)))
        if cells:
            rows.append(cells)
    if not rows:
        return None
    if all(not c for r in rows for _, c in r):
        return None
    ncol = max(len(r) for r in rows)
    if len(rows) == 1 and ncol == 1:
        return ("p", rows[0][0][1].replace("<br>", "\n"))
    if complex_:
        out = ["<table>"]
        for r in rows:
            out.append("<tr>")
            for td, c in r:
                attrs = ""
                for a in ("colspan", "rowspan"):
                    if td.get(a, "1") != "1":
                        attrs += ' %s="%s"' % (a, td.get(a))
                out.append("<td%s>%s</td>" % (attrs, c))
            out.append("</tr>")
        out.append("</table>")
        return ("table", "\n".join(out))
    out = []
    for i, r in enumerate(rows):
        cells = [c.replace("|", "\\|") for _, c in r] + [""] * (ncol - len(r))
        out.append("| " + " | ".join(cells) + " |")
        if i == 0:
            out.append("|" + "---|" * ncol)
    return ("table", "\n".join(out))


def html_blocks(path):
    raw = open(path, encoding="utf-8").read()
    doc = lhtml.fromstring(raw)
    body = doc.find(".//body")
    if body is None:
        body = doc
    blocks = []

    def walk(e):
        for c in e:
            tag = c.tag if isinstance(c.tag, str) else ""
            if tag == "table":
                r = table_md(c)
                if r:
                    blocks.append(r if r[0] == "table" else ("p", r[1], {}))
            elif tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
                t = inline(c)
                if t:
                    blocks.append(("p", t, {"b": is_bold(c), "i": is_italic(c), "c": is_center(c)}))
            elif tag in ("script", "style", "head"):
                continue
            else:
                walk(c)
    walk(body)
    return blocks


def text_blocks(body):
    blocks = []
    for line in body.split("\n"):
        t = line.replace("\xa0", " ").strip()
        t = re.sub(r"[ \t]+", " ", t)
        if not t:
            continue
        blocks.append(("p", t, {}))
    return blocks


# --------------------------------------------------------------------------- structure
def detect(blocks, from_html):
    """Return list of items: ("h", kind, text) / ("art", label, title) / ("p", text, attrs) / ("table", md)."""
    items = []
    i = 0
    n = len(blocks)
    while i < n:
        b = blocks[i]
        if b[0] != "p":
            items.append(b)
            i += 1
            continue
        t, a = b[1], b[2]
        plain = re.sub(r"<[^>]+>", "", t)
        m = STRUCT_RE.match(plain) if len(plain) < 70 else None
        if m and (not from_html or a.get("b") or a.get("c")):
            unit = m.group(2).upper()
            title = None
            if i + 1 < n and blocks[i + 1][0] == "p":
                nt = blocks[i + 1][1]
                na = blocks[i + 1][2]
                np_ = re.sub(r"<[^>]+>", "", nt)
                ok = (len(np_) < 300 and not STRUCT_RE.match(np_) and not ART_RE.match(nt)
                      and (na.get("b") or na.get("c") if from_html else (np_.upper() == np_ or len(np_) < 160)))
                if ok:
                    title = nt
                    i += 1
            items.append(("h", unit, plain if not title else "%s. %s" % (plain.rstrip("."), title)))
            i += 1
            continue
        m = ART_RE.match(t)
        if m and len(plain) < 400 and (not from_html or a.get("b")):
            items.append(("art", m.group(1), m.group(2).strip()))
            i += 1
            continue
        items.append(b)
        i += 1
    return items


def render(items, title):
    kinds = [u for u in UNITS if any(it[0] == "h" and it[1] == u for it in items)]
    level = {u: 2 + k for k, u in enumerate(kinds)}
    art_level = 2 + len(kinds)
    out = ["# " + title, ""]
    for it in items:
        if it[0] == "h":
            lv = level[it[1]]
            out += [("#" * min(lv, 6) + " " + it[2]) if lv <= 6 else "**%s**" % it[2], ""]
        elif it[0] == "art":
            label = "%s straipsnis" % it[1]
            text = label + (". " + it[2] if it[2] else "")
            if art_level <= 6:
                out += ["#" * art_level + " " + text, ""]
            else:
                out += ["**%s**" % text, ""]
        elif it[0] == "table":
            out += [it[1], ""]
        else:
            t = it[1]
            a = it[2] if len(it) > 2 else {}
            lines = [md_escape(x) for x in t.split("\n")]
            t = "  \n".join(lines)
            if a.get("i") and not t.startswith("*"):
                t = "*%s*" % t.strip("*")
            out += [t, ""]
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- main
def read_mirror(raw, rel):
    t = open(os.path.join(raw, rel), encoding="utf-8").read()
    if t.startswith("---"):
        t = t.split("\n---", 1)[1][1:]
    lines = t.split("\n")
    # drop the mirror's own H1 and the editor note preceding the consolidation line
    while lines and (not lines[0].strip() or lines[0].startswith("# ")):
        lines.pop(0)
    if lines and lines[0].startswith("Redagavo:"):
        lines.pop(0)
    return "\n".join(lines)


def target(r):
    rid = r["id"]
    if rid in CODES:
        return "kodeksai", CODES[rid] + ".md"
    if rid == CONSTITUTION:
        return "konstitucija", "konstitucija.md"
    if r["rank"] == "konstitucija":
        return "tarptautines-sutartys", slugify(r["title"].replace("Lietuvos Respublikos ", "")) + ".md"
    if r["rank"] == "konstitucinis_istatymas":
        sub = "konstituciniai-istatymai"
    else:
        sub = "istatymai/" + ((r.get("date") or "0000")[:4])
    t = re.sub(r"^Lietuvos Respublikos\s+", "", r["title"])
    base = slugify(t, 80)
    if r.get("number"):
        base = slugify(r["number"], 20) + "-" + base
    return sub, (base or slugify(rid)) + ".md"


def main(raw, repo):
    index = [json.loads(l) for l in open(os.path.join(raw, "index.jsonl"), encoding="utf-8")]
    fetched = json.load(open(os.path.join(raw, "fetched.json"))) if os.path.exists(os.path.join(raw, "fetched.json")) else {}
    meta = json.load(open(os.path.join(raw, "index.meta.json")))
    # acts only present in e-seimas (newer than the mirror snapshot)
    for k, info in fetched.items():
        if k.startswith("eseimas:"):
            pt = info.get("page_title") or ""
            no, _, title = pt.partition(" ")
            index.append({"id": info["eseimas_id"], "title": title, "rank": "istatymas", "number": no,
                          "issuer": "Lietuvos Respublikos Seimas", "date": None, "in_force_from": None,
                          "consolidated_from": info.get("edition_from"), "eseimas_only": True})
    used = {}
    written = []
    for r in index:
        info = fetched.get(r["id"])
        if r.get("eseimas_only"):
            info = fetched["eseimas:" + r["id"]]
        official = bool(info and info.get("has_text"))
        if official:
            path = os.path.join(raw, "cache", "txt", info["eseimas_id"] + ".html")
            blocks = html_blocks(path)
            if r.get("eseimas_only") and not r.get("date"):
                head = " ".join(b[1] for b in blocks[:30] if b[0] == "p")
                m = re.search(r"(\d{4}) m\. \w+ \d+ d\. Nr\.", head)
                r["date"] = m.group(1) if m else TODAY[:4]
            items = detect(blocks, True)
            cons_from = info.get("edition_from")
            cons_to = info.get("edition_to")
            text_source = ESEIMAS + info["url"]
            snapshot = None
        else:
            body = read_mirror(raw, r["text"])
            items = detect(text_blocks(body), False)
            cons_from = r.get("consolidated_from")
            cons_to = None
            mirror = r["mirror"]
            rev = meta[mirror].split()
            repo_url = {"yiin": "https://github.com/Yiin/lt-teises-aktai",
                        "legalize-lt": "https://github.com/legalize-dev/legalize-lt"}[mirror]
            sub = r["text"].split("/", 1)[1]
            text_source = "%s/blob/%s/%s" % (repo_url, rev[0], sub)
            snapshot = rev[1][:10]
        sub, fn = target(r)
        key = sub + "/" + fn
        if key in used:
            fn = fn[:-3] + "-" + slugify(r["id"])[:12] + ".md"
            key = sub + "/" + fn
        used[key] = r["id"]
        typ = {"konstitucija": "constitution", "konstitucinis_istatymas": "constitutional_law",
               "kodeksas": "code", "istatymas": "act"}[r["rank"]]
        if r["id"] in CODES:
            typ = "code"
        if sub == "tarptautines-sutartys":
            typ = "treaty"
        title = r["title"].strip()
        if r.get("eseimas_only"):
            etar = None
        else:
            etar = "https://www.e-tar.lt/portal/lt/legalAct/" + r["id"]
        fm = [
            "---",
            "title: " + yaml_str(title),
            "identifier: " + yaml_str(r["id"] if not r.get("eseimas_only") else info["eseimas_id"]),
        ]
        if r.get("number"):
            fm.append("number: " + yaml_str(r["number"]))
        fm += ["type: " + typ, "jurisdiction: lt", "language: lt"]
        if r.get("date") and len(r["date"]) == 10:
            fm.append("date: " + r["date"])
        if r.get("in_force_from"):
            fm.append("in_force_from: " + r["in_force_from"])
        if cons_from:
            fm.append("last_amended: " + cons_from)
        if cons_to:
            fm.append("consolidated_version_until: " + cons_to)
        fm.append("status: in_force")
        if r.get("issuer"):
            fm.append("issuer: " + yaml_str(r["issuer"]))
        if etar:
            fm.append("source: " + yaml_str(etar))
        if official:
            fm.append("eseimas: " + yaml_str(info.get("portal")))
        fm.append("text_source: " + yaml_str(text_source))
        if official:
            fm.append("text_origin: \"e-seimas.lrs.lt (official consolidated HTML)\"")
        else:
            fm.append("text_origin: \"data.gov.lt TAR open data (tekstas_lt) via %s mirror, snapshot %s\"" % (r["mirror"], snapshot))
        fm += ["retrieved: " + TODAY, "---", ""]
        md = "\n".join(fm) + render(items, title)
        d = os.path.join(repo, sub)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        written.append((sub, fn, r["id"], "official" if official else r["mirror"]))
    with open(os.path.join(raw, "written.json"), "w") as f:
        json.dump(written, f, ensure_ascii=False)
    from collections import Counter
    print(len(written), Counter((w[0].split("/")[0], w[3]) for w in written))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
