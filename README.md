# LawCodex — Lithuania (Lietuva)

Lithuanian legislation in force (the Constitution, codes and laws adopted by the Seimas) as
Markdown, one file per act, in the official language (Lithuanian). The texts are the consolidated
versions (*suvestinė redakcija*) of the Register of Legal Acts (*Teisės aktų registras*, TAR).

Retrieved: **2026-10-12**. Read the [Sources](#sources) and [Known gaps](#known-gaps) sections
before relying on these files. Most texts come from a public mirror of the official open data,
whose texts date from **spring 2026**. Only the Constitution, the 12 codes and 17 other laws were
downloaded from the official site on the retrieval date.

## Contents

| Category | Directory | Files | Text origin |
|---|---|---:|---|
| Constitution (*Lietuvos Respublikos Konstitucija*) | `konstitucija/` | 1 | official (e-seimas), current |
| Codes (*kodeksai*) | `kodeksai/` | 12 | official (e-seimas), current |
| Constitutional laws (*konstituciniai įstatymai*) | `konstituciniai-istatymai/` | 21 | open-data mirror |
| Laws (*įstatymai*) | `istatymai/<year>/` | 12,193 | 17 official (e-seimas), 12,176 open-data mirror |
| International constitutions registered as *Konstitucija* in TAR (UNESCO, IOM) | `tarptautines-sutartys/` | 2 | open-data mirror |
| **Total** | | **12,229** | |

The `istatymai/` set holds every act of type *Įstatymas* that the open-data mirror lists as in
force. That is 1,749 base laws (many of them laws ratifying treaties) and 10,444 amending laws
(*... įstatymo ... straipsnių pakeitimo įstatymas*). In Lithuania an amending law stays formally
in force after its changes are merged into the consolidated text of the law it amends. Amending
laws are therefore kept, so that their own final and transitional provisions are available.

The 12 codes in `kodeksai/` are the Civil (*civilinis*), Civil Procedure (*civilinio proceso*),
Criminal (*baudžiamasis*), Criminal Procedure (*baudžiamojo proceso*), Penal Enforcement (*bausmių
vykdymo*), Administrative Offences (*administracinių nusižengimų*), Labour (*darbo*), Electoral
(*rinkimų*), Railway Transport (*geležinkelių transporto*), Road Transport (*kelių transporto*),
Inland Waterway Transport (*vidaus vandenų transporto*) and State Politicians' Conduct (*valstybės
politikų elgesio*) codes. Most Lithuanian codes are enacted as the annex of a law "approving,
bringing into force and implementing" them. The file holds that whole consolidated act: the
approval law followed by the code.

### Layout and file names

- `konstitucija/konstitucija.md`, `kodeksai/<code-name>.md`.
- `istatymai/<year>/<number>-<title-slug>.md`: laws are grouped by year of adoption. The file
  name starts with the official document number (e.g. `I-1240`, `XIV-1028`), followed by the
  ASCII-transliterated title, without the leading "Lietuvos Respublikos". Example:
  `istatymai/1996/i-1240-statybos-istatymas.md` is the Law on Construction.
- `konstituciniai-istatymai/<number>-<title-slug>.md`.

### File format

```markdown
---
title: "Lietuvos Respublikos statybos įstatymas"
identifier: "TAR.F31E79DEC55D"        # e-tar document id (TAR.<hex> or 32-hex)
number: "I-1240"                       # official document number
type: act                              # constitution | code | constitutional_law | act | treaty
jurisdiction: lt
language: lt
date: 1996-03-19                       # adoption date
in_force_from: 1996-09-01
last_amended: 2026-10-01               # first day of the consolidated version reproduced
consolidated_version_until: 2026-10-31 # (official texts only) last day of that version
status: in_force
issuer: "Lietuvos Respublikos Seimas"
source: "https://www.e-tar.lt/portal/lt/legalAct/TAR.F31E79DEC55D"
eseimas: "https://e-seimas.lrs.lt/portal/legalAct/lt/TAD/TAIS.26250/asr"   # official texts only
text_source: "https://e-seimas.lrs.lt/rs/actualedition/TAIS.26250/FWzmRQAHaJ/"
text_origin: "e-seimas.lrs.lt (official consolidated HTML)"
retrieved: 2026-10-12
---
```

The text starts with the official consolidation header (*Suvestinė redakcija nuo …*, publication
reference, *i. k.* code). Headings follow the act's structure:
*knyga* (book) › *dalis* (part) › *skyrius* (chapter) › *skirsnis* (section) › *poskirsnis*
(subsection) › *straipsnis* (article). Levels are assigned from the units actually present in the
act, starting at `##`. Articles use the deepest heading level, or **bold** when that would be deeper
than `######`. The editorial notes of the consolidated text (*Straipsnio pakeitimai: Nr. …*)
are kept. Superscript article and paragraph numbers (e.g. 5<sup>1</sup>) are kept as `<sup>`.

## Sources

1. **e-seimas.lrs.lt**: the *Teisės aktų informacinė sistema* (TAIS) of the Seimas, which publishes
   the same consolidated texts as TAR. The Constitution, the 12 codes and 17 laws were downloaded on
   2026-10-12 as official HTML, from `/rs/actualedition/<id>/<edition>/`. The current edition was
   chosen from `/portal/legalActEditions/lt/TAD/<id>`. The `eseimas:` field gives the page.
2. **Open data of the Register of Legal Acts** (data.gov.lt dataset
   [2613](https://data.gov.lt/datasets/2613/), "TARIS duomenų rinkiniai", maintained by the Office
   of the Seimas). Everything else comes from this dataset, through two public git mirrors:
   - [Yiin/lt-teises-aktai](https://github.com/Yiin/lt-teises-aktai) (commit `fac6653`, 2026-08-09):
     12,102 files. Its texts keep the order and much of the formatting of the source, including
     tables for part of the acts. Its newest act was adopted on 2026-03-19.
   - [legalize-dev/legalize-lt](https://github.com/legalize-dev/legalize-lt) (commit `76c1b57`,
     2026-09-25): 97 files. These are acts missing from the first mirror, or acts whose text there is
     truncated. They are plain text only.

   Each file's `text_source` is the exact mirror file and commit used. Its `source` is the act's
   official e-tar page.

### Why mirrors

The official sources could not be harvested in bulk from our network, and no access restriction
was circumvented:

- `data.gov.lt` / `get.data.gov.lt` (the official bulk API) answer every request with a FortiWeb
  "Web Page Blocked" page (HTTP 500, attack id 20000018), whatever the User-Agent.
- `www.e-tar.lt` (all paths, including `robots.txt` and the `/rs/` REST endpoints) answers with a
  Cloudflare JavaScript challenge (HTTP 403 "Just a moment…").
- On `e-seimas.lrs.lt`, all search forms (JSF/PrimeFaces POST requests, including pagination of the
  public pre-filled searches) are rejected by an F5 bot-defence ("Unauthorized Request Blocked")
  for clients that do not run its JavaScript. Plain GET requests on document pages work.
  However, e-seimas uses its own document ids (`TAIS.<n>` or a 32-hex id), which differ from
  the e-tar ids, so documents cannot be enumerated or looked up without the search.
  The 30 acts taken from e-seimas are those whose e-seimas id was known: the Constitution and
  codes (ids found manually), plus the acts linked from the public "Naujausi įsigalioję
  įstatymai" page. Each one is matched to the index through the e-tar link in its own header.
- `apps.lrs.lt` (Seimas XML open data) disallows all crawling in `robots.txt`, and it did not
  answer from our network. It does not provide legal-act texts in any case.

No `robots.txt` exists on e-seimas.lrs.lt (404). Requests were sequential or ran 2 at a time, with
a delay of at least 0.4 s and the User-Agent `LawCodex/1.0 (+https://github.com/LawCodex)`.

## Known gaps

- **The mirror texts are not current.** Mirror files (12,199 of 12,229) reproduce the consolidated
  version that was in the open data in spring 2026. Amendments adopted after about mid-March 2026
  are not in them. Check `last_amended` and the e-tar `source` link. The 30 e-seimas files are
  current as of 2026-10-12.
- **Laws adopted after mid-March 2026 are mostly missing.** The only ones present are the few that
  legalize-lt carries (14 adopted in March–September 2026) and 1 e-seimas act (XV-805). In-force status is the mirror's, so an act repealed since then
  may still be included.
- 8 mirror files reproduce a consolidated version that starts after the retrieval date
  (`last_amended` later than 2026-10-12). That is the version the mirror held as the latest.
- In some mirror texts, tables (mostly in annexes) are flattened into one cell per line. That is
  how they appear in the plain-text open-data field.
- **Not included:** Government resolutions (*Vyriausybės nutarimai*), Presidential decrees,
  ministerial orders and other secondary legislation. No bulk source for them was reachable (see
  above). The mirrors carry only laws, so these could not be enumerated. Repealed acts and English
  translations are also not included.
- The constitutional acts that form part of the Constitution (Article 150) are separate files.
  Constitutional Law "Dėl Lietuvos valstybės" and Constitutional Act "Dėl Lietuvos Respublikos
  nesijungimo į postsovietines Rytų sąjungas" are in `konstituciniai-istatymai/`. The Constitutional
  Act on membership of the European Union is in the law that added it to the Constitution:
  `istatymai/2004/ix-2343-konstitucijos-papildymo-konstituciniu-aktu-del-lietuvos-respublikos-narystes.md`.

## Licence

Under Article 5 of the Lithuanian Law on Copyright and Related Rights (*Autorių teisių ir gretutinių
teisių įstatymas*), legal acts and their official translations are not objects of copyright. The
TAR open data are published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
(source: Teisės aktų registras, Lietuvos Respublikos Seimo kanceliarija). The Seimas open data are
also published under CC BY 4.0, with attribution to www.lrs.lt and the Office of the Seimas. The
scripts in `scripts/` are released into the public domain.

## Regenerating

```sh
pip install -r scripts/requirements.txt
RAW=/path/to/scratch            # raw downloads and caches (not committed)
python3 scripts/build_index.py "$RAW"     # clone/pull the mirrors, build $RAW/index.jsonl
python3 scripts/lt_fetch.py    "$RAW"     # official e-seimas texts for known ids (cached)
python3 scripts/convert.py     "$RAW" .   # write the Markdown files
```

If `data.gov.lt` is reachable from your network, the index and texts should be rebuilt from the
official API instead (`https://get.data.gov.lt/datasets/gov/lrsk/teises_aktai/Dokumentas` and
`.../Suvestine`, with the `tekstas_lt` field). That would also cover Government resolutions.
